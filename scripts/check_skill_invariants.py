#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

from autoresearch_helpers import (
    AutoresearchError,
    default_exec_state_path,
    improvement,
    log_summary,
    parse_results_log,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate real skill-run artifacts against mode-specific invariants."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    exec_parser = subparsers.add_parser("exec", help="Check exec-mode artifact invariants.")
    exec_parser.add_argument("--repo", required=True)
    exec_parser.add_argument("--last-message-file")
    exec_parser.add_argument("--lessons-sha256")
    exec_parser.add_argument("--expect-prev-results", action="store_true")
    exec_parser.add_argument("--expect-prev-state", action="store_true")
    exec_parser.add_argument("--expect-improvement", action="store_true")

    interactive_parser = subparsers.add_parser(
        "interactive", help="Check iterating-mode artifacts after a manual smoke run."
    )
    interactive_parser.add_argument("--repo", required=True)
    interactive_parser.add_argument("--verify-cmd", required=True)
    interactive_parser.add_argument("--expect-improvement", action="store_true")

    return parser.parse_args()


def validate_exec(repo: Path, args: argparse.Namespace) -> None:
    results_path = repo / "research-results.tsv"
    prev_results_path = repo / "research-results.prev.tsv"
    state_path = repo / "autoresearch-state.json"
    prev_state_path = repo / "autoresearch-state.prev.json"
    lessons_path = repo / "autoresearch-lessons.md"
    scratch_state_path = default_exec_state_path(repo)

    if not results_path.exists():
        raise AutoresearchError("exec run did not produce research-results.tsv")

    parsed = parse_results_log(results_path)
    direction = parsed.metadata.get("metric_direction")
    if direction not in {"lower", "higher"}:
        raise AutoresearchError("results log is missing a valid metric direction comment")
    summary = log_summary(parsed, direction)

    if summary["main_rows"] < 2:
        raise AutoresearchError("exec run did not record any main iteration beyond baseline")
    if args.expect_improvement and not improvement(
        summary["current_metric"], summary["baseline_metric"], direction
    ):
        raise AutoresearchError(
            "exec fixture did not improve the retained metric over the baseline"
        )
    if args.expect_prev_results and not prev_results_path.exists():
        raise AutoresearchError("exec run did not archive the prior research-results.tsv file")
    if args.expect_prev_state and not prev_state_path.exists():
        raise AutoresearchError("exec run did not archive the prior autoresearch-state.json file")
    if state_path.exists():
        raise AutoresearchError("exec run unexpectedly created autoresearch-state.json")
    if scratch_state_path.exists():
        raise AutoresearchError(
            f"exec run left scratch JSON state behind: {scratch_state_path}"
        )
    if args.lessons_sha256:
        if not lessons_path.exists():
            raise AutoresearchError("expected autoresearch-lessons.md to remain present")
        if sha256_file(lessons_path) != args.lessons_sha256:
            raise AutoresearchError("exec run modified autoresearch-lessons.md")
    if args.last_message_file:
        last_message_path = Path(args.last_message_file)
        if not last_message_path.exists():
            raise AutoresearchError("missing --output-last-message file from codex exec")
        if not last_message_path.read_text(encoding="utf-8").strip():
            raise AutoresearchError("last message file is empty")

    print("exec invariants: OK")


def validate_interactive(repo: Path, args: argparse.Namespace) -> None:
    results_path = repo / "research-results.tsv"
    state_path = repo / "autoresearch-state.json"
    lessons_path = repo / "autoresearch-lessons.md"

    if not results_path.exists():
        raise AutoresearchError("interactive run did not produce research-results.tsv")
    if not state_path.exists():
        raise AutoresearchError("interactive run did not produce autoresearch-state.json")
    if not lessons_path.exists():
        raise AutoresearchError("interactive run did not produce autoresearch-lessons.md")

    parsed = parse_results_log(results_path)
    direction = parsed.metadata.get("metric_direction")
    if direction not in {"lower", "higher"}:
        raise AutoresearchError("results log is missing a valid metric direction comment")
    summary = log_summary(parsed, direction)
    if summary["main_rows"] < 2:
        raise AutoresearchError("interactive run did not record any main iteration beyond baseline")
    if args.expect_improvement and not improvement(
        summary["current_metric"], summary["baseline_metric"], direction
    ):
        raise AutoresearchError(
            "interactive fixture did not improve the retained metric over the baseline"
        )
    if not lessons_path.read_text(encoding="utf-8").strip():
        raise AutoresearchError("interactive run left autoresearch-lessons.md empty")

    completed = subprocess.run(
        args.verify_cmd,
        cwd=repo,
        shell=True,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AutoresearchError(
            "interactive verify command still fails:\n"
            + (completed.stdout + completed.stderr).strip()
        )

    print("interactive invariants: OK")


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    if not repo.exists():
        raise AutoresearchError(f"repo does not exist: {repo}")

    if args.mode == "exec":
        validate_exec(repo, args)
    else:
        validate_interactive(repo, args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutoresearchError as exc:
        raise SystemExit(f"error: {exc}")
