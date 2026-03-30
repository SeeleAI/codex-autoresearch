#!/usr/bin/env python3
"""
Validate a project state document system.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


REQUIRED_STATE_FILES = {
    "project-index.md",
    "requirements.md",
    "change-decisions.md",
    "architecture-milestones.md",
    "todo.md",
    "acceptance-report.md",
    "lessons-learned.md",
    "run-log.md",
    "autoresearch-config.md",
    "autoresearch-runtime.md",
    "progress-snapshots.json",
}
ID_PATTERN = re.compile(r"\b([A-Z]{2,4})-(\d{3,})\b")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def validate_link(agents_path: Path, claude_path: Path) -> list[str]:
    problems: list[str] = []
    if not agents_path.exists():
        problems.append("Missing root AGENTS.md")
    if not claude_path.exists():
        problems.append("Missing root CLAUDE.md")
    if problems:
        return problems
    try:
        if not os.path.samefile(agents_path, claude_path):
            problems.append("CLAUDE.md is not the same file as AGENTS.md")
    except OSError as exc:
        problems.append(f"Could not compare AGENTS.md and CLAUDE.md: {exc}")
    return problems


def validate_required_files(state_dir: Path) -> list[str]:
    problems: list[str] = []
    if not state_dir.exists():
        return [f"Missing state directory: {state_dir}"]
    for name in sorted(REQUIRED_STATE_FILES):
        if not (state_dir / name).exists():
            problems.append(f"Missing state file: {name}")
    return problems


def validate_index(index_path: Path) -> list[str]:
    problems: list[str] = []
    if not index_path.exists():
        return problems
    text = read_text(index_path)
    if "Top next action" not in text:
        problems.append("project-index.md does not declare a top next action section")
    if not re.search(r"\bTD-\d{3,}\b", text):
        problems.append("project-index.md does not reference any TODO ID")
    if "Autoresearch Managed Summary" not in text:
        problems.append("project-index.md does not contain the Autoresearch Managed Summary section")
    if "Autoresearch Managed Summary" in text and "Progress snapshot truth" not in text:
        problems.append("project-index.md does not reference the progress snapshot truth path")
    return problems


def validate_autoresearch_docs(state_dir: Path) -> list[str]:
    problems: list[str] = []
    config_path = state_dir / "autoresearch-config.md"
    runtime_path = state_dir / "autoresearch-runtime.md"
    if config_path.exists():
        text = read_text(config_path)
        if "## Run Contract" not in text:
            problems.append("autoresearch-config.md does not declare a Run Contract section")
    if runtime_path.exists():
        text = read_text(runtime_path)
        if "## Runtime Overview" not in text:
            problems.append("autoresearch-runtime.md does not declare a Runtime Overview section")
        if "## Runtime Overview" in text and "Runtime status:" in text and "progress-snapshots.json" not in text:
            problems.append("autoresearch-runtime.md does not reference progress-snapshots.json as numeric progress truth")
    snapshot_path = state_dir / "progress-snapshots.json"
    if snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"progress-snapshots.json is not valid JSON: {exc}")
        else:
            if "current_snapshot" not in payload or "history" not in payload:
                problems.append("progress-snapshots.json must contain current_snapshot and history")
    return problems


def validate_ids(state_dir: Path) -> list[str]:
    problems: list[str] = []
    found_any = False
    for path in state_dir.glob("*.md"):
        text = read_text(path)
        for prefix, number_text in ID_PATTERN.findall(text):
            found_any = True
            item_id = f"{prefix}-{number_text}"
            if not re.fullmatch(r"[A-Z]{2,4}-\d{3,}", item_id):
                problems.append(f"Malformed item ID found: {item_id}")
    if not found_any:
        problems.append("No typed item IDs were found in the state documents")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a project state document system.")
    parser.add_argument("project_root", type=Path, help="Project root to validate.")
    parser.add_argument(
        "--state-dir",
        default=".agent-os",
        help="Relative state directory under the project root.",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    state_dir = project_root / args.state_dir

    problems: list[str] = []
    problems.extend(validate_link(project_root / "AGENTS.md", project_root / "CLAUDE.md"))
    problems.extend(validate_required_files(state_dir))
    problems.extend(validate_index(state_dir / "project-index.md"))
    problems.extend(validate_autoresearch_docs(state_dir))
    problems.extend(validate_ids(state_dir))

    if problems:
        for problem in problems:
            print(f"[ERROR] {problem}")
        return 1

    print("[OK] Project state document system is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
