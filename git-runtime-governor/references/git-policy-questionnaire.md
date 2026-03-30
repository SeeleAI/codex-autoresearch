# Git Policy Questionnaire

Use this questionnaire during initialization and first recovery for repos managed by `git-runtime-governor`.

Ask in grouped batches. Do not collapse everything into one question.

## Group 1: Repo Topology And Ownership

- Is the primary workspace already a git repo?
- If not, should autoresearch initialize git here?
- Are there companion repos, and what are their paths and scopes?
- Are existing uncommitted changes user-owned, autoresearch-owned, or mixed?

## Group 2: Branch And Worktree Strategy

- May autoresearch create and use a dedicated experiment branch?
- If the repo already has branch conventions, should autoresearch follow them?
- If the user does not want branch creation, what is the allowed fallback?

## Group 3: Autoresearch And Runtime Artifacts

- Should `research-results.tsv` be ignored, tracked, or tracked only at milestones?
- Should `autoresearch-state.json` be ignored, tracked, or tracked only at milestones?
- Should launch or runtime control files stay ignored by default?
- Should logs and progress snapshots be ignored or retained?

## Group 4: Media, Documents, And Binaries

- Should gif and video outputs be ignored, always tracked, or tracked only in selected categories?
- Should PDF outputs be ignored, always tracked, or tracked only in selected categories?
- Should other binary artifacts follow the same rule as media, or be treated separately?

## Group 5: Data, Cache, And Build Output

- Which cache and build directories should remain ignored?
- Are there data or model outputs that must be preserved in git despite their size or volatility?
- Are there project-specific generated files that need special treatment?

## Group 6: Auto-Commit Policy

- Should every iteration auto-commit on the experiment branch?
- Which file categories are allowed into the per-iteration auto-commit?
- What summary style should the commit message emphasize?
- If a category is not explicitly answered, confirm that the default is conservative ignore.
