from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path, PurePosixPath


MANAGED_BLOCK_START = "# BEGIN AUTORESEARCH GIT RUNTIME GOVERNOR"
MANAGED_BLOCK_END = "# END AUTORESEARCH GIT RUNTIME GOVERNOR"
MANAGED_GIT_POLICY_START = "<!-- AUTORESEARCH-MANAGED-GIT-POLICY START -->"
MANAGED_GIT_POLICY_END = "<!-- AUTORESEARCH-MANAGED-GIT-POLICY END -->"
AUTORESEARCH_OWNED_BASENAMES = {
    "research-results.tsv",
    "autoresearch-state.json",
    "autoresearch-launch.json",
    "autoresearch-runtime.json",
    "autoresearch-runtime.log",
    "autoresearch-lessons.md",
    "autoresearch-hook-context.json",
}

CATEGORY_RULES = {
    "autoresearch-state": [
        "research-results.tsv",
        "autoresearch-state.json",
        "autoresearch-lessons.md",
    ],
    "runtime-control": [
        "autoresearch-launch.json",
        "autoresearch-runtime.json",
        "autoresearch-runtime.log",
        "*.prev.json",
        "*.prev.tsv",
    ],
    "logs-snapshots": [
        "logs/",
        "tmp/",
        ".tmp-tests/",
        "progress-snapshots.json",
    ],
    "build-cache": [
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        "dist/",
        "build/",
    ],
    "media-files": [
        "*.gif",
        "*.mp4",
        "*.mov",
        "*.webm",
    ],
    "document-files": [
        "*.pdf",
        "*.docx",
        "*.pptx",
    ],
    "data-model-artifacts": [
        "*.pt",
        "*.pth",
        "*.ckpt",
        "*.bin",
        "data/",
        "artifacts/",
    ],
}


def ordered_unique(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def render_template_markdown() -> str:
    sections = [
        "# General Gitignore Template",
        "",
        "This markdown template defines the standard retention categories for `git-runtime-governor`.",
        "",
    ]
    descriptions = {
        "autoresearch-state": "Autoresearch state files",
        "runtime-control": "Runtime control files",
        "logs-snapshots": "Logs and snapshots",
        "build-cache": "Build and cache output",
        "media-files": "Media files",
        "document-files": "Document files",
        "data-model-artifacts": "Data and model artifacts",
    }
    for category, label in descriptions.items():
        sections.append(f"## {label}")
        sections.append("")
        for rule in CATEGORY_RULES[category]:
            sections.append(f"- `{rule}`")
        sections.append("")
    sections.extend(
        [
            "## Custom Extensions",
            "",
            "- Add project-specific ignore rules here when they do not fit a standard category.",
            "",
        ]
    )
    return "\n".join(sections)


def render_gitignore_block(categories: list[str], custom_rules: list[str]) -> str:
    invalid = sorted(set(categories) - set(CATEGORY_RULES))
    if invalid:
        raise ValueError(f"Unknown categories: {', '.join(invalid)}")
    rules: list[str] = []
    for category in categories:
        rules.extend(CATEGORY_RULES[category])
    rules.extend(custom_rules)
    body = ordered_unique(rules)
    lines = [
        MANAGED_BLOCK_START,
        "# Generated from git-runtime-governor policy categories.",
        *body,
        MANAGED_BLOCK_END,
    ]
    return "\n".join(lines) + "\n"


def merge_gitignore_text(existing: str, managed_block: str) -> str:
    start = existing.find(MANAGED_BLOCK_START)
    end = existing.find(MANAGED_BLOCK_END)
    if start != -1 and end != -1 and end >= start:
        end += len(MANAGED_BLOCK_END)
        updated = existing[:start].rstrip("\n") + "\n\n" + managed_block
        suffix = existing[end:].lstrip("\n")
        if suffix:
            updated += "\n" + suffix
        return updated.rstrip("\n") + "\n"
    if existing.strip():
        return existing.rstrip("\n") + "\n\n" + managed_block
    return managed_block


def build_commit_message(
    *,
    iteration: int,
    mode: str,
    summary: str,
    policy_fingerprint: str,
    categories: list[str],
) -> str:
    first_line = (
        f"autoresearch: iteration {iteration:03d} "
        f"[mode={mode}] [policy={policy_fingerprint}]"
    )
    body = [
        "",
        f"summary: {summary}",
        "categories: " + (", ".join(categories) if categories else "none"),
    ]
    return "\n".join([first_line, *body]) + "\n"


def parse_scope_patterns(scope_text: str | None) -> list[str]:
    if not scope_text:
        return []
    return [token for token in re.split(r"[\s,]+", scope_text.strip()) if token]


def path_is_in_scope(path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False

    normalized = path.replace("\\", "/")
    stripped_path = normalized.lstrip("./")
    candidate = PurePosixPath(stripped_path)
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/").lstrip("./").strip()
        if not normalized_pattern:
            continue
        is_glob = any(marker in normalized_pattern for marker in "*?[")
        base = normalized_pattern.rstrip("/")

        if normalized_pattern.endswith("/") or not is_glob:
            if base and (stripped_path == base or stripped_path.startswith(f"{base}/")):
                return True

        variants = {normalized_pattern}
        while True:
            expanded = {variant.replace("**/", "") for variant in variants if "**/" in variant}
            expanded -= variants
            if not expanded:
                break
            variants |= expanded

        if any(candidate.match(variant) for variant in variants):
            return True

    return False


def is_autoresearch_owned_artifact(path: str | Path) -> bool:
    candidate = Path(path)
    normalized_parts = {part.lower() for part in candidate.parts}
    if candidate.name in {"AGENTS.md", "CLAUDE.md"}:
        return True
    if ".agent-os" in normalized_parts:
        return True
    names = [candidate.name]
    parent_name = candidate.parent.name
    if parent_name and parent_name != ".":
        names.append(parent_name)

    for name in names:
        pending = [name]
        seen = set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            if current in AUTORESEARCH_OWNED_BASENAMES:
                return True
            for base in AUTORESEARCH_OWNED_BASENAMES:
                if current.startswith(f"{base}.") or current.endswith(f".{base}"):
                    return True
            path_name = Path(current)
            suffix = path_name.suffix
            if suffix:
                stem = path_name.stem
                for marker in (".prev", ".bak", ".tmp"):
                    if stem.endswith(marker):
                        pending.append(f"{stem[: -len(marker)]}{suffix}")
            for marker in (".prev", ".bak", ".tmp"):
                if current.endswith(marker):
                    pending.append(current[: -len(marker)])
    return False


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or f"git {' '.join(args)} failed")
    return completed


def git_status_entries(repo: Path) -> list[tuple[str, tuple[str, ...]]]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "-z",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or "git status failed")
    entries = [entry for entry in completed.stdout.split("\0") if entry]
    parsed_entries: list[tuple[str, tuple[str, ...]]] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        status = entry[:2]
        paths = [entry[3:] if len(entry) > 3 else entry]
        if "R" in status or "C" in status:
            if index + 1 < len(entries):
                paths.append(entries[index + 1])
            index += 1
        parsed_entries.append((status, tuple(paths)))
        index += 1
    return parsed_entries


def extract_managed_git_policy(config_text: str) -> dict[str, object]:
    start = config_text.find(MANAGED_GIT_POLICY_START)
    end = config_text.find(MANAGED_GIT_POLICY_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError("Managed git policy block is missing from autoresearch-config.md")
    block = config_text[start + len(MANAGED_GIT_POLICY_START) : end]
    match = re.search(r"```json\s*(\{.*?\})\s*```", block, re.DOTALL)
    if match is None:
        raise ValueError("Managed git policy block does not contain a JSON payload")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("Managed git policy JSON must be an object")
    return payload


def parse_scope_from_config(config_text: str) -> str:
    match = re.search(r"^- Scope:\s*`([^`]+)`", config_text, re.MULTILINE)
    return match.group(1).strip() if match is not None else ""


def path_matches_rule(path: str, rule: str) -> bool:
    return path_is_in_scope(path, [rule])


def collect_in_policy_paths(
    *,
    repo: Path,
    scope_text: str,
    artifact_rules: list[str],
) -> list[str]:
    scope_patterns = parse_scope_patterns(scope_text)
    selected: list[str] = []
    for _, paths in git_status_entries(repo):
        for raw_path in paths:
            normalized = raw_path.replace("\\", "/").lstrip("./")
            if not normalized:
                continue
            if normalized == ".gitignore":
                selected.append(normalized)
                continue
            if is_autoresearch_owned_artifact(normalized):
                continue
            if path_is_in_scope(normalized, scope_patterns) or any(
                path_matches_rule(normalized, rule) for rule in artifact_rules
            ):
                selected.append(normalized)
    return ordered_unique(selected)


def refresh_gitignore(
    *,
    repo: Path,
    categories: list[str],
    custom_rules: list[str],
) -> bool:
    gitignore_path = repo / ".gitignore"
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    merged = merge_gitignore_text(existing, render_gitignore_block(categories, custom_rules))
    if merged == existing:
        return False
    gitignore_path.write_text(merged, encoding="utf-8")
    return True


def governed_commit(
    *,
    repo: Path,
    config_path: Path,
    scope_text: str,
    iteration: int,
    mode: str,
    summary: str,
) -> dict[str, object]:
    config_text = config_path.read_text(encoding="utf-8")
    policy = extract_managed_git_policy(config_text)
    if not bool(policy.get("auto_commit_enabled", False)):
        raise RuntimeError("Managed git policy does not permit auto-commit.")

    managed_paths = [
        str(Path(path).resolve())
        for path in policy.get("managed_repo_paths", [])
        if isinstance(path, str) and path.strip()
    ]
    if managed_paths and str(repo.resolve()) not in managed_paths:
        raise RuntimeError(f"Repo {repo} is not listed in the managed git policy.")

    effective_scope = scope_text.strip() or parse_scope_from_config(config_text)
    if not effective_scope:
        raise RuntimeError("No managed scope is available for governed commit.")

    categories = [
        category
        for category in policy.get("allowed_categories", [])
        if isinstance(category, str) and category.strip()
    ]
    custom_rules = [
        rule
        for rule in policy.get("custom_gitignore_rules", [])
        if isinstance(rule, str) and rule.strip()
    ]
    gitignore_changed = refresh_gitignore(repo=repo, categories=categories, custom_rules=custom_rules)
    artifact_rules: list[str] = []
    for category in categories:
        artifact_rules.extend(CATEGORY_RULES[category])
    artifact_rules.extend(custom_rules)

    selected_paths = collect_in_policy_paths(
        repo=repo,
        scope_text=effective_scope,
        artifact_rules=artifact_rules,
    )
    if gitignore_changed and ".gitignore" not in selected_paths:
        selected_paths.append(".gitignore")
    selected_paths = ordered_unique(selected_paths)
    if not selected_paths:
        raise RuntimeError("No in-policy file changes are available for governed commit.")

    run_git(repo, "add", "--", *selected_paths)
    staged = [
        line.strip()
        for line in run_git(repo, "diff", "--cached", "--name-only").stdout.splitlines()
        if line.strip()
    ]
    if not staged:
        raise RuntimeError("Governed commit produced an empty staged set.")

    message = build_commit_message(
        iteration=iteration,
        mode=mode,
        summary=summary,
        policy_fingerprint=str(policy.get("policy_fingerprint") or "unset"),
        categories=categories,
    )
    run_git(repo, "commit", "-m", message)
    commit = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    return {
        "repo": str(repo),
        "commit": commit,
        "policy_fingerprint": str(policy.get("policy_fingerprint") or "unset"),
        "staged_files": staged,
        "categories": categories,
        "scope": effective_scope,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helper utilities for git-runtime-governor.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("print-template")

    render = subparsers.add_parser("render-gitignore")
    render.add_argument("--category", action="append", default=[])
    render.add_argument("--custom-rule", action="append", default=[])

    merge = subparsers.add_parser("merge-gitignore")
    merge.add_argument("--target", required=True)
    merge.add_argument("--category", action="append", default=[])
    merge.add_argument("--custom-rule", action="append", default=[])

    commit = subparsers.add_parser("commit-message")
    commit.add_argument("--iteration", type=int, required=True)
    commit.add_argument("--mode", required=True)
    commit.add_argument("--summary", required=True)
    commit.add_argument("--policy-fingerprint", required=True)
    commit.add_argument("--category", action="append", default=[])

    governed = subparsers.add_parser("governed-commit")
    governed.add_argument("--repo", required=True)
    governed.add_argument("--config-path")
    governed.add_argument("--scope", required=True)
    governed.add_argument("--iteration", type=int, required=True)
    governed.add_argument("--mode", required=True)
    governed.add_argument("--summary", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "print-template":
        print(render_template_markdown())
        return 0

    if args.command == "render-gitignore":
        print(render_gitignore_block(args.category, args.custom_rule), end="")
        return 0

    if args.command == "merge-gitignore":
        target = Path(args.target)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        merged = merge_gitignore_text(existing, render_gitignore_block(args.category, args.custom_rule))
        target.write_text(merged, encoding="utf-8")
        print(f"Updated {target}")
        return 0

    if args.command == "commit-message":
        print(
            build_commit_message(
                iteration=args.iteration,
                mode=args.mode,
                summary=args.summary,
                policy_fingerprint=args.policy_fingerprint,
                categories=args.category,
            ),
            end="",
        )
        return 0

    if args.command == "governed-commit":
        repo = Path(args.repo).resolve()
        config_path = (
            Path(args.config_path).resolve()
            if args.config_path
            else repo / ".agent-os" / "autoresearch-config.md"
        )
        payload = governed_commit(
            repo=repo,
            config_path=config_path,
            scope_text=args.scope,
            iteration=args.iteration,
            mode=args.mode,
            summary=args.summary,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
