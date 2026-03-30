#!/usr/bin/env bash

set -euo pipefail

dry_run="${1:-}"

need_git=0
need_gh=0

if ! command -v git >/dev/null 2>&1; then
  need_git=1
fi

if ! command -v gh >/dev/null 2>&1; then
  need_gh=1
fi

if [ "$need_git" -eq 0 ] && [ "$need_gh" -eq 0 ]; then
  echo "[env-bootstrap] git and gh already installed"
  echo "[env-bootstrap] next: run gh auth login if GitHub authentication is not complete"
  exit 0
fi

run_cmd() {
  if [ "$dry_run" = "--dry-run" ]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi
  "$@"
}

with_privilege() {
  if command -v sudo >/dev/null 2>&1; then
    run_cmd sudo "$@"
  else
    run_cmd "$@"
  fi
}

echo "[env-bootstrap] installing required core tools"

if command -v apt-get >/dev/null 2>&1; then
  with_privilege apt-get update
  packages=()
  [ "$need_git" -eq 1 ] && packages+=("git")
  [ "$need_gh" -eq 1 ] && packages+=("gh")
  with_privilege apt-get install -y "${packages[@]}"
elif command -v dnf >/dev/null 2>&1; then
  packages=()
  [ "$need_git" -eq 1 ] && packages+=("git")
  [ "$need_gh" -eq 1 ] && packages+=("gh")
  with_privilege dnf install -y "${packages[@]}"
elif command -v yum >/dev/null 2>&1; then
  packages=()
  [ "$need_git" -eq 1 ] && packages+=("git")
  [ "$need_gh" -eq 1 ] && packages+=("gh")
  with_privilege yum install -y "${packages[@]}"
elif command -v pacman >/dev/null 2>&1; then
  packages=()
  [ "$need_git" -eq 1 ] && packages+=("git")
  [ "$need_gh" -eq 1 ] && packages+=("github-cli")
  with_privilege pacman -Sy --noconfirm "${packages[@]}"
elif command -v zypper >/dev/null 2>&1; then
  packages=()
  [ "$need_git" -eq 1 ] && packages+=("git")
  [ "$need_gh" -eq 1 ] && packages+=("gh")
  with_privilege zypper install -y "${packages[@]}"
elif command -v brew >/dev/null 2>&1; then
  packages=()
  [ "$need_git" -eq 1 ] && packages+=("git")
  [ "$need_gh" -eq 1 ] && packages+=("gh")
  run_cmd brew install "${packages[@]}"
elif command -v conda >/dev/null 2>&1; then
  packages=()
  [ "$need_git" -eq 1 ] && packages+=("git")
  [ "$need_gh" -eq 1 ] && packages+=("gh")
  run_cmd conda install -y -c conda-forge "${packages[@]}"
else
  echo "[env-bootstrap] no supported package manager found for automatic git/gh installation" >&2
  exit 1
fi

echo "[env-bootstrap] installation step finished"
echo "[env-bootstrap] required next step: run gh auth login"
