# Autoresearch Runtime

## Runtime Overview

- Session mode: [foreground/background]
- Runtime status: [idle/running/stopped/needs_human]
- Recovery order: `AGENTS.md` -> `.agent-os/project-index.md` -> active items -> `.agent-os/run-log.md`
- Last reconciliation: [timestamp and short summary]

## Current Run Pointers

- Launch manifest: [path or none]
- Results log: [path]
- State JSON: [path]
- Runtime JSON: [path or none]
- Runtime log: [path or none]

## Continue Policy

- Explicit continue commands such as `continue`, `继续`, `接着干`, or `auto` should resume from the current documents and runtime artifacts.
- Minor direction changes should update documents and continue.
- Major goal or boundary changes should trigger re-planning before execution.

## Reconciliation Policy

- Project documents are the primary semantic truth.
- Runtime artifacts are the primary execution evidence and control-plane source.
- Numeric progress truth lives in `.agent-os/progress-snapshots.json`; this section is a rendered mirror.
- Reconcile before resume. Auto-repair minor drift. Escalate major conflicts for human judgment.
