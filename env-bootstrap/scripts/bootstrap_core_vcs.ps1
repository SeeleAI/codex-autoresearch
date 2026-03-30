param(
  [switch]$DryRun
)

$NeedGit = -not (Get-Command git -ErrorAction SilentlyContinue)
$NeedGh = -not (Get-Command gh -ErrorAction SilentlyContinue)

if (-not $NeedGit -and -not $NeedGh) {
  "[env-bootstrap] git and gh already installed"
  "[env-bootstrap] next: run gh auth login if GitHub authentication is not complete"
  exit 0
}

function Invoke-Step {
  param(
    [string]$File,
    [string[]]$Args
  )

  if ($DryRun) {
    "[dry-run] {0} {1}" -f $File, ($Args -join " ")
    return
  }

  & $File @Args
  if ($LASTEXITCODE -ne 0) {
    throw "command failed: $File $($Args -join ' ')"
  }
}

"[env-bootstrap] installing required core tools"

if (Get-Command winget -ErrorAction SilentlyContinue) {
  if ($NeedGit) {
    Invoke-Step -File "winget" -Args @("install", "--id", "Git.Git", "-e", "--accept-package-agreements", "--accept-source-agreements")
  }
  if ($NeedGh) {
    Invoke-Step -File "winget" -Args @("install", "--id", "GitHub.cli", "-e", "--accept-package-agreements", "--accept-source-agreements")
  }
} elseif (Get-Command choco -ErrorAction SilentlyContinue) {
  $Packages = @()
  if ($NeedGit) {
    $Packages += "git"
  }
  if ($NeedGh) {
    $Packages += "gh"
  }
  $Args = @("install", "-y") + $Packages
  Invoke-Step -File "choco" -Args $Args
} elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
  $Packages = @()
  if ($NeedGit) {
    $Packages += "git"
  }
  if ($NeedGh) {
    $Packages += "gh"
  }
  $Args = @("install") + $Packages
  Invoke-Step -File "scoop" -Args $Args
} elseif (Get-Command conda -ErrorAction SilentlyContinue) {
  $Packages = @()
  if ($NeedGit) {
    $Packages += "git"
  }
  if ($NeedGh) {
    $Packages += "gh"
  }
  $Args = @("install", "-y", "-c", "conda-forge") + $Packages
  Invoke-Step -File "conda" -Args $Args
} else {
  Write-Error "[env-bootstrap] no supported package manager found for automatic git/gh installation"
  exit 1
}

"[env-bootstrap] installation step finished"
"[env-bootstrap] required next step: run gh auth login"
