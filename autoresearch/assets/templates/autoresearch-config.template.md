# Autoresearch Config

## Run Contract

- Mode: [loop/debug/fix/security/ship/exec]
- Session mode: [foreground/background]
- Goal: [Project-level goal statement]
- Scope: [Primary managed scope]
- Metric: [Mechanical metric name]
- Direction: [lower/higher]
- Verify: [Mechanical verify command]
- Guard: [Optional regression guard]
- Stop condition: [Optional stop condition]
- Iterations: [bounded/unbounded]
- Execution policy: [danger_full_access/workspace_write/etc.]

## Managed Repos

- Primary repo: [path or relative label]
- Companion repos: [none or list]

## Managed Git Policy

<!-- AUTORESEARCH-MANAGED-GIT-POLICY START -->
```json
{
  "allowed_categories": [],
  "auto_commit_enabled": false,
  "branch_strategy": "dedicated_experiment_branch",
  "custom_gitignore_rules": [],
  "managed_repo_paths": [],
  "policy_fingerprint": "unset"
}
```
<!-- AUTORESEARCH-MANAGED-GIT-POLICY END -->

## Autonomous Boundaries

- The agent must keep project documents and runtime artifacts synchronized.
- The agent may continue autonomously after launch until a terminal condition or a true blocker appears.
- Human re-planning is required when the top-level goal, acceptance boundary, hard constraints, non-goals, prohibited directions, or project nature changes.

## Sync Discipline

- Update `.agent-os/project-index.md` when the current truth or top next action changes.
- Update `.agent-os/run-log.md` at the end of each meaningful autonomous work session.
- Update `.agent-os/acceptance-report.md` when new evidence is produced.
- Update `.agent-os/lessons-learned.md` when a failed exploration materially affects future strategy.
