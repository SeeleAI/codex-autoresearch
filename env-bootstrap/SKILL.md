---
name: env-bootstrap
description: Prepare and audit the local execution environment before coding, setup, install, download, training, mobile, web, or evaluation work. Use when Codex needs to normalize conda, proxy, GPU, Hugging Face mirror, Git/GitHub CLI, Node.js/web, Java/Android, container, or general developer tooling. When the user says `init`, run a concise multi-stack environment audit, install missing `git` and `gh` if possible, and require the user to log into GitHub with `gh auth login`.
---

# Env Bootstrap

Use this skill to normalize the machine environment before running repository setup, dependency installation, model download, training, evaluation, mobile builds, web development, or debugging commands.

When this skill mentions `<skill-root>`, it means the directory containing the loaded `SKILL.md`. In the common repo-local install this is `.agents/skills/codex-autoresearch/env-bootstrap`.

## Internal Module Metadata

Visibility: internal
Module type: environment-collaboration
Primary caller: codex-autoresearch

## Internal Module Map

<!-- INTERNAL-MODULES:ENV-SKILL-START -->
- `env-bootstrap/`: `environment-collaboration`. Prepare and audit the local execution environment before coding, setup, install, download, training, mobile, web, or evaluation work. Use when Codex needs to normalize conda, proxy, GPU, Hugging Face mirror, Git/GitHub CLI, Node.js/web, Java/Android, container, or general developer tooling. When the user says `init`, run a concise multi-stack environment audit, install missing `git` and `gh` if possible, and require the user to log into GitHub with `gh auth login`.
<!-- INTERNAL-MODULES:ENV-SKILL-END -->

Choose the probe and remediation entrypoints by host OS:

- Linux and macOS: use the bundled shell scripts in `scripts/*.sh`.
- Windows: use the bundled PowerShell scripts in `scripts/*.ps1`.
- Do not assume WSL, Git Bash, or Cygwin on Windows when a native PowerShell path exists.

## Operating Modes

### `init`

Use `init` as the environment initialization and audit entrypoint.

1. Run the OS-appropriate environment probe to generate a concise but broad audit record.

```bash
bash <skill-root>/scripts/probe_env.sh init
```

```powershell
pwsh -File <skill-root>/scripts/probe_env.ps1 -Mode init
```

```powershell
powershell -ExecutionPolicy Bypass -File <skill-root>/scripts/probe_env.ps1 -Mode init
```

2. Treat the audit output as reusable context for the rest of the session.
3. If `git` or `gh` is missing, recommend the OS-appropriate bootstrap helper immediately and only run it when the current task actually requires remediation.
4. After `gh` is available, require the user to authenticate their own GitHub account with `gh auth login`.
5. Do not force-install other missing toolchains. Record them as optional or task-specific gaps.

### Default mode

Use the default mode when the task already names a concrete stack and only needs lightweight normalization before commands run.

1. Run the OS-appropriate probe for a focused snapshot.

```bash
bash <skill-root>/scripts/probe_env.sh
```

```powershell
pwsh -File <skill-root>/scripts/probe_env.ps1
```

2. Prefer `conda run -n <env> <command>` for one-off commands that do not need an interactive shell.
3. Initialize `conda activate` only when a long-lived shell session is required.
4. Export proxy variables only when external network access is failing or a command must reach external services.
5. Export `HF_ENDPOINT=https://hf-mirror.com` before downloading Hugging Face models or datasets on this machine.
6. Verify GPU visibility before heavy installs, training, or inference jobs.

## Audit Coverage For `init`

The `init` audit should stay concise while covering:

- host OS, shell, and current workspace
- platform package managers and OS-specific developer tooling
- proxy and Hugging Face mirror state
- proxy usability and fallback candidates
- Git and GitHub CLI availability
- Python and conda
- Node.js and common web package managers
- Java and Android SDK tools
- container tooling
- GPU visibility

If a category is absent, report it briefly as `missing` instead of expanding into long troubleshooting text.

## Git And GitHub CLI Policy

- `git` and `gh` are the only tools that become mandatory during `init`.
- If either tool is missing, treat that as a readiness gap and recommend the bundled OS-appropriate bootstrap helper. Run the helper only when the current task actually needs repair, not for a read-only readiness check.
- Prefer the machine's existing package manager. Keep the install scope narrow: only `git` and `gh`.
- If installation succeeds, instruct the user to complete:

```bash
gh auth login
```

- The user must perform the login interactively with their own GitHub account.

## Conda Rules

- Prefer `conda run -n <env> <command>` for deterministic non-interactive execution.
- On Linux and macOS, if activation is required, run:

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate <env>
```

- On Windows PowerShell, if activation is required, run:

```powershell
conda activate <env>
```

- If `conda activate` is unavailable in PowerShell, prefer `conda run -n <env> <command>` instead of modifying the profile during the session.
- Use `python -m pip ...` inside the selected conda environment instead of bare `pip ...`.
- Record the active environment name and Python executable in command logs when debugging setup failures.

## Proxy Rules

- When external network access fails, export the user-preferred proxy values first.
- On Linux and macOS:

```bash
export http_proxy=127.0.0.1:7897
export https_proxy=127.0.0.1:7897
```

- On Windows PowerShell:

```powershell
$env:http_proxy="127.0.0.1:7897"
$env:https_proxy="127.0.0.1:7897"
```

- Probe the configured proxy during `init` and treat local port reachability plus one outbound HTTP check as the default health signal.
- If the default proxy is unavailable, try these fallback candidates in order.
- Linux and macOS:

```bash
export http_proxy=127.0.0.1:7890
export https_proxy=127.0.0.1:7890
```

```bash
export http_proxy=http://127.0.0.1:7897
export https_proxy=http://127.0.0.1:7897
```

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
```

```bash
export all_proxy=socks5://127.0.0.1:7897
export ALL_PROXY=socks5://127.0.0.1:7897
```

- Windows PowerShell:

```powershell
$env:http_proxy="127.0.0.1:7890"
$env:https_proxy="127.0.0.1:7890"
```

```powershell
$env:http_proxy="http://127.0.0.1:7897"
$env:https_proxy="http://127.0.0.1:7897"
```

```powershell
$env:http_proxy="http://127.0.0.1:7890"
$env:https_proxy="http://127.0.0.1:7890"
```

```powershell
$env:all_proxy="socks5://127.0.0.1:7897"
$env:ALL_PROXY="socks5://127.0.0.1:7897"
```

- If a tool rejects host:port syntax and expects a URL, retry with the scheme-qualified HTTP variant first:

```bash
export http_proxy=http://127.0.0.1:7897
export https_proxy=http://127.0.0.1:7897
```

- PowerShell equivalent:

```powershell
$env:http_proxy="http://127.0.0.1:7897"
$env:https_proxy="http://127.0.0.1:7897"
```

- Keep proxy changes scoped to the current shell or the specific command whenever practical.
- Prefer the shortest working configuration. Do not export every fallback at once.
- Unset proxy variables after the network-sensitive step if they interfere with local-only tooling.

## Hugging Face Rules

- Before `huggingface_hub`, `transformers`, `datasets`, or model-weight downloads, export:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

- On Windows PowerShell:

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
```

- Keep download commands inside the intended conda environment so cached packages and Python dependencies stay consistent.
- Reuse existing caches unless the task specifically requires a clean download.

## GPU Rules

- Check `nvidia-smi` before GPU-dependent installs or jobs.
- For Python ML stacks, verify framework-level CUDA visibility, not just driver visibility.
- Treat "driver visible but framework cannot see CUDA" as an environment problem, usually caused by the wrong conda environment, wheel variant, or CUDA runtime mismatch.

## Command Hygiene

- Read [references/environment-playbook.md](references/environment-playbook.md) when you need concrete command templates or troubleshooting steps.
- Keep environment changes minimal, explicit, and easy to undo.
- Prefer per-command environment injection over editing shell startup files.
- Prefer native Windows tooling on Windows instead of translating shell snippets through WSL unless the task explicitly targets WSL.
- Surface the exact environment assumptions in your progress update before running expensive commands.
- Avoid destructive cleanup unless the user explicitly asks for it.

## Resources

- `scripts/probe_env.sh`: Linux and macOS environment probe for focused snapshots and `init` audits.
- `scripts/probe_env.ps1`: Windows-native environment probe for focused snapshots and `init` audits.
- `scripts/bootstrap_core_vcs.sh`: Linux and macOS helper to install missing `git` and `gh`.
- `scripts/bootstrap_core_vcs.ps1`: Windows helper to install missing `git` and `gh`.
- `references/environment-playbook.md`: Load for command recipes, `init` behavior, and troubleshooting guidance.
