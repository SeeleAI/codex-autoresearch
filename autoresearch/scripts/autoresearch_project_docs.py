#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import hashlib
import json
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    default_launch_manifest_path,
    default_runtime_log_path,
    default_runtime_state_path,
    default_state_path,
    parse_results_log,
    read_runtime_payload,
    require_consistent_state,
    resolve_state_path_for_log,
    results_repo_root,
)
from autoresearch_progress_snapshot import persist_progress_snapshot, render_progress_snapshot_lines


STATE_DIR_NAME = ".agent-os"
AGENTS_FILE = "AGENTS.md"
CLAUDE_FILE = "CLAUDE.md"
MANAGED_SECTION_START = "<!-- AUTORESEARCH-MANAGED START -->"
MANAGED_SECTION_END = "<!-- AUTORESEARCH-MANAGED END -->"
CORE_STATE_FILES = {
    "project-index.md",
    "requirements.md",
    "change-decisions.md",
    "architecture-milestones.md",
    "todo.md",
    "acceptance-report.md",
    "lessons-learned.md",
    "run-log.md",
}
AUTORESEARCH_STATE_FILES = {
    "autoresearch-config.md",
    "autoresearch-runtime.md",
    "progress-snapshots.json",
}
REQUIRED_PROJECT_STATE_FILES = CORE_STATE_FILES | AUTORESEARCH_STATE_FILES
RUN_LOG_PATH = "run-log.md"
ACCEPTANCE_REPORT_PATH = "acceptance-report.md"
LESSONS_LEARNED_PATH = "lessons-learned.md"
PROJECT_INDEX_PATH = "project-index.md"
AUTORESEARCH_CONFIG_PATH = "autoresearch-config.md"
AUTORESEARCH_RUNTIME_PATH = "autoresearch-runtime.md"
PROGRESS_SNAPSHOT_PATH = "progress-snapshots.json"
ARCHITECTURE_PATH = "architecture-milestones.md"
ID_PATTERN = re.compile(r"\b([A-Z]{2,4})-(\d{3,})\b")
MANAGED_GIT_POLICY_START = "<!-- AUTORESEARCH-MANAGED-GIT-POLICY START -->"
MANAGED_GIT_POLICY_END = "<!-- AUTORESEARCH-MANAGED-GIT-POLICY END -->"
DEFAULT_BRANCH_STRATEGY = "dedicated_experiment_branch"
DEFAULT_GIT_POLICY = {
    "auto_commit_enabled": False,
    "policy_fingerprint": "unset",
    "allowed_categories": [],
    "custom_gitignore_rules": [],
    "branch_strategy": DEFAULT_BRANCH_STRATEGY,
    "managed_repo_paths": [],
}


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def templates_root() -> Path:
    return skill_root() / "assets" / "templates"


def project_state_dir(project_root: Path, state_dir: str = STATE_DIR_NAME) -> Path:
    return project_root / state_dir


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def project_system_status(project_root: Path, state_dir: str = STATE_DIR_NAME) -> dict[str, Any]:
    state_path = project_state_dir(project_root, state_dir)
    agents_path = project_root / AGENTS_FILE
    claude_path = project_root / CLAUDE_FILE
    missing_root: list[str] = []
    missing_files: list[str] = []
    same_file = False
    files_aligned = False

    if not agents_path.exists():
        missing_root.append(AGENTS_FILE)
    if not claude_path.exists():
        missing_root.append(CLAUDE_FILE)
    if not state_path.exists():
        missing_root.append(state_dir)
    else:
        for name in sorted(REQUIRED_PROJECT_STATE_FILES):
            if not (state_path / name).exists():
                missing_files.append(name)

    if agents_path.exists() and claude_path.exists():
        files_aligned, same_file = files_match(agents_path, claude_path)

    initialized = not missing_root and not missing_files and files_aligned
    return {
        "initialized": initialized,
        "project_root": str(project_root),
        "state_dir": str(state_path),
        "missing_root": missing_root,
        "missing_files": missing_files,
        "claude_samefile": same_file,
        "claude_matches_agents": files_aligned,
    }


def require_project_system(project_root: Path, state_dir: str = STATE_DIR_NAME) -> dict[str, Any]:
    status = project_system_status(project_root, state_dir)
    if status["initialized"]:
        return status
    missing_bits = list(status["missing_root"]) + list(status["missing_files"])
    raise AutoresearchError(
        "Unified project system is not initialized. Missing: " + ", ".join(missing_bits)
    )


def load_template(name: str) -> str:
    return read_text(templates_root() / name)


def upsert_managed_block(path: Path, body: str) -> None:
    text = read_text(path) if path.exists() else ""
    block = f"{MANAGED_SECTION_START}\n{body.rstrip()}\n{MANAGED_SECTION_END}\n"
    if MANAGED_SECTION_START in text and MANAGED_SECTION_END in text:
        pattern = re.compile(
            re.escape(MANAGED_SECTION_START) + r".*?" + re.escape(MANAGED_SECTION_END) + r"\n?",
            re.DOTALL,
        )
        updated = pattern.sub(lambda _: block, text, count=1)
    else:
        updated = text.rstrip() + ("\n\n" if text.strip() else "") + block
    write_text(path, updated)


def append_section_entry(path: Path, heading: str, entry: str) -> None:
    text = read_text(path) if path.exists() else ""
    stripped_entry = entry.rstrip()
    if stripped_entry in text:
        return
    if heading in text:
        index = text.index(heading) + len(heading)
        updated = text[:index] + "\n\n" + stripped_entry + text[index:]
    else:
        updated = text.rstrip() + ("\n\n" if text.strip() else "") + heading + "\n\n" + stripped_entry + "\n"
    write_text(path, updated)


def ensure_initial_item_ids(project_root: Path, state_dir: str = STATE_DIR_NAME) -> None:
    state_path = project_state_dir(project_root, state_dir)
    for path in state_path.glob("*.md"):
        text = read_text(path)
        if ID_PATTERN.search(text):
            continue
        stem = path.name
        if stem == PROJECT_INDEX_PATH:
            continue
        write_text(path, text.rstrip() + "\n\n- `TD-001`: bootstrap placeholder\n")


def _normalize_string_list(values: Any) -> list[str]:
    if values in (None, "", []):
        return []
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, list):
        raw_values = values
    else:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _policy_fingerprint(policy: dict[str, Any]) -> str:
    serializable = {
        "auto_commit_enabled": bool(policy.get("auto_commit_enabled", False)),
        "allowed_categories": _normalize_string_list(policy.get("allowed_categories")),
        "custom_gitignore_rules": _normalize_string_list(policy.get("custom_gitignore_rules")),
        "branch_strategy": str(policy.get("branch_strategy") or DEFAULT_BRANCH_STRATEGY),
        "managed_repo_paths": _normalize_string_list(policy.get("managed_repo_paths")),
    }
    digest = hashlib.sha256(
        json.dumps(serializable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest[:12]


def normalize_managed_git_policy(config: dict[str, Any] | None, *, project_root: Path) -> dict[str, Any]:
    config = dict(config or {})
    raw_policy = config.get("git_policy")
    policy = dict(DEFAULT_GIT_POLICY)
    if isinstance(raw_policy, dict):
        policy.update(raw_policy)
    explicit_fingerprint = ""
    if isinstance(raw_policy, dict):
        raw_fingerprint = raw_policy.get("policy_fingerprint")
        if isinstance(raw_fingerprint, str):
            explicit_fingerprint = raw_fingerprint.strip()

    repos = config.get("repos")
    managed_repo_paths = []
    if isinstance(repos, list):
        for entry in repos:
            if not isinstance(entry, dict):
                continue
            raw_path = entry.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue
            managed_repo_paths.append(str(Path(raw_path).resolve()))
    if not managed_repo_paths:
        managed_repo_paths = [str(project_root.resolve())]

    policy["auto_commit_enabled"] = bool(policy.get("auto_commit_enabled", False))
    policy["allowed_categories"] = _normalize_string_list(policy.get("allowed_categories"))
    policy["custom_gitignore_rules"] = _normalize_string_list(policy.get("custom_gitignore_rules"))
    policy["branch_strategy"] = str(policy.get("branch_strategy") or DEFAULT_BRANCH_STRATEGY)
    policy["managed_repo_paths"] = _normalize_string_list(policy.get("managed_repo_paths")) or managed_repo_paths
    policy["policy_fingerprint"] = explicit_fingerprint or _policy_fingerprint(policy)
    return policy


def render_autoresearch_config(config: dict[str, Any], *, mode: str, project_root: Path) -> str:
    repos = config.get("repos", [])
    companion = [f"- Companion repo: `{repo['path']}` :: `{repo['scope']}`" for repo in repos[1:]]
    iterations = config.get("iterations")
    git_policy = normalize_managed_git_policy(config, project_root=project_root)
    return "\n".join(
        [
            "# Autoresearch Config",
            "",
            "## Run Contract",
            "",
            f"- Mode: `{mode}`",
            f"- Session mode: `{config.get('session_mode', 'foreground')}`",
            f"- Goal: {config.get('goal', '')}",
            f"- Scope: `{config.get('scope', '')}`",
            f"- Metric: `{config.get('metric', '')}`",
            f"- Direction: `{config.get('direction', '')}`",
            f"- Verify: `{config.get('verify', '')}`",
            f"- Guard: `{config.get('guard') or 'none'}`",
            f"- Stop condition: `{config.get('stop_condition') or 'none'}`",
            f"- Iterations: `{iterations if iterations is not None else 'unbounded'}`",
            f"- Execution policy: `{config.get('execution_policy', 'foreground-managed')}`",
            "",
            "## Managed Repos",
            "",
            f"- Primary repo: `{project_root}`",
            *(companion or ["- Companion repos: none"]),
            "",
            "## Managed Git Policy",
            "",
            MANAGED_GIT_POLICY_START,
            "```json",
            json.dumps(git_policy, indent=2, sort_keys=True),
            "```",
            MANAGED_GIT_POLICY_END,
            "",
            "## Autonomous Boundaries",
            "",
            "- The agent must keep the project documents and runtime artifacts synchronized.",
            "- Explicit continue commands resume from documents first, then runtime artifacts.",
            "- Minor direction changes update documents and continue.",
            "- Major goal or boundary changes require re-planning before execution.",
            "",
            "## Sync Discipline",
            "",
            "- Update `project-index.md` when current truth or top next action changes.",
            "- Update `run-log.md` at the end of each meaningful autonomous work session.",
            "- Update `acceptance-report.md` whenever new evidence is produced.",
            "- Update `lessons-learned.md` when a failed exploration materially affects future strategy.",
        ]
    ) + "\n"


def render_autoresearch_runtime(
    *,
    config: dict[str, Any],
    state_payload: dict[str, Any],
    runtime_payload: dict[str, Any] | None,
    launch_path: Path,
    results_path: Path,
    state_path: Path,
    runtime_path: Path,
    runtime_log_path: Path,
    reconcile_summary: str,
    progress_lines: list[str],
) -> str:
    runtime_status = runtime_payload.get("status", "idle") if runtime_payload else "idle"
    terminal_reason = runtime_payload.get("terminal_reason", "none") if runtime_payload else "none"
    return "\n".join(
        [
            "# Autoresearch Runtime",
            "",
            "## Runtime Overview",
            "",
            f"- Session mode: `{config.get('session_mode', 'foreground')}`",
            f"- Runtime status: `{runtime_status}`",
            f"- Terminal reason: `{terminal_reason}`",
            "- Recovery order: `AGENTS.md` -> `.agent-os/project-index.md` -> active items -> `.agent-os/run-log.md`",
            f"- Last reconciliation: {reconcile_summary}",
            "",
            "## Current Run Pointers",
            "",
            f"- Launch manifest: `{launch_path if launch_path.exists() else 'none'}`",
            f"- Results log: `{results_path}`",
            f"- State JSON: `{state_path}`",
            f"- Runtime JSON: `{runtime_path if runtime_path.exists() else 'none'}`",
            f"- Runtime log: `{runtime_log_path if runtime_log_path.exists() else 'none'}`",
            "",
            "## Current Metric Snapshot",
            "",
            f"- Baseline metric: `{state_payload['state']['baseline_metric']}`",
            f"- Retained metric: `{state_payload['state']['current_metric']}`",
            f"- Best metric: `{state_payload['state']['best_metric']}` at iteration `{state_payload['state']['best_iteration']}`",
            f"- Last status: `{state_payload['state']['last_status']}`",
            "",
            "## Continue Policy",
            "",
            "- Explicit continue commands such as `continue`, `继续`, `接着干`, or `auto` should resume directly.",
            "- Minor direction changes should update documents and continue.",
            "- Major goal or boundary changes should trigger re-planning.",
            "",
            "## Reconciliation Policy",
            "",
            "- Project documents are the primary semantic truth.",
            "- Runtime artifacts are the primary execution evidence and control-plane source.",
            "- Numeric progress truth lives in `.agent-os/progress-snapshots.json`; this section is a rendered mirror.",
            "- Reconcile before resume. Auto-repair minor drift. Escalate major conflicts for human judgment.",
            "",
            *progress_lines,
        ]
    ) + "\n"


def sync_project_docs(
    *,
    results_path: Path,
    state_path_arg: str | None = None,
    event_kind: str,
    event_summary: str,
    state_dir: str = STATE_DIR_NAME,
) -> dict[str, Any]:
    repo = results_repo_root(results_path)
    status = require_project_system(repo, state_dir)
    parsed = parse_results_log(results_path)
    state_path = resolve_state_path_for_log(state_path_arg, parsed, cwd=repo)
    parsed, state_payload, _, _ = require_consistent_state(results_path, state_path, parsed=parsed)
    runtime_path = default_runtime_state_path(repo)
    launch_path = default_launch_manifest_path(repo)
    runtime_log_path = default_runtime_log_path(repo)
    runtime_payload = read_runtime_payload(runtime_path) if runtime_path.exists() else None
    state_path_dir = project_state_dir(repo, state_dir)

    state_config = dict(state_payload.get("config", {}))
    state_config["git_policy"] = normalize_managed_git_policy(state_config, project_root=repo)
    state_payload["config"] = state_config
    config_text = render_autoresearch_config(state_config, mode=state_payload.get("mode", "loop"), project_root=repo)
    write_text(state_path_dir / AUTORESEARCH_CONFIG_PATH, config_text)

    progress_payload = persist_progress_snapshot(
        results_path=results_path,
        state_path_arg=str(state_path),
    )
    progress_snapshot = progress_payload["current_snapshot"]
    progress_lines = render_progress_snapshot_lines(progress_snapshot)

    reconcile_summary = f"{state_payload.get('updated_at', 'unknown')} :: {event_kind} :: {event_summary}"
    runtime_text = render_autoresearch_runtime(
        config=state_payload.get("config", {}),
        state_payload=state_payload,
        runtime_payload=runtime_payload,
        launch_path=launch_path,
        results_path=results_path,
        state_path=state_path,
        runtime_path=runtime_path,
        runtime_log_path=runtime_log_path,
        reconcile_summary=reconcile_summary,
        progress_lines=progress_lines,
    )
    write_text(state_path_dir / AUTORESEARCH_RUNTIME_PATH, runtime_text)

    upsert_managed_block(
        state_path_dir / PROJECT_INDEX_PATH,
        "\n".join(
            [
                "## Autoresearch Managed Summary",
                "",
                f"- Goal: {state_payload.get('config', {}).get('goal', '')}",
                f"- Session mode: `{state_payload.get('config', {}).get('session_mode', 'foreground')}`",
                f"- Runtime status: `{runtime_payload.get('status', 'idle') if runtime_payload else 'idle'}`",
                f"- Retained metric: `{state_payload['state']['current_metric']}`",
                f"- Last status: `{state_payload['state']['last_status']}`",
                f"- Results path: `{results_path}`",
                f"- Progress snapshot truth: `{state_path_dir / PROGRESS_SNAPSHOT_PATH}`",
                "",
                *progress_lines,
            ]
        ),
    )

    run_log_entry = "\n".join(
        [
            f"- `{state_payload.get('updated_at', 'unknown')}` `{event_kind}`: {event_summary}",
            f"  Evidence: `{results_path}` and `{state_path}`",
            f"  Next likely action: continue from iteration `{state_payload['state']['iteration']}` unless a higher-priority human decision appears.",
        ]
    )
    append_section_entry(state_path_dir / RUN_LOG_PATH, "## Recent Entries", run_log_entry)

    acceptance_entry = "\n".join(
        [
            f"- `{state_payload.get('updated_at', 'unknown')}` `{event_kind}`",
            f"  Result: retained metric `{state_payload['state']['current_metric']}`, last status `{state_payload['state']['last_status']}`.",
            f"  Evidence: `{results_path}` and `{state_path}`.",
        ]
    )
    append_section_entry(state_path_dir / ACCEPTANCE_REPORT_PATH, "## Autoresearch Evidence", acceptance_entry)

    if event_kind in {"discard", "crash", "blocked", "pivot", "refine", "search"}:
        lesson_entry = "\n".join(
            [
                f"- `{state_payload.get('updated_at', 'unknown')}` `{event_kind}`",
                f"  Observation: {event_summary}",
                "  Retry condition: resume only if the next hypothesis changes the causal path or removes the blocker.",
            ]
        )
        append_section_entry(state_path_dir / LESSONS_LEARNED_PATH, "## Project-Level Autoresearch Lessons", lesson_entry)

    return {
        "project_root": str(repo),
        "state_dir": status["state_dir"],
        "results_path": str(results_path),
        "state_path": str(state_path),
        "progress_snapshot_path": str(state_path_dir / PROGRESS_SNAPSHOT_PATH),
        "progress_snapshot": progress_snapshot,
    }
