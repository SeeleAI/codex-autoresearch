#!/usr/bin/env python3
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoresearch_helpers import (
    AutoresearchError,
    log_summary,
    parse_results_log,
    read_json,
    read_runtime_payload,
    read_state_payload,
    resolve_state_path_for_log,
    results_repo_root,
    write_json_atomic,
)


STATE_DIR_NAME = ".agent-os"
SNAPSHOT_FILE_NAME = "progress-snapshots.json"
SNAPSHOT_LOCK_FILE_NAME = "progress-snapshots.lock"
MAX_HISTORY = 10
STALL_REPORT_WINDOW = 3
STALL_ITERATION_WINDOW = 3
ALERT_CODES = ("STALL", "REGRESS", "SCOPE_UP", "SCOPE_DOWN", "EVIDENCE_GAP")
TRACKING_FIELD_RE = re.compile(
    r"^\s*-\s+(short_label|track_progress|progress_group|progress_scope|evidence_status|evidence_ref|decomposition_mode):\s*(.*)$"
)
ITEM_RE = re.compile(r"^\s*-\s+`(?P<id>[A-Z]{2,4}-\d{3,})`\s+`\[(?P<status>[^\]]+)\]`:\s*(?P<title>.*)$")
ACCEPTANCE_RE = re.compile(
    r"^\s*-\s+`(?P<id>[A-Z]{2,4}-\d{3,})`(?:\s+related to\s+`(?P<related>[A-Z]{2,4}-\d{3,})`)?\s*:\s*(?P<title>.*)$"
)
RECENT_ENTRY_RE = re.compile(r"^\s*-\s+`(?P<timestamp>[^`]+)`\s+`(?P<kind>[^`]+)`:\s*(?P<summary>.*)$")


@dataclass
class ProgressItem:
    item_id: str
    item_type: str
    status: str
    title: str
    section: str
    short_label: str
    track_progress: bool
    progress_group: str
    progress_scope: str
    evidence_status: str
    evidence_ref: str
    decomposition_mode: str

    @property
    def verified(self) -> bool:
        return (
            self.track_progress
            and self.evidence_status == "verified"
            and bool(self.evidence_ref)
        )

    @property
    def evidence_gap(self) -> bool:
        return self.track_progress and not self.verified

    @property
    def blocked(self) -> bool:
        return self.track_progress and self.status == "blocked"


def project_state_dir(project_root: Path) -> Path:
    return project_root / STATE_DIR_NAME


def snapshot_path(project_root: Path) -> Path:
    return project_state_dir(project_root) / SNAPSHOT_FILE_NAME


def snapshot_lock_path(project_root: Path) -> Path:
    return project_state_dir(project_root) / SNAPSHOT_LOCK_FILE_NAME


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def read_snapshot_history(project_root: Path) -> dict[str, Any]:
    path = snapshot_path(project_root)
    if not path.exists():
        return {"current_snapshot": None, "history": []}
    payload = read_json(path)
    history = payload.get("history")
    current = payload.get("current_snapshot")
    if not isinstance(history, list):
        raise AutoresearchError("Progress snapshot history must be a list.")
    return {
        "current_snapshot": current if isinstance(current, dict) else None,
        "history": [entry for entry in history if isinstance(entry, dict)],
    }


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"true", "yes", "1", "y"}


def parse_markdown_items(path: Path, *, item_type: str) -> list[ProgressItem]:
    lines = read_text(path).splitlines()
    items: list[ProgressItem] = []
    current_section = ""
    current_item: ProgressItem | None = None

    for raw_line in lines:
        heading_match = re.match(r"^##\s+(.*)$", raw_line)
        if heading_match:
            current_section = heading_match.group(1).strip()
            current_item = None
            continue

        item_match = ITEM_RE.match(raw_line) if item_type != "acceptance" else ACCEPTANCE_RE.match(raw_line)
        if item_match:
            groups = item_match.groupdict()
            status = str(groups.get("status") or current_section).strip().lower().replace(" ", "_")
            current_item = ProgressItem(
                item_id=str(groups["id"]),
                item_type=item_type,
                status=status,
                title=str(groups.get("title") or "").strip(),
                section=current_section,
                short_label="",
                track_progress=False,
                progress_group="",
                progress_scope="",
                evidence_status="",
                evidence_ref="",
                decomposition_mode="",
            )
            items.append(current_item)
            continue

        field_match = TRACKING_FIELD_RE.match(raw_line)
        if field_match and current_item is not None:
            key = field_match.group(1)
            value = field_match.group(2).strip()
            if key == "track_progress":
                current_item.track_progress = parse_bool(value)
            elif key == "short_label":
                current_item.short_label = value
            elif key == "progress_group":
                current_item.progress_group = value
            elif key == "progress_scope":
                current_item.progress_scope = value
            elif key == "evidence_status":
                current_item.evidence_status = value.strip().lower()
            elif key == "evidence_ref":
                current_item.evidence_ref = value
            elif key == "decomposition_mode":
                current_item.decomposition_mode = value.strip().lower()
            continue

        if raw_line.strip() and not raw_line.startswith(" "):
            current_item = None

    return items


def require_trackable_fields(items: list[ProgressItem]) -> None:
    missing: list[str] = []
    for item in items:
        if not item.track_progress:
            continue
        for field_name in ("short_label", "progress_group", "progress_scope", "evidence_status"):
            if not getattr(item, field_name):
                missing.append(f"{item.item_id}:{field_name}")
    if missing:
        raise AutoresearchError(
            "Trackable progress items are missing required fields: " + ", ".join(sorted(missing))
        )


def count_blocked(items: list[ProgressItem]) -> int:
    return sum(1 for item in items if item.blocked)


def summarize_items(items: list[ProgressItem]) -> dict[str, Any]:
    trackable = [item for item in items if item.track_progress]
    verified = [item for item in trackable if item.verified]
    evidence_gap = [item for item in trackable if item.evidence_gap]
    blocked = [item for item in trackable if item.blocked]
    return {
        "total": len(trackable),
        "verified": len(verified),
        "unverified": len(trackable) - len(verified),
        "blocked": len(blocked),
        "evidence_gap": len(evidence_gap),
    }


def summarize_by_group(items: list[ProgressItem]) -> list[dict[str, Any]]:
    grouped: dict[str, list[ProgressItem]] = {}
    for item in items:
        if not item.track_progress or not item.progress_group:
            continue
        grouped.setdefault(item.progress_group, []).append(item)
    output: list[dict[str, Any]] = []
    for group_name in sorted(grouped):
        group_items = grouped[group_name]
        output.append(
            {
                "group": group_name,
                "short_label": group_items[0].short_label or group_name,
                "verified": sum(1 for item in group_items if item.verified),
                "total": len(group_items),
                "blocked": sum(1 for item in group_items if item.blocked),
                "evidence_gap": sum(1 for item in group_items if item.evidence_gap),
                "evidence_ids": sorted(
                    {
                        item.evidence_ref
                        for item in group_items
                        if item.evidence_ref
                    }
                ),
            }
        )
    return output


def item_snapshot(items: list[ProgressItem]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in items:
        if not item.track_progress:
            continue
        output.append(
            {
                "id": item.item_id,
                "short_label": item.short_label,
                "status": item.status,
                "progress_group": item.progress_group,
                "progress_scope": item.progress_scope,
                "verified": 1 if item.verified else 0,
                "total": 1,
                "blocked": 1 if item.blocked else 0,
                "evidence_gap": 1 if item.evidence_gap else 0,
                "evidence_ref": item.evidence_ref,
                "evidence_status": item.evidence_status,
                "decomposition_mode": item.decomposition_mode,
            }
        )
    return output


def metric_block(current: int, total: int, previous_current: int | None, previous_total: int | None) -> dict[str, int]:
    return {
        "current": current,
        "total": total,
        "delta": current - (previous_current or 0),
        "total_delta": total - (previous_total or 0),
    }


def build_recent_event_ids(run_log_path: Path, *, limit: int = 3) -> list[str]:
    if not run_log_path.exists():
        return []
    event_ids: list[str] = []
    for line in read_text(run_log_path).splitlines():
        match = RECENT_ENTRY_RE.match(line)
        if not match:
            continue
        event_ids.append(f"{match.group('kind')}@{match.group('timestamp')}")
    return event_ids[-limit:]


def previous_metric(previous_snapshot: dict[str, Any] | None, *path: str) -> tuple[int | None, int | None]:
    current: Any = previous_snapshot or {}
    for key in path:
        if not isinstance(current, dict):
            return None, None
        current = current.get(key)
    if not isinstance(current, dict):
        return None, None
    current_value = current.get("current")
    total_value = current.get("total")
    return (
        int(current_value) if isinstance(current_value, int) else None,
        int(total_value) if isinstance(total_value, int) else None,
    )


def build_trend(history: list[dict[str, Any]], current_snapshot: dict[str, Any]) -> dict[str, list[int]]:
    recent = [entry for entry in history[-2:] if isinstance(entry, dict)] + [current_snapshot]
    return {
        "project_verified": [int(entry["project"]["verified"]["current"]) for entry in recent],
        "verified_total": [int(entry["project"]["verified"]["total"]) for entry in recent],
        "blocked_total": [int(entry["project"]["blocked"]["current"]) for entry in recent],
    }


def report_streak(history: list[dict[str, Any]], verified_now: int) -> int:
    streak = 1
    for snapshot in reversed(history):
        try:
            if int(snapshot["project"]["verified"]["current"]) != verified_now:
                break
        except (KeyError, TypeError, ValueError):
            break
        streak += 1
    return streak


def iteration_streak(
    history: list[dict[str, Any]],
    *,
    verified_now: int,
    current_iteration: int,
) -> int:
    if current_iteration <= 0:
        return 0
    seen_iterations = {current_iteration}
    streak = 1
    for snapshot in reversed(history):
        try:
            if int(snapshot["project"]["verified"]["current"]) != verified_now:
                break
            iteration = int(snapshot.get("iteration", 0))
        except (KeyError, TypeError, ValueError):
            break
        if iteration <= 0 or iteration in seen_iterations:
            continue
        seen_iterations.add(iteration)
        streak += 1
    return streak


def build_alerts(
    *,
    current_snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
    history: list[dict[str, Any]],
    run_log_path: Path,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    current_project = current_snapshot["project"]
    verified_now = int(current_project["verified"]["current"])
    total_now = int(current_project["verified"]["total"])
    evidence_gap_now = int(current_project["evidence_gap"]["current"])
    blocked_now = int(current_project["blocked"]["current"])
    evidence_ids = list(current_snapshot["evidence_ids"])

    if previous_snapshot is not None:
        verified_prev = int(previous_snapshot["project"]["verified"]["current"])
        total_prev = int(previous_snapshot["project"]["verified"]["total"])
        if verified_now < verified_prev:
            alerts.append(
                {
                    "code": "REGRESS",
                    "value": verified_now - verified_prev,
                    "evidence_ids": evidence_ids[:3],
                }
            )
        if total_now > total_prev:
            alerts.append(
                {
                    "code": "SCOPE_UP",
                    "value": total_now - total_prev,
                    "evidence_ids": evidence_ids[:3],
                }
            )
        if total_now < total_prev:
            alerts.append(
                {
                    "code": "SCOPE_DOWN",
                    "value": total_now - total_prev,
                    "evidence_ids": evidence_ids[:3],
                }
            )

    if evidence_gap_now > 0:
        alerts.append(
            {
                "code": "EVIDENCE_GAP",
                "value": evidence_gap_now,
                "evidence_ids": evidence_ids[:3],
            }
        )

    streak_reports = report_streak(history, verified_now)
    streak_iterations = iteration_streak(
        history,
        verified_now=verified_now,
        current_iteration=int(current_snapshot["iteration"]),
    )
    if streak_reports >= STALL_REPORT_WINDOW and streak_iterations >= STALL_ITERATION_WINDOW:
        alerts.append(
            {
                "code": "STALL",
                "value": verified_now,
                "window_reports": streak_reports,
                "window_iterations": streak_iterations,
                "evidence_ids": build_recent_event_ids(run_log_path),
            }
        )

    normalized: list[dict[str, Any]] = []
    for alert in alerts:
        if alert["code"] not in ALERT_CODES:
            continue
        normalized.append(alert)
    return normalized


def build_progress_snapshot(
    *,
    project_root: Path,
    results_path: Path,
    state_path: Path,
    runtime_path: Path | None = None,
    previous_snapshot: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state_dir = project_state_dir(project_root)
    milestones = parse_markdown_items(state_dir / "architecture-milestones.md", item_type="milestone")
    todos = parse_markdown_items(state_dir / "todo.md", item_type="todo")
    acceptance = parse_markdown_items(state_dir / "acceptance-report.md", item_type="acceptance")
    require_trackable_fields(milestones + todos + acceptance)

    state_payload = read_state_payload(state_path)
    parsed = parse_results_log(results_path)
    log_stats = log_summary(parsed, str(state_payload.get("config", {}).get("direction", "lower")))
    runtime_payload = read_runtime_payload(runtime_path) if runtime_path and runtime_path.exists() else None

    project_items = milestones + todos + acceptance
    project_summary = summarize_items(project_items)
    milestone_summary = summarize_items(milestones)
    todo_summary = summarize_items(todos)
    acceptance_summary = summarize_items(acceptance)

    previous_snapshot = previous_snapshot if isinstance(previous_snapshot, dict) else None
    history = [entry for entry in (history or []) if isinstance(entry, dict)]

    current_snapshot: dict[str, Any] = {
        "schema_version": 1,
        "snapshot_id": f"{state_payload.get('updated_at', '')}:{state_payload.get('state', {}).get('iteration', 0)}",
        "project_root": str(project_root),
        "results_path": str(results_path),
        "state_path": str(state_path),
        "runtime_path": str(runtime_path) if runtime_path else "",
        "updated_at": str(state_payload.get("updated_at", "")),
        "iteration": int(state_payload.get("state", {}).get("iteration", 0)),
        "last_status": str(state_payload.get("state", {}).get("last_status", "")),
        "runtime_status": str((runtime_payload or {}).get("status", "idle")),
        "project": {
            "verified": metric_block(
                project_summary["verified"],
                project_summary["total"],
                *previous_metric(previous_snapshot, "project", "verified"),
            ),
            "unverified": metric_block(
                project_summary["unverified"],
                project_summary["total"],
                *previous_metric(previous_snapshot, "project", "unverified"),
            ),
            "blocked": metric_block(
                project_summary["blocked"],
                project_summary["total"],
                *previous_metric(previous_snapshot, "project", "blocked"),
            ),
            "evidence_gap": metric_block(
                project_summary["evidence_gap"],
                project_summary["total"],
                *previous_metric(previous_snapshot, "project", "evidence_gap"),
            ),
            "main_iterations": metric_block(
                int(log_stats["iteration"]),
                int(log_stats["iteration"]),
                *previous_metric(previous_snapshot, "project", "main_iterations"),
            ),
        },
        "milestones": {
            "verified": metric_block(
                milestone_summary["verified"],
                milestone_summary["total"],
                *previous_metric(previous_snapshot, "milestones", "verified"),
            ),
            "blocked": metric_block(
                milestone_summary["blocked"],
                milestone_summary["total"],
                *previous_metric(previous_snapshot, "milestones", "blocked"),
            ),
            "items": item_snapshot(milestones),
        },
        "todos": {
            "verified": metric_block(
                todo_summary["verified"],
                todo_summary["total"],
                *previous_metric(previous_snapshot, "todos", "verified"),
            ),
            "blocked": metric_block(
                todo_summary["blocked"],
                todo_summary["total"],
                *previous_metric(previous_snapshot, "todos", "blocked"),
            ),
            "items": item_snapshot(todos),
        },
        "acceptance_groups": {
            "verified": metric_block(
                acceptance_summary["verified"],
                acceptance_summary["total"],
                *previous_metric(previous_snapshot, "acceptance_groups", "verified"),
            ),
            "blocked": metric_block(
                acceptance_summary["blocked"],
                acceptance_summary["total"],
                *previous_metric(previous_snapshot, "acceptance_groups", "blocked"),
            ),
            "groups": summarize_by_group(acceptance),
        },
        "deltas": {
            "scope_total": metric_block(
                project_summary["total"],
                project_summary["total"],
                *previous_metric(previous_snapshot, "deltas", "scope_total"),
            ),
        },
        "evidence_ids": sorted(
            {
                item.evidence_ref
                for item in project_items
                if item.track_progress and item.evidence_ref
            }
        ),
    }
    current_snapshot["alerts"] = build_alerts(
        current_snapshot=current_snapshot,
        previous_snapshot=previous_snapshot,
        history=history,
        run_log_path=state_dir / "run-log.md",
    )
    current_snapshot["history"] = build_trend(history, current_snapshot)
    return current_snapshot


def calculate_progress_snapshot(
    *,
    results_path: Path,
    state_path_arg: str | None = None,
) -> dict[str, Any]:
    repo = results_repo_root(results_path)
    state_path = resolve_state_path_for_log(state_path_arg, None, cwd=repo)
    runtime_path = repo / "autoresearch-runtime.json"
    existing = read_snapshot_history(repo)
    previous_snapshot = existing["current_snapshot"]
    history = list(existing["history"])
    snapshot = build_progress_snapshot(
        project_root=repo,
        results_path=results_path,
        state_path=state_path,
        runtime_path=runtime_path,
        previous_snapshot=previous_snapshot,
        history=history,
    )
    return {
        "project_root": str(repo),
        "current_snapshot": snapshot,
        "history": history,
    }


def persist_progress_snapshot(
    *,
    results_path: Path,
    state_path_arg: str | None = None,
) -> dict[str, Any]:
    repo = results_repo_root(results_path)
    lock_path = snapshot_lock_path(repo)
    deadline = time.time() + 5.0
    while True:
        try:
            fd = lock_path.open("x", encoding="utf-8")
            fd.write(str(time.time()))
            fd.close()
            break
        except FileExistsError:
            if time.time() >= deadline:
                raise AutoresearchError(f"Timed out acquiring progress snapshot lock: {lock_path}")
            time.sleep(0.05)

    try:
        payload = calculate_progress_snapshot(
            results_path=results_path,
            state_path_arg=state_path_arg,
        )
        history = list(payload["history"])
        snapshot = payload["current_snapshot"]
        updated_history = (history + [snapshot])[-MAX_HISTORY:]
        persisted = {
            "current_snapshot": snapshot,
            "history": updated_history,
        }
        write_json_atomic(snapshot_path(repo), persisted)
        return persisted
    finally:
        lock_path.unlink(missing_ok=True)


def render_progress_snapshot_lines(snapshot: dict[str, Any]) -> list[str]:
    lines = ["## Progress Snapshot", ""]
    lines.append(f"SNAPSHOT {snapshot['snapshot_id']}")
    project = snapshot["project"]
    lines.append(
        f"PROJECT {project['verified']['current']}/{project['verified']['total']} ({project['verified']['delta']:+d})"
    )
    lines.append(
        f"UNVERIFIED {project['unverified']['current']}/{project['unverified']['total']} ({project['unverified']['delta']:+d})"
    )
    lines.append(
        f"BLOCKED {project['blocked']['current']}/{project['blocked']['total']} ({project['blocked']['delta']:+d})"
    )
    lines.append(
        f"EVIDENCE_GAP {project['evidence_gap']['current']}/{project['evidence_gap']['total']} ({project['evidence_gap']['delta']:+d})"
    )
    lines.append(
        f"MILESTONES {snapshot['milestones']['verified']['current']}/{snapshot['milestones']['verified']['total']} ({snapshot['milestones']['verified']['delta']:+d})"
    )
    lines.append(
        f"TODOS {snapshot['todos']['verified']['current']}/{snapshot['todos']['verified']['total']} ({snapshot['todos']['verified']['delta']:+d})"
    )
    lines.append(
        f"ACCEPTANCE {snapshot['acceptance_groups']['verified']['current']}/{snapshot['acceptance_groups']['verified']['total']} ({snapshot['acceptance_groups']['verified']['delta']:+d})"
    )
    lines.append(
        f"SCOPE {snapshot['deltas']['scope_total']['current']}/{snapshot['deltas']['scope_total']['total']} ({snapshot['deltas']['scope_total']['delta']:+d})"
    )
    lines.append(
        "TREND "
        + "/".join(str(value) for value in snapshot["history"]["project_verified"])
        + " "
        + "/".join(str(value) for value in snapshot["history"]["blocked_total"])
    )
    for item in snapshot["milestones"]["items"]:
        lines.append(
            f"MS {item['short_label']} {item['verified']}/{item['total']} ({item['verified']:+d})"
        )
    for item in snapshot["todos"]["items"]:
        lines.append(
            f"TD {item['short_label']} {item['verified']}/{item['total']} ({item['verified']:+d})"
        )
    for group in snapshot["acceptance_groups"]["groups"]:
        lines.append(
            f"AC {group['short_label']} {group['verified']}/{group['total']} ({group['verified']:+d})"
        )
    for alert in snapshot["alerts"]:
        evidence = ",".join(alert.get("evidence_ids", []))
        lines.append(f"ALERT {alert['code']} {alert['value']} {evidence}".rstrip())
    lines.append("")
    return lines


__all__ = [
    "MAX_HISTORY",
    "SNAPSHOT_FILE_NAME",
    "SNAPSHOT_LOCK_FILE_NAME",
    "build_progress_snapshot",
    "calculate_progress_snapshot",
    "persist_progress_snapshot",
    "project_state_dir",
    "read_snapshot_history",
    "render_progress_snapshot_lines",
    "snapshot_path",
]
