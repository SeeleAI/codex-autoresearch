---
name: autoresearch-internal-skill-creator
description: Create and maintain internal skill modules inside the codex-autoresearch repository. Use when Codex needs to scaffold a new internal module under this repo, wire it into the root or internal protocol documents, or rebuild INTERNAL-MODULES.md after any skill change in this repository.
---

# Autoresearch Internal Skill Creator

Use this visible skill to govern internal modules for `codex-autoresearch`.

When this skill mentions `<skill-root>`, it means the directory containing this `SKILL.md`. When it mentions `<repo-root>`, it means the parent directory of this skill folder.

## Required Rules

- Internal modules keep `SKILL.md` as their entry file.
- Internal modules create `scripts/`, `references/`, and `assets/`.
- Internal modules never expose `agents/openai.yaml`.
- After any change to a skill or internal module in this repository, run `sync` mode so `INTERNAL-MODULES.md` and the internal module maps stay aligned with the repository.

## Modes

### `create`

Use `create` to scaffold a new internal module and immediately rebuild the registry.

Required inputs:

- module name
- module type: `root-routing`, `engine-protocol`, `environment-collaboration`, or `shared-tooling`
- responsibility summary
- primary caller: `codex-autoresearch`, `autoresearch`, or `env-bootstrap`

```powershell
python <skill-root>/scripts/manage_internal_modules.py create <name> --module-type <type> --summary "<summary>" --primary-caller <caller>
```

### `sync`

Use `sync` after any repository change that touches a visible skill, internal module, or module wiring.

```powershell
python <skill-root>/scripts/manage_internal_modules.py sync
```

`sync` performs a full rebuild of `INTERNAL-MODULES.md`, refreshes the generated module maps in the root and internal protocol files, and reports structural changes such as added or removed modules.
