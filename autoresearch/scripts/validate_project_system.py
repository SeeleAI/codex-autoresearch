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

from autoresearch_progress_snapshot import parse_markdown_items
from autoresearch_project_docs import (
    ARCHITECTURE_PATH,
    DECOMPOSITION_MODE_CHOICES,
    PLANNING_STRATEGY_CHOICES,
    PLANNING_STRATEGY_MODULAR,
)


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
MANAGED_GIT_POLICY_START = "<!-- AUTORESEARCH-MANAGED-GIT-POLICY START -->"
MANAGED_GIT_POLICY_END = "<!-- AUTORESEARCH-MANAGED-GIT-POLICY END -->"
PLANNING_STRATEGY_RE = re.compile(r"^\s*-\s+Planning strategy:\s*`([^`]+)`\s*$", re.MULTILINE)
TRANSITION_RULE_RE = re.compile(r"^\s*-\s+Transition rule:\s*`([^`]+)`\s*$", re.MULTILINE)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def files_match(path_a: Path, path_b: Path) -> tuple[bool, bool]:
    same_file = False
    try:
        same_file = os.path.samefile(path_a, path_b)
    except OSError:
        same_file = False
    if same_file:
        return True, True
    try:
        return read_text(path_a) == read_text(path_b), False
    except OSError:
        return False, False


def validate_link(agents_path: Path, claude_path: Path) -> list[str]:
    problems: list[str] = []
    if not agents_path.exists():
        problems.append("Missing root AGENTS.md")
    if not claude_path.exists():
        problems.append("Missing root CLAUDE.md")
    if problems:
        return problems
    matches, same_file = files_match(agents_path, claude_path)
    if not matches:
        problems.append("CLAUDE.md does not match AGENTS.md")
    elif not same_file:
        print("[WARN] CLAUDE.md is a content-matched copy of AGENTS.md, not a hard link")
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
    selected_strategy: str | None = None
    if config_path.exists():
        text = read_text(config_path)
        if "## Run Contract" not in text:
            problems.append("autoresearch-config.md does not declare a Run Contract section")
        if "## Managed Git Policy" not in text:
            problems.append("autoresearch-config.md does not declare a Managed Git Policy section")
        if "## Planning Strategy" not in text:
            problems.append("autoresearch-config.md does not declare a Planning Strategy section")
        else:
            strategy_match = PLANNING_STRATEGY_RE.search(text)
            if strategy_match is None:
                problems.append("autoresearch-config.md is missing a Planning strategy line")
            else:
                selected_strategy = strategy_match.group(1).strip()
                if selected_strategy not in PLANNING_STRATEGY_CHOICES:
                    problems.append(
                        "autoresearch-config.md planning strategy must be one of: "
                        + ", ".join(PLANNING_STRATEGY_CHOICES)
                    )
            if TRANSITION_RULE_RE.search(text) is None:
                problems.append("autoresearch-config.md is missing a planning strategy transition rule")
        if MANAGED_GIT_POLICY_START not in text or MANAGED_GIT_POLICY_END not in text:
            problems.append("autoresearch-config.md is missing the managed git policy marker block")
        else:
            block = text.split(MANAGED_GIT_POLICY_START, 1)[1].split(MANAGED_GIT_POLICY_END, 1)[0]
            match = re.search(r"```json\s*(\{.*?\})\s*```", block, re.DOTALL)
            if match is None:
                problems.append("autoresearch-config.md managed git policy block is not valid JSON markdown")
            else:
                try:
                    payload = json.loads(match.group(1))
                except json.JSONDecodeError as exc:
                    problems.append(f"autoresearch-config.md managed git policy JSON is invalid: {exc}")
                else:
                    if not isinstance(payload, dict):
                        problems.append("autoresearch-config.md managed git policy JSON must be an object")
                    elif "policy_fingerprint" not in payload:
                        problems.append("autoresearch-config.md managed git policy JSON is missing policy_fingerprint")
    if runtime_path.exists():
        text = read_text(runtime_path)
        if "## Runtime Overview" not in text:
            problems.append("autoresearch-runtime.md does not declare a Runtime Overview section")
        if "## Runtime Overview" in text and "Runtime status:" in text and "progress-snapshots.json" not in text:
            problems.append("autoresearch-runtime.md does not reference progress-snapshots.json as numeric progress truth")
        if "Selected planning strategy:" not in text:
            problems.append("autoresearch-runtime.md does not expose the selected planning strategy")
        if "Effective planning strategy:" not in text:
            problems.append("autoresearch-runtime.md does not expose the effective planning strategy")
    snapshot_path = state_dir / "progress-snapshots.json"
    if snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"progress-snapshots.json is not valid JSON: {exc}")
        else:
            if "current_snapshot" not in payload or "history" not in payload:
                problems.append("progress-snapshots.json must contain current_snapshot and history")

    decomposition_problems = validate_decomposition_modes(
        state_dir=state_dir,
        selected_strategy=selected_strategy,
    )
    problems.extend(decomposition_problems)
    return problems


def validate_decomposition_modes(
    *,
    state_dir: Path,
    selected_strategy: str | None,
) -> list[str]:
    problems: list[str] = []
    offenders: list[str] = []
    for relative_name, item_type in (
        (ARCHITECTURE_PATH, "milestone"),
        ("todo.md", "todo"),
    ):
        path = state_dir / relative_name
        if not path.exists():
            continue
        for item in parse_markdown_items(path, item_type=item_type):
            if item_type == "milestone" and not (
                item.item_id.startswith("MS-") or item.section.strip().lower() == "milestones"
            ):
                continue
            if item_type == "todo" and not item.item_id.startswith("TD-"):
                continue
            if not item.item_id:
                continue
            mode = item.decomposition_mode.strip().lower()
            if not mode:
                problems.append(f"{relative_name} item {item.item_id} is missing decomposition_mode")
                continue
            if mode not in DECOMPOSITION_MODE_CHOICES:
                problems.append(
                    f"{relative_name} item {item.item_id} has invalid decomposition_mode {mode!r}"
                )
                continue
            if selected_strategy == PLANNING_STRATEGY_MODULAR and mode == "combined":
                offenders.append(f"{item.item_id} ({relative_name})")
    if offenders:
        problems.append(
            "modular_final_path forbids combined milestones/todos: " + ", ".join(offenders)
        )
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
