---
name: codex-autoresearch
description: Unified public entrypoint for project initialization, recovery, environment readiness checks, git governance, and autonomous autoresearch execution. Use this root skill as the primary `$codex-autoresearch` entrypoint. It orchestrates the nested `env-bootstrap` readiness skill, the internal `git-runtime-governor` governance module, and the internal `codex-autoresearch-engine` execution skill.
---

# Codex Autoresearch

Use this root skill as the public `$codex-autoresearch` entrypoint.

Treat this directory as a wrapper over three nested internal modules:

- `env-bootstrap/` for environment readiness and drift checks
- `git-runtime-governor/` for repo adoption, git policy capture, `.gitignore` governance, and auto-commit control
- `autoresearch/` for the actual planning, recovery, and autonomous execution protocol

Keep the root skill focused on routing. Do not duplicate the full engine workflow here.

## Routing Rules

1. Read this root file first when `$codex-autoresearch` is invoked from this directory.
2. Classify the request as one of:
   - first initialization or project adoption
   - recovery, resume, or environment-sensitive restart
   - ordinary already-initialized iteration
3. For initialization or recovery, load `env-bootstrap/SKILL.md` first and run the appropriate readiness probe.
4. After readiness is established for initialization or recovery, route through `git-runtime-governor/SKILL.md` so git adoption, dirty-worktree ownership, branch strategy, artifact retention, and `.gitignore` policy are decided before execution continues.
5. After git governance is established, continue in `autoresearch/SKILL.md` as the main execution protocol.
6. For ordinary already-initialized iteration, go to `autoresearch/SKILL.md` unless the request or symptoms point to environment drift. The engine must still route every completed round through `git-runtime-governor/SKILL.md` after verification and before the final keep/discard/blocker resolution is recorded.

## Environment Probe Policy

- Initialization: run a broad readiness audit before planning or launch.
- Recovery: run a lighter probe focused on tool availability, hardware visibility, and environment drift.
- Ordinary iteration: skip repeated probes unless the task shows environment-related symptoms.
- Audit first by default. Do not install tools proactively unless the missing dependency is a real blocker.
- Keep environment findings as session context unless the user explicitly pins an environment choice or the blocker must be recorded in project state.

## Public Contract

- The public human-facing entrypoint remains `$codex-autoresearch`.
- `autoresearch/` remains the internal `codex-autoresearch-engine`.
- `env-bootstrap/` remains the internal environment readiness module.
- `git-runtime-governor/` remains the internal git governance module for repo attachment, ignore policy, and round-level auto-commit.
- Only the root directory should be exposed as a visible Codex skill.
- The nested directories are implementation structure, not additional user-facing skills.

## Internal Governance

- Use `$autoresearch-internal-skill-creator` when you need to create a new internal module or resynchronize the internal module registry.
- After any change to a skill or internal module in this repository, call the creator in `sync` mode before considering the work complete.
- Keep `INTERNAL-MODULES.md` in sync with the repository's actual module layout and wiring.
- Keep the root routing rules aligned with the internal git governance contract: initialization and first recovery route through `git-runtime-governor`, and ordinary iterations require the engine to auto-commit through that module after verification and before finalization.

### Internal Module Map

<!-- INTERNAL-MODULES:ROOT-SKILL-START -->
- `autoresearch-internal-skill-creator/`: `visible-governance`. Create and maintain internal skill modules inside the codex-autoresearch repository. Use when Codex needs to scaffold a new internal module under this repo, wire it into the root or internal protocol documents, or rebuild INTERNAL-MODULES.md after any skill change in this repository.
- `autoresearch/`: `engine-protocol`. Internal execution engine for the `codex-autoresearch` wrapper. Use when maintaining or directly testing the autonomous improve-verify loop, runtime helpers, project-state integration, recovery logic, or exec/background control flow behind `$codex-autoresearch`. Do not use for ordinary one-shot coding help or casual Q&A.
- `env-bootstrap/`: `environment-collaboration`. Prepare and audit the local execution environment before coding, setup, install, download, training, mobile, web, or evaluation work. Use when Codex needs to normalize conda, proxy, GPU, Hugging Face mirror, Git/GitHub CLI, Node.js/web, Java/Android, container, or general developer tooling. When the user says `init`, run a concise multi-stack environment audit, install missing `git` and `gh` if possible, and require the user to log into GitHub with `gh auth login`.
<!-- INTERNAL-MODULES:ROOT-SKILL-END -->
