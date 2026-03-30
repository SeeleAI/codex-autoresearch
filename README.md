# codex-autoresearch

This directory is now a unified wrapper around three internal modules:

- [`autoresearch/`](./autoresearch): the internal `codex-autoresearch-engine` planning, recovery, and execution skill
- [`env-bootstrap/`](./env-bootstrap): the environment detection and developer-tool readiness skill
- [`git-runtime-governor/`](./git-runtime-governor): the internal git governance skill for repo adoption, ignore policy, and per-round auto-commit

The public entrypoint is still `$codex-autoresearch`.

## Why This Was Split

The original `codex-autoresearch` payload has been moved into [`autoresearch/`](./autoresearch) as an internal engine module.

[`env-bootstrap/`](./env-bootstrap) checks hardware and tool readiness before autoresearch continues.

[`git-runtime-governor/`](./git-runtime-governor) is the unified upper governance layer for all git-related runtime behavior, including dirty worktree handling, experiment branch policy, `.gitignore` generation, and the mandatory auto-commit boundary before a round is finalized.

This split keeps one top-level visible skill while still separating engine and environment logic internally.

## Relationship Between The Runtime Layers

- root `SKILL.md`
  - the main orchestrator
  - decides whether a call is initialization, recovery, or ordinary iteration
  - sequences environment readiness checks and git governance before autoresearch when needed
- `autoresearch/`
  - owns the core plan, recovery, project-state, and autonomous iteration protocols as the internal `codex-autoresearch-engine`
- `env-bootstrap/`
  - owns environment auditing and readiness checks for hardware and developer tooling
- `git-runtime-governor/`
  - owns repo adoption, `.gitignore` policy, recovery-time git questioning, and the per-iteration auto-commit boundary

## Runtime Intent

### First initialization / adoption

1. Run environment detection through `env-bootstrap/`.
2. Route through `git-runtime-governor/` to decide git adoption, branch strategy, artifact retention, and `.gitignore` policy.
3. Treat that output as short-lived execution context plus persisted git policy.
4. Enter `autoresearch/` plan-mode initialization.

### Recovery / resume / continue

1. Run a lighter environment readiness check through `env-bootstrap/`.
2. Route through `git-runtime-governor/` for first-recovery git questioning and policy refresh.
3. If the environment is still compatible, continue through `autoresearch/`.
4. If there is a blocking environment gap, record the blocker and stop.

### Ordinary already-initialized iteration

1. Continue through `autoresearch/` directly.
2. Do not repeat environment probing unless symptoms suggest environment drift or missing tooling.
3. Require the engine to route each completed round through `git-runtime-governor/` after verification and before keep/discard/blocker finalization so in-policy git changes are auto-committed.

## Persistence Rules

Environment detection is primarily session context, not a default long-term artifact.

Only persist environment details into the project document system when:

- the user explicitly pins an environment choice such as a GPU, conda env, or toolchain, or
- an environment issue becomes a real blocker that must be tracked in project state

## Visibility Contract

Only the root `codex-autoresearch` directory should be exposed as a visible Codex skill.

The nested `autoresearch/` and `env-bootstrap/` directories exist so the root skill can load their internal protocols. They are implementation modules, not separate user-facing skill entries.

`git-runtime-governor/` is also internal-only. It must not expose `agents/openai.yaml`; the only visible skills in this repository are the root wrapper and `$autoresearch-internal-skill-creator`.

## Internal Module Governance

The visible maintenance entrypoint is `$autoresearch-internal-skill-creator`.

After any change to a skill or internal module in this repository, use that visible governance skill in `sync` mode so `INTERNAL-MODULES.md` and the internal module maps stay consistent with the current repository state.

The routing contract also has to stay aligned: initialization and first recovery go through `env-bootstrap` then `git-runtime-governor`, and every ordinary iteration must hit `git-runtime-governor` again after verification and before the round is finalized.

### Current Module Map

<!-- INTERNAL-MODULES:ROOT-README-START -->
- `autoresearch-internal-skill-creator/`: `visible-governance`. Create and maintain internal skill modules inside the codex-autoresearch repository. Use when Codex needs to scaffold a new internal module under this repo, wire it into the root or internal protocol documents, or rebuild INTERNAL-MODULES.md after any skill change in this repository.
- `autoresearch/`: `engine-protocol`. Internal execution engine for the `codex-autoresearch` wrapper. Use when maintaining or directly testing the autonomous improve-verify loop, runtime helpers, project-state integration, recovery logic, or exec/background control flow behind `$codex-autoresearch`. Do not use for ordinary one-shot coding help or casual Q&A.
- `env-bootstrap/`: `environment-collaboration`. Prepare and audit the local execution environment before coding, setup, install, download, training, mobile, web, or evaluation work. Use when Codex needs to normalize conda, proxy, GPU, Hugging Face mirror, Git/GitHub CLI, Node.js/web, Java/Android, container, or general developer tooling. When the user says `init`, run a concise multi-stack environment audit, install missing `git` and `gh` if possible, and require the user to log into GitHub with `gh auth login`.
<!-- INTERNAL-MODULES:ROOT-README-END -->
