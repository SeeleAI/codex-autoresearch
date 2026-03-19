# Session Resume Protocol

Detect and recover from interrupted runs. Resume from the last consistent retained state instead of guessing from stale artifacts.

## JSON State File

The primary recovery source is `autoresearch-state.json`, an atomic-write snapshot updated after each main iteration. Schema:

```json
{
  "version": 1,
  "run_tag": "<run-tag>",
  "mode": "loop",
  "config": {
    "goal": "<goal text>",
    "scope": "<glob pattern>",
    "metric": "<metric name>",
    "direction": "lower | higher",
    "verify": "<verify command>",
    "guard": "<guard command or null>"
  },
  "state": {
    "iteration": 15,
    "baseline_metric": 47,
    "best_metric": 28,
    "best_iteration": 12,
    "current_metric": 28,
    "last_commit": "a1b2c3d",
    "last_trial_commit": "d4e5f6a",
    "last_trial_metric": 31,
    "keeps": 8,
    "discards": 5,
    "crashes": 1,
    "no_ops": 0,
    "blocked": 0,
    "consecutive_discards": 2,
    "pivot_count": 0,
    "last_status": "discard"
  },
  "updated_at": "2026-03-19T08:15:32Z"
}
```

Write protocol: write to `autoresearch-state.json.tmp`, then rename to `autoresearch-state.json` (atomic). Never commit this file to git.

## Detection Signals

At the start of every invocation, check for prior run artifacts in this order:

| Priority | Signal | File / Command | Weight |
|----------|--------|---------------|--------|
| 1 | **JSON state** | `autoresearch-state.json` exists and is valid JSON with `version` field | **primary** |
| 2 | Results log | `research-results.tsv` exists and has a baseline row | strong |
| 3 | Lessons file | `autoresearch-lessons.md` exists | moderate |
| 4 | Git history | Recent commits with `experiment:` prefix | moderate |
| 5 | Output dirs | `debug/`, `fix/`, `security/`, `ship/` directories with timestamped subdirectories | weak |

If none of these signals are present, proceed with a fresh run (normal wizard flow).

## Helper Script

Prefer the bundled helper script over ad hoc TSV/JSON parsing:

```bash
python3 scripts/autoresearch_resume_check.py
```

It reconstructs retained state from the TSV, tolerates parallel worker rows, and returns one of four decisions:

- `full_resume`
- `mini_wizard`
- `tsv_fallback`
- `fresh_start`

Use `--write-repaired-state` when TSV recovery is valid and you want to rewrite `autoresearch-state.json` before resuming.

## Recovery Priority Matrix

| # | Condition | Decision |
|---|-----------|----------|
| 1 | JSON valid + helper reports `full_resume` | **Full resume** (skip wizard) |
| 2 | JSON valid + helper reports `mini_wizard` | **Mini-wizard** (1 round) |
| 3 | JSON missing or unusable + helper reports `tsv_fallback` | **TSV fallback** |
| 4 | Helper reports `fresh_start` | **Fresh start** |

### Priority 1: Full Resume

When the helper reports `full_resume`:

1. Restore loop variables from the JSON `state` and `config`.
2. Print a resume banner:
   ```
   Resuming from iteration {state.iteration}, retained metric: {state.current_metric}, best metric: {state.best_metric}.
   {state.keeps} kept, {state.discards} discarded, {state.crashes} crashed so far.
   Source: autoresearch-state.json (validated against TSV main rows)
   ```
3. Skip the wizard entirely.
4. Read the lessons file if present.
5. Run the verify command once as a sanity check.
6. If the current metric drifted, log a `drift` row and continue from the recalibrated state.

### Priority 2: Mini-Wizard

When JSON exists but the helper reports `mini_wizard`:

1. Show what was detected:
   - prior run tag, iteration count, retained metric, and last status from JSON,
   - the helper's mismatch reasons (for example retained-metric mismatch, missing main iteration row, or stale counters).
2. Ask exactly one question:
   - resume from JSON state, or
   - start fresh and archive old artifacts.
3. If resuming, use JSON `config` as the authoritative config and re-confirm it in a single block.
4. If starting fresh, rename prior artifacts with `.prev` suffixes and proceed with the full wizard.

### Priority 3: TSV Fallback

When JSON is missing or unusable but the helper reports `tsv_fallback`:

1. Reconstruct retained state from integer main rows in `research-results.tsv`.
2. If the user wants to resume, prefer:
   ```bash
   python3 scripts/autoresearch_resume_check.py --write-repaired-state
   ```
3. Present one condensed confirmation block sourced from the reconstructed state.
4. After confirmation, continue from the next main iteration.

### Priority 4: Fresh Start

When the helper reports `fresh_start`:

1. Proceed with the normal wizard flow.
2. Rename prior `research-results.tsv` / `autoresearch-state.json` files to `.prev` variants if they exist.
3. Keep `autoresearch-lessons.md` unless it is clearly corrupt.

## Edge Cases

### Corrupt JSON

If `autoresearch-state.json` exists but is not valid JSON, treat it as unusable. Rename to `.bak` if you need to preserve it, then rely on TSV fallback or fresh start.

### Corrupt Results Log

If `research-results.tsv` is missing a baseline row, has a broken header, or contains unparsable metric cells, treat it as corrupt and start fresh.

### Different Goal

If the recovered config clearly belongs to a different goal than the current request, start fresh and rename the old artifacts to `.prev`.

## Integration Points

- **autonomous-loop-protocol.md:** Run the resume helper before the full wizard. Initialize new run artifacts only after baseline is measured.
- **results-logging.md:** Main integer rows define retained state; worker rows are audit detail only.
- **interaction-wizard.md:** Mini-wizard uses helper mismatch reasons instead of raw row counts.
- **health-check-protocol.md:** Deep integrity checks use the resume helper, not row-count heuristics.
- **exec-workflow.md:** Exec mode skips session resume, archives prior persistent artifacts, and cleans up its scratch JSON state before exit.
