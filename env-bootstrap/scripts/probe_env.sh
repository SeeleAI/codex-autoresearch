#!/usr/bin/env bash

set -u

mode="${1:-default}"
default_proxy_host="127.0.0.1"
default_proxy_port="7897"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
bootstrap_helper="${script_dir}/bootstrap_core_vcs.sh"

platform_summary() {
  if command -v sw_vers >/dev/null 2>&1; then
    printf 'macOS %s' "$(sw_vers -productVersion 2>/dev/null || echo unknown)"
  elif [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf '%s %s' "${NAME:-Linux}" "${VERSION_ID:-}"
  else
    uname -sr 2>/dev/null || echo unknown
  fi
}

pick_proxy_value() {
  if [ -n "${http_proxy:-}" ]; then
    echo "${http_proxy}"
  elif [ -n "${https_proxy:-}" ]; then
    echo "${https_proxy}"
  elif [ -n "${HTTP_PROXY:-}" ]; then
    echo "${HTTP_PROXY}"
  elif [ -n "${HTTPS_PROXY:-}" ]; then
    echo "${HTTPS_PROXY}"
  else
    echo "${default_proxy_host}:${default_proxy_port}"
  fi
}

normalize_proxy_endpoint() {
  local raw="$1"
  raw="${raw#http://}"
  raw="${raw#https://}"
  raw="${raw#socks5://}"
  raw="${raw#socks5h://}"
  raw="${raw%%/*}"
  echo "${raw}"
}

check_tcp_port() {
  local host="$1"
  local port="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket()
sock.settimeout(2.0)
try:
    sock.connect((host, port))
except OSError:
    print("closed")
    sys.exit(1)
else:
    print("open")
    sys.exit(0)
finally:
    sock.close()
PY
  else
    echo "unknown"
    return 2
  fi
}

check_proxy_http() {
  local proxy="$1"
  if command -v curl >/dev/null 2>&1; then
    if curl -x "$proxy" -fsSI --connect-timeout 5 --max-time 10 https://github.com >/dev/null 2>&1; then
      echo "ok"
      return 0
    fi
    if curl -x "$proxy" -fsSI --connect-timeout 5 --max-time 10 https://hf-mirror.com >/dev/null 2>&1; then
      echo "ok"
      return 0
    fi
    echo "fail"
    return 1
  fi
  echo "unknown"
  return 2
}

proxy_health_summary() {
  local proxy_value
  local endpoint
  local host
  local port
  local tcp_state
  local http_state

  proxy_value="$(pick_proxy_value)"
  endpoint="$(normalize_proxy_endpoint "$proxy_value")"
  host="${endpoint%%:*}"
  port="${endpoint##*:}"

  if [ -z "$host" ] || [ -z "$port" ] || [ "$host" = "$port" ]; then
    echo "invalid | ${proxy_value}"
    return
  fi

  tcp_state="$(check_tcp_port "$host" "$port" 2>/dev/null || true)"
  http_state="$(check_proxy_http "$proxy_value" 2>/dev/null || true)"

  if [ "$tcp_state" = "open" ] && [ "$http_state" = "ok" ]; then
    echo "ok | ${proxy_value} | tcp=${tcp_state} | outbound=${http_state}"
  elif [ "$tcp_state" = "open" ] && [ "$http_state" = "unknown" ]; then
    echo "partial | ${proxy_value} | tcp=${tcp_state} | outbound=${http_state}"
  elif [ "$tcp_state" = "open" ]; then
    echo "degraded | ${proxy_value} | tcp=${tcp_state} | outbound=${http_state}"
  else
    echo "fail | ${proxy_value} | tcp=${tcp_state:-unknown} | outbound=${http_state:-unknown}"
  fi
}

print_kv() {
  local key="$1"
  local value="$2"
  printf '%-22s %s\n' "${key}:" "${value}"
}

print_cmd_status() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    print_kv "$name" "$(command -v "$name")"
  else
    print_kv "$name" "not found"
  fi
}

tool_status() {
  local name="$1"
  local version_cmd="$2"
  if command -v "$name" >/dev/null 2>&1; then
    local version
    version="$(bash -lc "$version_cmd" 2>/dev/null | head -n 1)"
    if [ -n "$version" ]; then
      echo "ok | ${version}"
    else
      echo "ok"
    fi
  else
    echo "missing"
  fi
}

platform_audit_summary() {
  printf 'os=%s; brew=%s; apt-get=%s; dnf=%s; yum=%s; pacman=%s; zypper=%s; xcode-select=%s; xcodebuild=%s; pod=%s' \
    "$(platform_summary)" \
    "$(tool_status brew 'brew --version')" \
    "$(tool_status apt-get 'apt-get --version')" \
    "$(tool_status dnf 'dnf --version')" \
    "$(tool_status yum 'yum --version')" \
    "$(tool_status pacman 'pacman --version')" \
    "$(tool_status zypper 'zypper --version')" \
    "$(tool_status xcode-select 'xcode-select -p')" \
    "$(tool_status xcodebuild 'xcodebuild -version')" \
    "$(tool_status pod 'pod --version')"
}

if [ "$mode" = "init" ]; then
  echo "[env-bootstrap] init audit"
  print_kv "date" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  print_kv "shell" "${SHELL:-unknown}"
  print_kv "platform" "$(platform_summary)"
  print_kv "cwd" "$(pwd)"
  print_kv "proxy" "http=${http_proxy:-unset}; https=${https_proxy:-unset}"
  print_kv "proxy health" "$(proxy_health_summary)"
  print_kv "hf endpoint" "${HF_ENDPOINT:-unset}"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh_auth_status="authenticated"
  else
    gh_auth_status="not-authenticated"
  fi
  echo "audit:"
  echo "- platform: $(platform_audit_summary)"
  echo "- vcs: git=$(tool_status git 'git --version'); gh=$(tool_status gh 'gh --version'); gh-auth=${gh_auth_status}"
  echo "- python: python=$(tool_status python 'python -V'); conda=$(tool_status conda 'conda --version')"
  echo "- web: node=$(tool_status node 'node --version'); npm=$(tool_status npm 'npm --version'); pnpm=$(tool_status pnpm 'pnpm --version'); yarn=$(tool_status yarn 'yarn --version'); bun=$(tool_status bun 'bun --version')"
  echo "- java-android: java=$(tool_status java 'java -version'); javac=$(tool_status javac 'javac -version'); gradle=$(tool_status gradle 'gradle --version'); mvn=$(tool_status mvn 'mvn -version'); adb=$(tool_status adb 'adb version'); sdkmanager=$(tool_status sdkmanager 'sdkmanager --version')"
  echo "- android-env: ANDROID_HOME=${ANDROID_HOME:-unset}; ANDROID_SDK_ROOT=${ANDROID_SDK_ROOT:-unset}"
  echo "- containers: docker=$(tool_status docker 'docker --version'); podman=$(tool_status podman 'podman --version')"
  if command -v nvidia-smi >/dev/null 2>&1; then
    local_gpu="$(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null | head -n 1)"
    echo "- gpu: ok | ${local_gpu:-available}"
  else
    echo "- gpu: missing"
  fi

  missing_core=""
  if ! command -v git >/dev/null 2>&1; then
    missing_core="git"
  fi
  if ! command -v gh >/dev/null 2>&1; then
    if [ -n "$missing_core" ]; then
      missing_core="${missing_core}, gh"
    else
      missing_core="gh"
    fi
  fi

  if [ -n "$missing_core" ]; then
    echo "action:"
    echo "- required: install missing core tools -> ${missing_core}"
    echo "- command: bash ${bootstrap_helper}"
  else
    echo "action:"
    echo "- required: core git/github tooling already present"
    if [ "$gh_auth_status" = "authenticated" ]; then
      echo "- next: GitHub CLI authentication already available"
    else
      echo "- next: run gh auth login"
    fi
  fi
  exit 0
fi

echo "[env-bootstrap] environment probe"

print_kv "date" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
print_kv "shell" "${SHELL:-unknown}"
print_kv "platform" "$(platform_audit_summary)"
print_kv "cwd" "$(pwd)"
print_kv "conda env" "${CONDA_DEFAULT_ENV:-inactive}"

print_cmd_status "conda"
if command -v conda >/dev/null 2>&1; then
  print_kv "conda version" "$(conda --version 2>/dev/null || echo unavailable)"
  print_kv "conda base" "$(conda info --base 2>/dev/null || echo unavailable)"
fi

if command -v python >/dev/null 2>&1; then
  print_kv "python" "$(command -v python)"
  print_kv "python version" "$(python -V 2>&1)"
elif command -v python3 >/dev/null 2>&1; then
  print_kv "python3" "$(command -v python3)"
  print_kv "python3 version" "$(python3 -V 2>&1)"
else
  print_kv "python" "not found"
fi

print_cmd_status "pip"

print_kv "http_proxy" "${http_proxy:-unset}"
print_kv "https_proxy" "${https_proxy:-unset}"
print_kv "HTTP_PROXY" "${HTTP_PROXY:-unset}"
print_kv "HTTPS_PROXY" "${HTTPS_PROXY:-unset}"
print_kv "all_proxy" "${all_proxy:-unset}"
print_kv "ALL_PROXY" "${ALL_PROXY:-unset}"
print_kv "proxy health" "$(proxy_health_summary)"
print_kv "HF_ENDPOINT" "${HF_ENDPOINT:-unset}"
print_kv "HF_HOME" "${HF_HOME:-unset}"

if command -v nvidia-smi >/dev/null 2>&1; then
  print_kv "nvidia-smi" "$(command -v nvidia-smi)"
  echo "gpu summary:"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null || nvidia-smi
else
  print_kv "nvidia-smi" "not found"
fi
