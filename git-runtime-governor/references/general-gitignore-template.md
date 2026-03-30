# General Gitignore Template

This is a markdown policy template, not a real `.gitignore`.

`git-runtime-governor` uses this template plus the user's answers to generate the managed block that gets merged into the real `.gitignore`.

## Autoresearch State Files

Typical paths:

- `research-results.tsv`
- `autoresearch-state.json`
- `autoresearch-lessons.md`

Default policy:

- Ask whether each state file should be ignored, tracked always, or tracked only at milestones.

## Runtime Control Files

Typical paths:

- `autoresearch-launch.json`
- `autoresearch-runtime.json`
- `autoresearch-runtime.log`
- `*.prev.json`
- `*.prev.tsv`

Default policy:

- Ignore unless the user explicitly wants these retained in git.

## Logs And Snapshots

Typical paths:

- `logs/`
- `tmp/`
- `.tmp-tests/`
- `progress-snapshots.json`

Default policy:

- Ignore unless the user wants audit snapshots versioned.

## Build Cache And Generated Cache

Typical paths:

- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `dist/`
- `build/`

Default policy:

- Ignore.

## Media Files

Typical patterns:

- `*.gif`
- `*.mp4`
- `*.mov`
- `*.webm`

Default policy:

- Ask whether media is evidence, deliverable, or disposable runtime output.

## Document Files

Typical patterns:

- `*.pdf`
- `*.docx`
- `*.pptx`

Default policy:

- Ask separately from media; many repos want PDFs retained while videos stay ignored.

## Data And Model Artifacts

Typical patterns:

- `*.pt`
- `*.pth`
- `*.ckpt`
- `*.bin`
- `data/`
- `artifacts/`

Default policy:

- Ignore unless the user explicitly wants these preserved in git.

## Custom Extensions

Reserve a policy section for project-specific rules that do not fit the standard categories.
