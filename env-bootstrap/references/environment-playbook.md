# Environment Playbook

## Contents

- Init audit flow
- Baseline check
- Core tool remediation
- Conda patterns
- Proxy patterns
- Hugging Face mirror patterns
- GPU validation
- Failure patterns

## Init Audit Flow

When the user says `init`, use the skill as a concise environment auditor instead of a Python-only setup helper.

When this playbook mentions `<skill-root>`, it means the directory containing the loaded `env-bootstrap/SKILL.md`. In the common repo-local install this is `.agents/skills/codex-autoresearch/env-bootstrap`.

Use the OS-appropriate probe.

Linux and macOS:

```bash
bash <skill-root>/scripts/probe_env.sh init
```

Windows PowerShell:

```powershell
pwsh -File <skill-root>/scripts/probe_env.ps1 -Mode init
```

Windows PowerShell 5 fallback:

```powershell
powershell -ExecutionPolicy Bypass -File <skill-root>/scripts/probe_env.ps1 -Mode init
```

The output should be short enough to reuse as session context and broad enough to cover:

- host OS, shell, and workspace
- platform package managers and OS-specific tooling
- proxy and `HF_ENDPOINT`
- proxy usability and fallback candidates
- `git` and `gh`
- Python and conda
- Node.js and web package managers
- Java and Android tooling
- container tooling
- GPU visibility

If `git` or `gh` is missing, recommend the narrow remediation helper immediately and run it only when the current task actually needs repair:

```bash
bash <skill-root>/scripts/bootstrap_core_vcs.sh
```

or on Windows:

```powershell
pwsh -File <skill-root>/scripts/bootstrap_core_vcs.ps1
```

If `gh` becomes available, require the user to finish interactive authentication:

```bash
gh auth login
```

Do not force-install any other missing stack during `init`. Keep those as short audit findings only.

## Baseline Check

Run the bundled probe that matches the host OS first.

Linux and macOS:

```bash
bash <skill-root>/scripts/probe_env.sh
```

Windows:

```powershell
pwsh -File <skill-root>/scripts/probe_env.ps1
```

Capture at least:

- host OS and package-manager layer
- active shell
- current working directory
- conda availability
- active conda environment
- Python executable and version
- proxy variables
- `HF_ENDPOINT`
- `nvidia-smi` summary

For the broader `init` path, prefer:

```bash
bash <skill-root>/scripts/probe_env.sh init
```

or on Windows:

```powershell
pwsh -File <skill-root>/scripts/probe_env.ps1 -Mode init
```

Use that output as the environment review record for follow-up tasks.

## Core Tool Remediation

`git` and `gh` are mandatory in `init` mode.

Install them with the bundled helper for the current OS.

Linux and macOS:

```bash
bash <skill-root>/scripts/bootstrap_core_vcs.sh
```

Windows:

```powershell
pwsh -File <skill-root>/scripts/bootstrap_core_vcs.ps1
```

The helper should stay narrow and only target `git` and `gh`.

After `gh` is installed, ask the user to authenticate:

```bash
gh auth login
```

The GitHub login must be completed by the user in their own interactive session.

## Conda Patterns

Prefer one-off command execution:

```bash
conda run -n <env> <command>
```

Examples:

```bash
conda run -n navila python -V
conda run -n navila python -m pip install -r requirements.txt
conda run -n navila python train.py
```

Use activation only when the workflow truly needs a persistent shell:

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate <env>
python -V
python -m pip list | head
```

If `conda activate` fails in a non-interactive shell, do not guess. Source `conda.sh` explicitly as shown above.

On Windows PowerShell, prefer:

```powershell
conda run -n <env> python -V
conda run -n <env> python -m pip install -r requirements.txt
```

Use `conda activate <env>` only when the shell already has Conda's PowerShell integration loaded.

## Proxy Patterns

When downloads fail or external services are unreachable, apply the machine-default proxy first.

Linux and macOS:

```bash
export http_proxy=127.0.0.1:7897
export https_proxy=127.0.0.1:7897
```

Windows PowerShell:

```powershell
$env:http_proxy="127.0.0.1:7897"
$env:https_proxy="127.0.0.1:7897"
```

If the proxy still fails, retry the common fallbacks in this order:

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

Windows PowerShell equivalents:

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

Examples:

```bash
export http_proxy=127.0.0.1:7897
export https_proxy=127.0.0.1:7897
git clone https://github.com/AnjieCheng/NaVILA
```

```powershell
$env:http_proxy="127.0.0.1:7897"
$env:https_proxy="127.0.0.1:7897"
git clone https://github.com/AnjieCheng/NaVILA
```

```bash
export http_proxy=127.0.0.1:7897
export https_proxy=127.0.0.1:7897
python -m pip install -r requirements.txt
```

Probe the proxy before a long install or clone when possible:

```bash
bash <skill-root>/scripts/probe_env.sh init
```

or on Windows:

```powershell
pwsh -File <skill-root>/scripts/probe_env.ps1 -Mode init
```

The audit should report both the chosen proxy values and whether the proxy passed a local port check plus an outbound HTTP probe.

If the proxy causes trouble after setup, cleanly remove it:

```bash
unset http_proxy
unset https_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
unset all_proxy
unset ALL_PROXY
```

Windows PowerShell cleanup:

```powershell
Remove-Item Env:http_proxy -ErrorAction SilentlyContinue
Remove-Item Env:https_proxy -ErrorAction SilentlyContinue
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:all_proxy -ErrorAction SilentlyContinue
Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
```

## Hugging Face Mirror Patterns

Prefer the mirror before model and dataset downloads:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

Windows PowerShell:

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
```

Examples:

```bash
export HF_ENDPOINT=https://hf-mirror.com
conda run -n navila python -c "from huggingface_hub import snapshot_download; snapshot_download('bert-base-uncased')"
```

```bash
export HF_ENDPOINT=https://hf-mirror.com
conda run -n navila python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('bert-base-uncased')"
```

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
conda run -n navila python -c "from huggingface_hub import snapshot_download; snapshot_download('bert-base-uncased')"
```

Keep the mirror export in the same shell as the download command. Do not assume child tools inherit state from a different terminal.

## GPU Validation

Check driver visibility:

```bash
nvidia-smi
```

Check framework visibility in the target environment:

```bash
conda run -n <env> python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

If CUDA is unavailable in the framework while `nvidia-smi` works:

- confirm the correct conda environment is active
- confirm the installed wheel matches CUDA expectations
- confirm the command is not falling back to a system Python

On Windows, prefer the same validation steps in PowerShell and keep the command inside the intended Conda environment.

## Failure Patterns

`conda: command not found`

- Find the base install with `which conda` or user shell init files.
- Use `source "$(conda info --base)/etc/profile.d/conda.sh"` before `conda activate`.
- Fall back to `conda run -n <env> ...` when activation is unnecessary.

`pip installs into the wrong interpreter`

- Use `python -m pip ...`.
- Print `python -c "import sys; print(sys.executable)"` before the install.
- On Windows, `py -c "import sys; print(sys.executable)"` is an acceptable fallback when `python` resolves incorrectly.

`git clone` or `pip install` times out

- Export the proxy variables.
- Retry once with the fallback list in the documented order.
- Re-run the environment probe and confirm the proxy health line reports `ok`.

`huggingface_hub` cannot download weights

- Export `HF_ENDPOINT=https://hf-mirror.com`.
- Keep proxy exports enabled if the mirror itself still needs the local proxy path.

nvidia-smi works but Python reports no CUDA

- Inspect the active Python interpreter.
- Verify the framework build inside the target conda environment.
- Treat this as an environment mismatch, not a model bug.
