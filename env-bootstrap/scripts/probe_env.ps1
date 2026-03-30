param(
  [string]$Mode = "default"
)

$DefaultProxyHost = "127.0.0.1"
$DefaultProxyPort = "7897"
$BootstrapHelperPath = (Join-Path $PSScriptRoot "bootstrap_core_vcs.ps1")

function Get-EnvValue {
  param([string[]]$Names)

  foreach ($Name in $Names) {
    $Value = [Environment]::GetEnvironmentVariable($Name)
    if ($Value) {
      return $Value
    }
  }

  return $null
}

function Get-ValueOrDefault {
  param(
    $Value,
    [string]$Default
  )

  if ($null -eq $Value) {
    return $Default
  }

  $Text = $Value.ToString()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $Default
  }

  return $Text
}

function Get-PlatformName {
  if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    return "Windows"
  }
  if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::OSX)) {
    return "macOS"
  }
  if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Linux)) {
    return "Linux"
  }

  return "Unknown"
}

function Get-OsSummary {
  $Platform = Get-PlatformName

  if ($Platform -eq "Windows") {
    try {
      $Os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
      return "{0} {1}" -f $Os.Caption, $Os.Version
    } catch {
      try {
        $Os = Get-WmiObject Win32_OperatingSystem -ErrorAction Stop
        return "{0} {1}" -f $Os.Caption, $Os.Version
      } catch {
        return "Windows"
      }
    }
  }

  try {
    return [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
  } catch {
    return $Platform
  }
}

function Pick-ProxyValue {
  $Value = Get-EnvValue -Names @("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY")
  if ($Value) {
    return $Value
  }

  return "{0}:{1}" -f $DefaultProxyHost, $DefaultProxyPort
}

function Normalize-ProxyEndpoint {
  param([string]$Raw)

  if (-not $Raw) {
    return ""
  }

  $Normalized = $Raw -replace '^(http|https|socks5|socks5h)://', ''
  if ($Normalized.Contains('/')) {
    $Normalized = $Normalized.Split('/')[0]
  }

  return $Normalized
}

function Check-TcpPort {
  param(
    [string]$Host,
    [string]$Port
  )

  try {
    $Client = New-Object System.Net.Sockets.TcpClient
    $Async = $Client.BeginConnect($Host, [int]$Port, $null, $null)
    if (-not $Async.AsyncWaitHandle.WaitOne(2000, $false)) {
      $Client.Close()
      return "closed"
    }

    $Client.EndConnect($Async) | Out-Null
    $Client.Close()
    return "open"
  } catch {
    return "closed"
  }
}

function Check-ProxyHttp {
  param([string]$Proxy)

  if (-not $Proxy) {
    return "unknown"
  }

  $ProxyUri = $Proxy
  if ($ProxyUri -notmatch '^[a-z]+://') {
    $ProxyUri = "http://{0}" -f $ProxyUri
  }

  foreach ($Uri in @("https://github.com", "https://hf-mirror.com")) {
    try {
      Invoke-WebRequest -Uri $Uri -Method Head -Proxy $ProxyUri -TimeoutSec 10 -ErrorAction Stop | Out-Null
      return "ok"
    } catch {
    }
  }

  return "fail"
}

function Get-ProxyHealthSummary {
  $ProxyValue = Pick-ProxyValue
  $Endpoint = Normalize-ProxyEndpoint -Raw $ProxyValue

  if (-not $Endpoint.Contains(':')) {
    return "invalid | {0}" -f $ProxyValue
  }

  $Host = $Endpoint.Split(':')[0]
  $Port = $Endpoint.Split(':')[-1]

  if (-not $Host -or -not $Port) {
    return "invalid | {0}" -f $ProxyValue
  }

  $TcpState = Check-TcpPort -Host $Host -Port $Port
  $HttpState = Check-ProxyHttp -Proxy $ProxyValue

  if ($TcpState -eq "open" -and $HttpState -eq "ok") {
    return "ok | {0} | tcp={1} | outbound={2}" -f $ProxyValue, $TcpState, $HttpState
  }
  if ($TcpState -eq "open") {
    return "degraded | {0} | tcp={1} | outbound={2}" -f $ProxyValue, $TcpState, $HttpState
  }

  return "fail | {0} | tcp={1} | outbound={2}" -f $ProxyValue, $TcpState, $HttpState
}

function Write-Kv {
  param(
    [string]$Key,
    [string]$Value
  )

  "{0,-22} {1}" -f ("{0}:" -f $Key), $Value
}

function Get-CommandPath {
  param([string]$Name)

  $Command = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $Command) {
    return "not found"
  }

  if ($Command.Source) {
    return $Command.Source
  }

  if ($Command.Path) {
    return $Command.Path
  }

  return $Command.Name
}

function Write-CommandStatus {
  param([string]$Name)
  Write-Kv -Key $Name -Value (Get-CommandPath -Name $Name)
}

function Get-ToolStatus {
  param(
    [string]$Name,
    [scriptblock]$VersionScript
  )

  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    return "missing"
  }

  try {
    $Version = & $VersionScript 2>&1 | Select-Object -First 1
    if ($Version) {
      return "ok | {0}" -f $Version.ToString().Trim()
    }
  } catch {
  }

  return "ok"
}

function Get-PlatformAuditSummary {
  return "os={0}; winget={1}; choco={2}; scoop={3}; wsl={4}" -f `
    (Get-OsSummary), `
    (Get-ToolStatus -Name "winget" -VersionScript { winget --version }), `
    (Get-ToolStatus -Name "choco" -VersionScript { choco --version }), `
    (Get-ToolStatus -Name "scoop" -VersionScript { scoop --version }), `
    (Get-ToolStatus -Name "wsl" -VersionScript { wsl --version })
}

if ($Mode -eq "init") {
  "[env-bootstrap] init audit"
  Write-Kv -Key "date" -Value ((Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))
  Write-Kv -Key "shell" -Value ("powershell {0}" -f $PSVersionTable.PSVersion.ToString())
  Write-Kv -Key "platform" -Value (Get-PlatformName)
  Write-Kv -Key "cwd" -Value (Get-Location).Path
  Write-Kv -Key "proxy" -Value ("http={0}; https={1}" -f `
    (Get-ValueOrDefault -Value (Get-EnvValue -Names @("http_proxy")) -Default "unset"), `
    (Get-ValueOrDefault -Value (Get-EnvValue -Names @("https_proxy")) -Default "unset"))
  Write-Kv -Key "proxy health" -Value (Get-ProxyHealthSummary)
  Write-Kv -Key "hf endpoint" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("HF_ENDPOINT")) -Default "unset")

  $GhAuthStatus = "not-authenticated"
  if (Get-Command gh -ErrorAction SilentlyContinue) {
    gh auth status > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
      $GhAuthStatus = "authenticated"
    }
  }

  "audit:"
  "- platform: {0}" -f (Get-PlatformAuditSummary)
  "- vcs: git={0}; gh={1}; gh-auth={2}" -f `
    (Get-ToolStatus -Name "git" -VersionScript { git --version }), `
    (Get-ToolStatus -Name "gh" -VersionScript { gh --version }), `
    $GhAuthStatus
  "- python: python={0}; conda={1}" -f `
    (Get-ToolStatus -Name "python" -VersionScript { python -V }), `
    (Get-ToolStatus -Name "conda" -VersionScript { conda --version })
  "- web: node={0}; npm={1}; pnpm={2}; yarn={3}; bun={4}" -f `
    (Get-ToolStatus -Name "node" -VersionScript { node --version }), `
    (Get-ToolStatus -Name "npm" -VersionScript { npm --version }), `
    (Get-ToolStatus -Name "pnpm" -VersionScript { pnpm --version }), `
    (Get-ToolStatus -Name "yarn" -VersionScript { yarn --version }), `
    (Get-ToolStatus -Name "bun" -VersionScript { bun --version })
  "- java-android: java={0}; javac={1}; gradle={2}; mvn={3}; adb={4}; sdkmanager={5}" -f `
    (Get-ToolStatus -Name "java" -VersionScript { java -version 2>&1 }), `
    (Get-ToolStatus -Name "javac" -VersionScript { javac -version 2>&1 }), `
    (Get-ToolStatus -Name "gradle" -VersionScript { gradle --version }), `
    (Get-ToolStatus -Name "mvn" -VersionScript { mvn -version }), `
    (Get-ToolStatus -Name "adb" -VersionScript { adb version }), `
    (Get-ToolStatus -Name "sdkmanager" -VersionScript { sdkmanager --version })
  "- android-env: ANDROID_HOME={0}; ANDROID_SDK_ROOT={1}" -f `
    (Get-ValueOrDefault -Value (Get-EnvValue -Names @("ANDROID_HOME")) -Default "unset"), `
    (Get-ValueOrDefault -Value (Get-EnvValue -Names @("ANDROID_SDK_ROOT")) -Default "unset")
  "- containers: docker={0}; podman={1}" -f `
    (Get-ToolStatus -Name "docker" -VersionScript { docker --version }), `
    (Get-ToolStatus -Name "podman" -VersionScript { podman --version })

  if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $GpuSummary = nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>$null | Select-Object -First 1
    "- gpu: ok | {0}" -f ($(if ($GpuSummary) { $GpuSummary } else { "available" }))
  } else {
    "- gpu: missing"
  }

  $MissingCore = @()
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    $MissingCore += "git"
  }
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    $MissingCore += "gh"
  }

  "action:"
  if ($MissingCore.Count -gt 0) {
    "- required: install missing core tools -> {0}" -f ($MissingCore -join ", ")
    "- command: pwsh -File {0}" -f $BootstrapHelperPath
  } else {
    "- required: core git/github tooling already present"
    if ($GhAuthStatus -eq "authenticated") {
      "- next: GitHub CLI authentication already available"
    } else {
      "- next: run gh auth login"
    }
  }

  exit 0
}

"[env-bootstrap] environment probe"
Write-Kv -Key "date" -Value ((Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))
Write-Kv -Key "shell" -Value ("powershell {0}" -f $PSVersionTable.PSVersion.ToString())
Write-Kv -Key "platform" -Value (Get-PlatformAuditSummary)
Write-Kv -Key "cwd" -Value (Get-Location).Path
Write-Kv -Key "conda env" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("CONDA_DEFAULT_ENV")) -Default "inactive")

Write-CommandStatus -Name "conda"
if (Get-Command conda -ErrorAction SilentlyContinue) {
  Write-Kv -Key "conda version" -Value (Get-ValueOrDefault -Value (conda --version 2>$null) -Default "unavailable")
  Write-Kv -Key "conda base" -Value (Get-ValueOrDefault -Value (conda info --base 2>$null) -Default "unavailable")
}

if (Get-Command python -ErrorAction SilentlyContinue) {
  Write-Kv -Key "python" -Value (Get-CommandPath -Name "python")
  Write-Kv -Key "python version" -Value (python -V 2>&1)
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  Write-Kv -Key "py" -Value (Get-CommandPath -Name "py")
  Write-Kv -Key "python version" -Value (py -V 2>&1)
} else {
  Write-Kv -Key "python" -Value "not found"
}

Write-CommandStatus -Name "pip"
Write-Kv -Key "http_proxy" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("http_proxy")) -Default "unset")
Write-Kv -Key "https_proxy" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("https_proxy")) -Default "unset")
Write-Kv -Key "HTTP_PROXY" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("HTTP_PROXY")) -Default "unset")
Write-Kv -Key "HTTPS_PROXY" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("HTTPS_PROXY")) -Default "unset")
Write-Kv -Key "all_proxy" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("all_proxy")) -Default "unset")
Write-Kv -Key "ALL_PROXY" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("ALL_PROXY")) -Default "unset")
Write-Kv -Key "proxy health" -Value (Get-ProxyHealthSummary)
Write-Kv -Key "HF_ENDPOINT" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("HF_ENDPOINT")) -Default "unset")
Write-Kv -Key "HF_HOME" -Value (Get-ValueOrDefault -Value (Get-EnvValue -Names @("HF_HOME")) -Default "unset")

if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  Write-Kv -Key "nvidia-smi" -Value (Get-CommandPath -Name "nvidia-smi")
  "gpu summary:"
  $GpuLines = nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>$null
  if ($GpuLines) {
    $GpuLines
  } else {
    nvidia-smi
  }
} else {
  Write-Kv -Key "nvidia-smi" -Value "not found"
}
