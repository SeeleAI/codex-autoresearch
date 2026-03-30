---
name: codex-autoresearch-engine
description: "Internal execution engine for the `codex-autoresearch` wrapper. Use when maintaining or directly testing the autonomous improve-verify loop, runtime helpers, project-state integration, recovery logic, or exec/background control flow behind `$codex-autoresearch`. Do not use for ordinary one-shot coding help or casual Q&A."
---

# codex-autoresearch

Autonomous goal-directed iteration with a built-in project operating system. Modify -> Verify -> Git auto-commit -> Keep/Discard -> Repeat.

This internal module is the main execution engine under the public `codex-autoresearch` wrapper. When used through the root entrypoint, initialization and recovery are expected to run an `env-bootstrap` probe first and then route through `git-runtime-governor` before execution continues.

## Internal Module Metadata

Visibility: internal
Module type: engine-protocol
Primary caller: codex-autoresearch

## Internal Module Map

<!-- INTERNAL-MODULES:ENGINE-SKILL-START -->
- `autoresearch/`: `engine-protocol`. Internal execution engine for the `codex-autoresearch` wrapper. Use when maintaining or directly testing the autonomous improve-verify loop, runtime helpers, project-state integration, recovery logic, or exec/background control flow behind `$codex-autoresearch`. Do not use for ordinary one-shot coding help or casual Q&A.
- `git-runtime-governor/`: `shared-tooling`. Govern all git operations for autoresearch-managed runtime projects, including repository adoption, ignore policy generation, recovery-time git questioning, and per-iteration auto-commit routing.
<!-- INTERNAL-MODULES:ENGINE-SKILL-END -->

## When Activated

1. Classify the request as `loop`, `plan`, `debug`, `fix`, `security`, `ship`, or `exec`, and parse any inline config from the prompt.
2. Load `references/core-principles.md` and `references/structured-output-spec.md`. For active execution modes (`loop`, `debug`, `fix`, `security`, `ship`, `exec`), also load `references/runtime-hard-invariants.md`.
3. Load only the additional references the current situation needs:
   - `references/session-resume-protocol.md` when resuming or controlling an existing run
   - `references/environment-awareness.md` before choosing hardware-sensitive work
   - `references/interaction-wizard.md` for every new interactive launch (`loop`, `debug`, `fix`, `security`, `ship`) before execution begins
   - `references/results-logging.md` only when debugging TSV/state semantics or helper behavior directly
4. For first initialization/adoption and recovery/resume work under the root wrapper, assume an `env-bootstrap` readiness probe has already run or must run before launch continues. Then load `../git-runtime-governor/SKILL.md` so git adoption, dirty-worktree ownership, branch strategy, and ignore policy are governed before launch.
5. Treat the unified project document system as a first-class runtime dependency. The root recovery path is `AGENTS.md` -> `.agent-os/project-index.md` -> active items -> `.agent-os/run-log.md`; runtime artifacts remain the execution evidence and control-plane source.
6. Load the selected mode workflow reference plus only the detailed cross-cutting protocols that actually apply (`lessons`, `pivot`, `health-check`, `parallel`, `web-search`, `hypothesis-perspectives`).
7. If the request is primarily about git, branches, worktrees, `.gitignore`, staging, or commits, load `../git-runtime-governor/SKILL.md` as a required companion protocol even outside initialization or recovery.
8. Use the bundled helper scripts when stateful artifacts or runtime control are involved. Resolve them relative to the loaded execution-skill root (`<skill-root>/scripts/...`), not the target repo root. In the common repo-local install this means commands such as `python3 .agents/skills/codex-autoresearch/autoresearch/scripts/autoresearch_init_run.py ...`. For repo-managed control-plane helpers (`autoresearch_resume_check.py`, `autoresearch_launch_gate.py`, `autoresearch_resume_prompt.py`, `autoresearch_supervisor_status.py`, `autoresearch_runtime_ctl.py status/stop`), prefer `--repo <repo>` and let the helper derive default artifact paths.
9. During every completed iteration, after verification and any guard handling but before the final keep/discard/blocker resolution is recorded, route to `../git-runtime-governor/SKILL.md` so the managed repos receive the required policy-governed auto-commit.
10. Execute the selected workflow exactly as written and produce the required structured output, project documents, and runtime artifacts.

## Core Loop

1. Read the relevant context.
2. Define a mechanical success metric.
3. Establish a baseline.
4. Make one focused change.
5. Verify with a command.
6. Keep or discard the change.
7. Log the result.
8. Repeat.

## Modes

| Mode | Purpose | Primary Reference |
|------|---------|-------------------|
| `loop` | Run the autonomous improvement loop | `references/loop-workflow.md` |
| `plan` | Convert a vague goal into a launch-ready config | `references/plan-workflow.md` |
| `debug` | Hunt bugs with evidence and hypotheses | `references/debug-workflow.md` |
| `fix` | Iteratively reduce errors to zero | `references/fix-workflow.md` |
| `security` | Run a structured security audit | `references/security-workflow.md` |
| `ship` | Gate and execute a ship workflow | `references/ship-workflow.md` |
| `exec` | Non-interactive CI/CD mode with JSON output | `references/exec-workflow.md` |

Use `Mode: <name>` in the prompt to force a specific subworkflow.

## Required Config

For the generic loop, the following fields are needed internally. Codex infers them from the user's natural language input and repo context, then fills gaps through guided conversation:

- `Goal`
- `Scope`
- `Metric`
- `Direction`
- `Verify`

Optional but recommended:

- `Guard`
- `Iterations`
- `Run tag`
- `Stop condition`

For every new interactive run, use the wizard contract in `references/interaction-wizard.md`.

## Unified Project System

`codex-autoresearch` now owns a built-in project document system.

Required files:

- root `AGENTS.md`
- root `CLAUDE.md`
- `.agent-os/project-index.md`
- `.agent-os/requirements.md`
- `.agent-os/change-decisions.md`
- `.agent-os/architecture-milestones.md`
- `.agent-os/todo.md`
- `.agent-os/acceptance-report.md`
- `.agent-os/lessons-learned.md`
- `.agent-os/run-log.md`
- `.agent-os/autoresearch-config.md`
- `.agent-os/autoresearch-runtime.md`

Truth model:

- Project documents are the primary semantic truth.
- Runtime artifacts are the primary execution evidence and control plane.
- Reconcile both before autonomous resume.

## Explicit Run Modes

- `$codex-autoresearch` remains the only public human-facing entrypoint.
- This file is an internal engine protocol loaded by the root wrapper; do not expose it as a separate visible skill entry.
- If the repo is not initialized with the unified project system, do not launch directly. Force a `plan`-mode initialization or adoption pass first.
- For a new interactive run, scan the repo, ask the confirmation questions, and require an explicit run-mode choice: **foreground** or **background**.
- If the user chooses **foreground**, keep the loop in the current Codex session. Use the shared helper scripts (`autoresearch_init_run.py`, `autoresearch_record_iteration.py`, `autoresearch_select_parallel_batch.py`, `autoresearch_supervisor_status.py`) and do not create launch/runtime control artifacts.
- If the user chooses **background**, call `autoresearch_runtime_ctl.py launch` to persist the confirmed launch manifest and start the detached runtime controller in one step. The runtime itself should execute non-interactive `codex exec` sessions with the generated runtime prompt supplied on stdin. This skill defaults those detached sessions to the sandboxed `workspace_write` path and only upgrades to `danger_full_access` (`--dangerously-bypass-approvals-and-sandbox`) when the user explicitly asks for unrestricted execution. If the mini-wizard outcome is "fresh start", call `autoresearch_runtime_ctl.py launch --fresh-start` so prior persistent run-control artifacts are archived as part of the same handoff.
- If the user resumes an existing interactive run in the other mode, synchronize `autoresearch-state.json` internally before continuing. Background `start` already performs that sync automatically before it relaunches nested Codex sessions; `autoresearch_set_session_mode.py` remains an internal/scripted recovery helper, not a normal user-facing step.
- Treat the repo where the run starts as the **primary repo**. Single-repo runs are the default. If the task truly spans multiple codebases, declare **companion repos** explicitly and give each repo its own scope instead of stuffing absolute paths into one mixed scope string.
- Foreground and background share the same experiment protocol, but they are mutually exclusive for a given repo/run. Never try to keep both modes active against the same `research-results.tsv` / `autoresearch-state.json` artifacts at the same time.
- For `status`, `stop`, or `resume` requests, stay on the same skill entry. `status` and `stop` apply to background runs only; foreground runs stay in the current session.
- `exec` remains the advanced / CI path. It is fully specified upfront and does not use the interactive handoff.

## Hard Rules

1. **Ask before act for new interactive launches.** For `loop`, `debug`, `fix`, `security`, and `ship`, ALWAYS scan the repo and ask at least one round of clarifying questions before the run starts. Load and follow `references/interaction-wizard.md` for every new interactive launch. The launch wizard must include an explicit run-mode choice: foreground or background. `exec` mode is the exception: it is fully configured upfront and must not stop for a launch question.
2. **Force full planning for uninitialized repos.** If root `AGENTS.md` or `.agent-os/project-index.md` is missing, treat the repo as uninitialized and force `Mode: plan`. Do not continue, resume, or launch directly from an uninitialized repo.
3. **Run environment detection before first initialization and recovery.** Under the root wrapper, initialization/adoption and recovery/resume must run an `env-bootstrap` readiness check first. Ordinary already-initialized iteration does not require repeated environment probes unless symptoms suggest environment drift.
4. **Respect the chosen run mode after launch approval.** In interactive modes, once the user says "go" (or equivalent: "start", "launch", or any clear approval), follow the selected run mode exactly. Foreground stays in the current session and must not call `autoresearch_runtime_ctl.py launch`. Background calls `autoresearch_runtime_ctl.py launch`, creating the confirmed launch manifest and detached runtime as a single script-level action. Detached sessions use the confirmed launch manifest's `execution_policy`; this skill defaults to sandboxed `workspace_write` unless the user explicitly asks for `danger_full_access`. If the chosen background path is a fresh start after recovery analysis, use `autoresearch_runtime_ctl.py launch --fresh-start` so stale persistent run-control artifacts are archived automatically. `exec` mode has no launch question; once safety checks pass, it begins immediately.
5. **Never ask after the user approves the run.** Once the user has approved `go` in either foreground or background mode, do not pause mid-run to ask anything -- not for clarification, not for confirmation, not for permission. If you encounter ambiguity during the loop, apply best practices and keep going. The user may be asleep.
6. Read all in-scope files before the first write.
7. One focused change per iteration.
8. Mechanical verification only.
9. Git adoption, dirty-worktree handling, branch/worktree strategy, `.gitignore` policy, staging, and round-level auto-commit decisions belong to `../git-runtime-governor/SKILL.md`. Do not apply legacy blanket git rules from memory when that module should decide.
10. Every completed iteration must route to `git-runtime-governor` after verification and any guard handling, but before keep/discard/blocker resolution is written. The governor stages and commits all in-policy changes for the managed repo set.
11. Never stage or revert unrelated user changes.
12. If git policy is unresolved for a repo or artifact category, default to conservative ignore until `git-runtime-governor` records an explicit policy in `.agent-os/autoresearch-config.md`.
13. Use the rollback strategy approved during setup. In a dedicated experiment branch/worktree with pre-launch approval, `git reset --hard HEAD~1` is allowed; otherwise use `git revert --no-edit HEAD`.
14. Discard gains under 1% that add disproportionate complexity.
15. Unlimited runs by default unless the user explicitly asks for `Iterations: N`.
16. External ship actions (deploy, publish, release) must be confirmed during the pre-launch wizard phase. If not confirmed before launch, skip them and log as blocker.
17. Do not ask "should I continue?". Once launched, keep the chosen run mode active until interrupted or a hard blocker / configured terminal condition appears (see `references/autonomous-loop-protocol.md` Stop Conditions for the full definition).
18. During active execution, keep `references/runtime-hard-invariants.md` as the primary runtime checklist. Foreground's core persistent artifacts are `research-results.tsv` and `autoresearch-state.json`; lessons are helper-derived secondary output.
19. When stuck (3+ consecutive discards), use the PIVOT/REFINE escalation ladder from `references/pivot-protocol.md` instead of brute-force retrying.
20. Prefer the bundled helper scripts over hand-editing `research-results.tsv`, `autoresearch-state.json`, or runtime-control files. Always call them via the skill-bundle path (`<skill-root>/scripts/...`); never call bare `scripts/autoresearch_*.py` from the target repo root unless the skill bundle itself is actually installed there.
21. In `exec` mode, never leave repo-root `autoresearch-state.json` behind. If helper scripts need state, use the exec scratch path and explicitly clean it up before exit. When you use `autoresearch_init_run.py --mode exec ...` with the default repo-root artifact names, do not manually rename old `research-results.tsv` or `autoresearch-state.json`; the helper already archives them to the canonical `research-results.prev.tsv` and `autoresearch-state.prev.json` paths before it starts fresh.
22. After any context compaction event (the CLI warns about thread length and compaction), re-read `references/runtime-hard-invariants.md`, `references/core-principles.md`, and the selected mode workflow from disk before the next iteration. Do not rely on memory of those documents after compaction.
23. Every 10 iterations, perform the Protocol Fingerprint Check defined in `references/runtime-hard-invariants.md`. Use Phase 8.7 of `references/autonomous-loop-protocol.md` only for the detailed re-anchoring procedure. If any item fails, re-read all loaded runtime docs from disk before continuing.
24. Whenever material state changes occur, synchronize the project document system as well as the runtime artifacts.

## Structured Output

Every mode should follow `references/structured-output-spec.md`.

Minimum requirement:

- for interactive and user-facing modes, print a setup summary before the loop starts,
- for interactive and user-facing modes, print progress updates during the loop,
- for interactive and user-facing modes, print a completion summary at the end,
- for `exec`, emit only the machine-readable JSON payloads defined in `references/exec-workflow.md`,
- write the mode-specific output files when the workflow defines an output directory.

## Quick Start

```text
$codex-autoresearch
I want to get rid of all the `any` types in my TypeScript code
```

```text
$codex-autoresearch
I want to make our API faster but I don't know where to start
```

```text
$codex-autoresearch
pytest is failing, 12 tests broken after the refactor
```

Codex scans the repo, asks targeted questions to clarify your intent, asks you to choose foreground or background for interactive runs, then starts the loop. You never need to write key-value config.

## References

- `references/core-principles.md`
- `references/runtime-hard-invariants.md`
- `references/loop-workflow.md`
- `references/autonomous-loop-protocol.md`
- `references/interaction-wizard.md`
- `references/structured-output-spec.md`
- `references/modes.md`
- `references/plan-workflow.md`
- `references/debug-workflow.md`
- `references/fix-workflow.md`
- `references/security-workflow.md`
- `references/ship-workflow.md`
- `references/exec-workflow.md`
- `references/results-logging.md`
- `references/lessons-protocol.md`
- `references/pivot-protocol.md`
- `references/web-search-protocol.md`
- `references/environment-awareness.md`
- `references/parallel-experiments-protocol.md`
- `references/session-resume-protocol.md`
- `references/health-check-protocol.md`
- `references/hypothesis-perspectives.md`
