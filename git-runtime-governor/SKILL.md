---
name: git-runtime-governor
description: Govern all git operations for autoresearch-managed runtime projects, including repository adoption, ignore policy generation, recovery-time git questioning, and per-iteration auto-commit routing.
---

# Git Runtime Governor

Internal module for `codex-autoresearch`.

## Internal Module Metadata

Visibility: internal
Module type: shared-tooling
Primary caller: autoresearch

## Responsibilities

- Govern all git operations for autoresearch-managed runtime projects, including repository adoption, ignore policy generation, recovery-time git questioning, and per-iteration auto-commit routing.
- Keep this module internal. Do not add `agents/openai.yaml`.

This module is the single git governance authority for autoresearch-managed runtime projects.

It owns:

- git adoption for workspaces that do not yet have `.git`
- integration with repos that already have git history, branches, or dirty worktrees
- policy capture for autoresearch artifacts, runtime files, media, documents, caches, and custom classes
- generation of a real `.gitignore` from the markdown template and the user's answers
- per-iteration auto-commit after verification and before final keep/discard/blocker resolution
- companion repo git policy alignment

Persist the long-lived git policy in `.agent-os/autoresearch-config.md`.

## Required Routing

`codex-autoresearch` must route to this module in all of these situations:

1. initialization or project adoption
2. first recovery or first continue after prior state exists
3. every iteration after verification and before the final round decision is recorded
4. any explicit user request that is primarily about git, branches, worktrees, ignores, staging, or commits

## Required Defaults

- Default branch strategy: use a dedicated experiment branch unless the user explicitly chooses a different strategy.
- Existing git repos: respect the current repo and branch layout first, then ask how autoresearch should attach.
- No-git workspaces: ask before initializing git and before absorbing existing files into version control.
- Dirty worktrees: ask who owns the changes before unattended execution starts.
- Unresolved file-category policy: default to conservative ignore rather than accidental inclusion.
- Companion repos: ask and store policy per repo; never assume the primary repo's rules automatically apply.
- Binary, media, and PDF files: include them in auto-commit only when the stored policy explicitly allows that category.

## Initialization And First Recovery

During initialization and first recovery, ask in grouped batches until the high-risk git decisions are explicit.

Use the staged questionnaire in `references/git-policy-questionnaire.md`.

Question groups must cover:

- repo topology and ownership
- branch or worktree strategy
- autoresearch state and runtime artifacts
- media and binary retention
- document retention
- companion repo policy
- auto-commit expectations and audit preferences

After the answers are stable:

1. update the git policy section in `.agent-os/autoresearch-config.md`
2. use `references/general-gitignore-template.md` plus the answers to generate candidate ignore rules
3. merge the generated managed block into the real `.gitignore`
4. confirm the final commit policy fingerprint that later auto-commits will reference

## Per-Iteration Auto-Commit

After the round's verification command completes, but before the final keep/discard/blocker decision is written, route to this module.

At that point:

1. read the persisted git policy from `.agent-os/autoresearch-config.md`
2. refresh `.gitignore` if the policy changed in this session
3. stage all modifications that are in-policy for the managed repo set
4. generate a structured commit message containing iteration, mode, summary, and policy fingerprint
5. create the git commit on the experiment branch
6. return control to the main autoresearch flow so the round can be finalized

This module governs all in-policy git changes for the managed repo set, not only files directly edited by autoresearch.

## References

- `references/git-policy-questionnaire.md`
- `references/general-gitignore-template.md`

## Helper Script

Use `scripts/git_runtime_governor.py` for deterministic helpers:

- `print-template` to print the markdown template text
- `render-gitignore` to generate the managed `.gitignore` block
- `merge-gitignore` to merge or refresh the managed block in a real `.gitignore`
- `commit-message` to produce the structured auto-commit message
