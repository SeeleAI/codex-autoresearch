#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    LESSONS_FILE_NAME,
    default_lessons_path,
    utc_now,
)


HEADER_RE = re.compile(r"^### L-(\d+):\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^- \*\*(Strategy|Outcome|Insight|Context|Iteration|Timestamp):\*\* (.+)$")
FIELD_NAME_MAP = {
    "Strategy": "strategy",
    "Outcome": "outcome",
    "Insight": "insight",
    "Context": "context",
    "Iteration": "iteration",
    "Timestamp": "timestamp",
}
REQUIRED_FIELDS = ("strategy", "outcome", "insight", "context", "iteration", "timestamp")
LESSON_OUTCOMES = ("keep", "discard", "crash", "pivot", "summary")


def lessons_path_from_results(results_path: Path) -> Path:
    return results_path.parent / LESSONS_FILE_NAME


def format_lesson_context(config: dict[str, Any]) -> str:
    goal = str(config.get("goal", "")).strip() or "-"
    scope = str(config.get("scope", "")).strip() or "-"
    metric = str(config.get("metric", "")).strip() or "-"
    direction = str(config.get("direction", "")).strip() or "-"
    return f"goal={goal}; scope={scope}; metric={metric}; direction={direction}"


def format_iteration_ref(run_tag: str | None, iteration: int | str | None) -> str:
    if iteration in {None, ""}:
        return "-"
    iteration_text = str(iteration)
    if run_tag:
        return f"{run_tag}#{iteration_text}"
    return iteration_text


def lesson_title_from_description(description: str) -> str:
    text = " ".join(description.strip().split())
    if not text:
        return "Autoresearch lesson"
    return text[:120]


def fallback_insight(outcome: str, description: str) -> str:
    if description.strip():
        return description.strip()
    if outcome == "keep":
        return "This strategy improved the retained metric and is worth reusing in similar contexts."
    if outcome == "pivot":
        return "This strategy family should be deprioritized in similar contexts."
    return "Capture the main lesson from this iteration."


def parse_lesson_entries(lessons_path: Path) -> list[dict[str, str]]:
    if not lessons_path.exists():
        return []

    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in lessons_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        header = HEADER_RE.match(line)
        if header is not None:
            if current is not None:
                missing = [field for field in REQUIRED_FIELDS if field not in current]
                if missing:
                    raise AutoresearchError(
                        f"Lesson {current['id']} is missing required fields: {', '.join(missing)}"
                    )
                entries.append(current)
            current = {
                "id": f"L-{header.group(1)}",
                "number": header.group(1),
                "title": header.group(2).strip(),
            }
            continue
        if current is None:
            raise AutoresearchError("Lessons file contains content before the first lesson header.")
        field = FIELD_RE.match(line)
        if field is None:
            raise AutoresearchError(f"Unparseable lesson line: {line!r}")
        current[FIELD_NAME_MAP[field.group(1)]] = field.group(2).strip()

    if current is not None:
        missing = [field for field in REQUIRED_FIELDS if field not in current]
        if missing:
            raise AutoresearchError(
                f"Lesson {current['id']} is missing required fields: {', '.join(missing)}"
            )
        entries.append(current)
    return entries


def backup_corrupt_lessons_file(lessons_path: Path) -> Path:
    backup_path = lessons_path.with_name(f"{lessons_path.name}.{utc_now().replace(':', '-')}.bak")
    lessons_path.rename(backup_path)
    return backup_path


def load_entries_for_append(lessons_path: Path) -> list[dict[str, str]]:
    if not lessons_path.exists():
        return []
    try:
        return parse_lesson_entries(lessons_path)
    except AutoresearchError:
        backup_corrupt_lessons_file(lessons_path)
        return []


def list_entries_with_recovery(lessons_path: Path) -> list[dict[str, str]]:
    return load_entries_for_append(lessons_path)


def append_lesson(
    *,
    lessons_path: Path,
    title: str,
    strategy: str,
    outcome: str,
    insight: str,
    context: str,
    iteration: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    if outcome not in LESSON_OUTCOMES:
        raise AutoresearchError(f"Unsupported lesson outcome: {outcome}")

    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    entries = load_entries_for_append(lessons_path)
    next_number = len(entries) + 1
    content = lessons_path.read_text(encoding="utf-8") if lessons_path.exists() else ""
    if content and not content.endswith("\n"):
        content += "\n"
    if content:
        content += "\n"
    content += "\n".join(
        [
            f"### L-{next_number}: {title.strip()}",
            f"- **Strategy:** {strategy.strip()}",
            f"- **Outcome:** {outcome}",
            f"- **Insight:** {insight.strip()}",
            f"- **Context:** {context.strip()}",
            f"- **Iteration:** {iteration.strip() or '-'}",
            f"- **Timestamp:** {(timestamp or utc_now()).strip()}",
            "",
        ]
    )
    lessons_path.write_text(content, encoding="utf-8")
    return {
        "lessons_path": str(lessons_path),
        "id": f"L-{next_number}",
        "title": title.strip(),
        "outcome": outcome,
        "iteration": iteration.strip() or "-",
    }


def append_iteration_lesson(
    *,
    lessons_path: Path,
    state_payload: dict[str, Any],
    status: str,
    description: str,
    iteration: int,
) -> dict[str, Any] | None:
    if state_payload.get("mode") == "exec" or status not in {"keep", "pivot"}:
        return None
    config = state_payload.get("config", {})
    return append_lesson(
        lessons_path=lessons_path,
        title=lesson_title_from_description(description),
        strategy=description.strip() or f"{status} iteration {iteration}",
        outcome=status,
        insight=fallback_insight(status, description),
        context=format_lesson_context(config),
        iteration=format_iteration_ref(state_payload.get("run_tag"), iteration),
    )


def parse_iteration_number(iteration_ref: str, run_tag: str | None) -> int | None:
    if not iteration_ref or iteration_ref == "-":
        return None
    if run_tag and iteration_ref.startswith(f"{run_tag}#"):
        suffix = iteration_ref.split("#", 1)[1]
    elif "#" in iteration_ref:
        return None
    else:
        suffix = iteration_ref
    try:
        return int(suffix)
    except ValueError:
        return None


def append_summary_lesson_if_needed(
    *,
    lessons_path: Path,
    state_payload: dict[str, Any],
    current_iteration: int,
) -> dict[str, Any] | None:
    if state_payload.get("mode") == "exec":
        return None

    run_tag = str(state_payload.get("run_tag") or "").strip() or None
    entries = load_entries_for_append(lessons_path)
    if run_tag is None:
        for entry in reversed(entries):
            if entry.get("outcome") == "summary" and entry.get("iteration") == str(current_iteration):
                return None
        entries = []
    for entry in reversed(entries):
        iteration_number = parse_iteration_number(entry.get("iteration", ""), run_tag)
        if iteration_number is None:
            continue
        if current_iteration - iteration_number <= 5:
            return None
        break

    config = state_payload.get("config", {})
    state = state_payload.get("state", {})
    best_metric = state.get("best_metric", state.get("current_metric", "-"))
    best_iteration = state.get("best_iteration", state.get("iteration", current_iteration))
    last_status = state.get("last_status", "-")
    return append_lesson(
        lessons_path=lessons_path,
        title=f"Run summary: {str(config.get('goal', 'Autoresearch run')).strip() or 'Autoresearch run'}",
        strategy="Runtime completion summary",
        outcome="summary",
        insight=(
            f"Best retained metric {best_metric} at iteration {best_iteration}; "
            f"the run ended with status {last_status}."
        ),
        context=format_lesson_context(config),
        iteration=format_iteration_ref(run_tag, current_iteration),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Append or inspect protocol-aligned autoresearch lessons."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    append = subparsers.add_parser("append")
    append.add_argument("--lessons-path", default=str(default_lessons_path()))
    append.add_argument("--title", required=True)
    append.add_argument("--strategy", required=True)
    append.add_argument("--outcome", required=True, choices=LESSON_OUTCOMES)
    append.add_argument("--insight", required=True)
    append.add_argument("--context", required=True)
    append.add_argument("--iteration", required=True)
    append.add_argument("--timestamp")

    show = subparsers.add_parser("list")
    show.add_argument("--lessons-path", default=str(default_lessons_path()))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "append":
        print(
            json.dumps(
                append_lesson(
                    lessons_path=Path(args.lessons_path),
                    title=args.title,
                    strategy=args.strategy,
                    outcome=args.outcome,
                    insight=args.insight,
                    context=args.context,
                    iteration=args.iteration,
                    timestamp=args.timestamp,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "list":
        print(
            json.dumps(
                list_entries_with_recovery(Path(args.lessons_path)),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    raise AutoresearchError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
