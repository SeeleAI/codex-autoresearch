from __future__ import annotations

import argparse
from pathlib import Path


MANAGED_BLOCK_START = "# BEGIN AUTORESEARCH GIT RUNTIME GOVERNOR"
MANAGED_BLOCK_END = "# END AUTORESEARCH GIT RUNTIME GOVERNOR"

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

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
