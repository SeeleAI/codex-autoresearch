from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .base import AutoresearchScriptsTestBase


class AutoresearchProgressSnapshotTest(AutoresearchScriptsTestBase):
    def resolve_temp_base(self) -> Path:
        candidates: list[Path] = []
        configured = os.environ.get("CODEX_TEST_TMPDIR")
        if configured:
            candidates.append(Path(configured).expanduser())
        candidates.append(Path(__file__).resolve().parents[2] / ".tmp-tests")
        candidates.append(Path(tempfile.gettempdir()).expanduser())

        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                probe = candidate / f".write-probe-{uuid4().hex}"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
                return candidate
            except OSError:
                continue
        raise RuntimeError("Could not find a writable temporary directory for autoresearch tests.")

    @contextmanager
    def make_tempdir(self):
        base = self.resolve_temp_base()
        repo = Path(tempfile.mkdtemp(prefix="tmp-progress-", dir=base))
        try:
            yield str(repo)
        finally:
            shutil.rmtree(repo, ignore_errors=True)

    def script_env(self, repo: Path) -> dict[str, str]:
        env = dict(os.environ)
        temp_root = str(repo.parent)
        env["TMP"] = temp_root
        env["TEMP"] = temp_root
        env["TMPDIR"] = temp_root
        env["CODEX_TEST_TMPDIR"] = temp_root
        return env

    def seed_progress_docs(self, repo: Path) -> None:
        state_dir = repo / ".agent-os"
        (state_dir / "architecture-milestones.md").write_text(
            """# Architecture And Milestones

## Milestones

- `MS-001` `[ready]`: Verified milestone
  - short_label: M1
  - track_progress: true
  - progress_group: RELEASE-1
  - progress_scope: milestone-1
  - evidence_status: verified
  - evidence_ref: EV-001
- `MS-002` `[ready]`: Pending milestone
  - short_label: M2
  - track_progress: true
  - progress_group: RELEASE-1
  - progress_scope: milestone-2
  - evidence_status: pending
  - evidence_ref:
""",
            encoding="utf-8",
        )
        (state_dir / "todo.md").write_text(
            """# TODO

## Backlog

- `TD-001` `[backlog]`: Pending todo
  - short_label: T1
  - track_progress: true
  - progress_group: S1-3
  - progress_scope: todo-1
  - evidence_status: pending
  - evidence_ref:

## Blocked

- `TD-002` `[blocked]`: Blocked todo
  - short_label: T2
  - track_progress: true
  - progress_group: S1-3
  - progress_scope: todo-2
  - evidence_status: pending
  - evidence_ref:

## Verified

- `TD-003` `[verified]`: Verified todo
  - short_label: T3
  - track_progress: true
  - progress_group: S1-3
  - progress_scope: todo-3
  - evidence_status: verified
  - evidence_ref: EV-003
""",
            encoding="utf-8",
        )
        (state_dir / "acceptance-report.md").write_text(
            """# Acceptance Report

## Passed Checks

- `EV-001` related to `TD-003`: Milestone acceptance
  - short_label: S1-3
  - track_progress: true
  - progress_group: S1-3
  - progress_scope: acceptance-1
  - evidence_status: verified
  - evidence_ref: EV-001

## Failed Or Pending Checks

- `EV-002` related to `TD-001`: Pending acceptance
  - short_label: S1-3
  - track_progress: true
  - progress_group: S1-3
  - progress_scope: acceptance-2
  - evidence_status: pending
  - evidence_ref:
""",
            encoding="utf-8",
        )

    def read_snapshot(self, repo: Path) -> dict[str, object]:
        return json.loads((repo / ".agent-os" / "progress-snapshots.json").read_text(encoding="utf-8"))

    def test_init_run_persists_fact_based_progress_snapshot(self) -> None:
        with self.make_tempdir() as tmp:
            repo = Path(tmp)
            env = self.script_env(repo)
            self.run_script_text("init_project_system.py", str(repo), env=env)
            self.run_script_text("validate_project_system.py", str(repo), env=env)
            self.seed_progress_docs(repo)

            result = self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(repo / "research-results.tsv"),
                "--state-path",
                str(repo / "autoresearch-state.json"),
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base123",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            snapshot = self.read_snapshot(repo)["current_snapshot"]
            assert isinstance(snapshot, dict)
            self.assertEqual(snapshot["project"]["verified"], {"current": 3, "total": 7, "delta": 3, "total_delta": 7})
            self.assertEqual(snapshot["project"]["blocked"], {"current": 1, "total": 7, "delta": 1, "total_delta": 7})
            self.assertEqual(snapshot["project"]["evidence_gap"], {"current": 4, "total": 7, "delta": 4, "total_delta": 7})
            self.assertEqual(snapshot["acceptance_groups"]["verified"]["current"], 1)
            self.assertEqual(len(self.read_snapshot(repo)["history"]), 1)
            self.assertIsNotNone(result["progress_snapshot"])

            project_index = (repo / ".agent-os" / "project-index.md").read_text(encoding="utf-8")
            self.assertIn("## Progress Snapshot", project_index)
            self.assertIn("PROJECT 3/7 (+3)", project_index)

    def test_progress_snapshot_tracks_delta_history_and_stall_alerts(self) -> None:
        with self.make_tempdir() as tmp:
            repo = Path(tmp)
            env = self.script_env(repo)
            self.run_script_text("init_project_system.py", str(repo), env=env)
            self.run_script_text("validate_project_system.py", str(repo), env=env)
            self.seed_progress_docs(repo)

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(repo / "research-results.tsv"),
                "--state-path",
                str(repo / "autoresearch-state.json"),
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base123",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            todo_path = repo / ".agent-os" / "todo.md"
            todo_path.write_text(
                todo_path.read_text(encoding="utf-8").replace(
                    "- `TD-001` `[backlog]`: Pending todo\n  - short_label: T1\n  - track_progress: true\n  - progress_group: S1-3\n  - progress_scope: todo-1\n  - evidence_status: pending\n  - evidence_ref:",
                    "- `TD-001` `[verified]`: Pending todo\n  - short_label: T1\n  - track_progress: true\n  - progress_group: S1-3\n  - progress_scope: todo-1\n  - evidence_status: verified\n  - evidence_ref: EV-004",
                ),
                encoding="utf-8",
            )

            first = self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(repo / "research-results.tsv"),
                "--state-path",
                str(repo / "autoresearch-state.json"),
                "--status",
                "keep",
                "--metric",
                "9",
                "--commit",
                "keep111",
                "--description",
                "verified one more item",
                env=env,
            )
            first_snapshot = first["progress_snapshot"]
            self.assertEqual(first_snapshot["project"]["verified"]["current"], 4)
            self.assertEqual(first_snapshot["project"]["verified"]["delta"], 1)
            self.assertEqual(first_snapshot["history"]["project_verified"], [3, 4])
            self.assertEqual(first_snapshot["history"]["verified_total"], [7, 7])

            for idx in range(2, 5):
                self.run_script(
                    "autoresearch_record_iteration.py",
                    "--results-path",
                    str(repo / "research-results.tsv"),
                    "--state-path",
                    str(repo / "autoresearch-state.json"),
                    "--status",
                    "discard",
                    "--metric",
                    str(9 + idx),
                    "--commit",
                    f"disc{idx}",
                    "--description",
                    f"no numeric progress {idx}",
                    env=env,
                )

            snapshot_payload = self.read_snapshot(repo)
            current_snapshot = snapshot_payload["current_snapshot"]
            assert isinstance(current_snapshot, dict)
            alert_codes = {entry["code"] for entry in current_snapshot["alerts"]}
            self.assertIn("STALL", alert_codes)
            self.assertIn("EVIDENCE_GAP", alert_codes)
            self.assertEqual(len(snapshot_payload["history"]), 5)

    def test_status_uses_nested_initialized_project_root_inside_outer_git_repo(self) -> None:
        with self.make_tempdir() as tmp:
            outer = Path(tmp)
            env = self.script_env(outer)
            (outer / ".git").mkdir()

            repo = outer / "nested-project"
            repo.mkdir(parents=True)
            self.run_script_text("init_project_system.py", str(repo), env=env)
            self.run_script_text("validate_project_system.py", str(repo), env=env)
            self.seed_progress_docs(repo)

            init_result = self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(repo / "research-results.tsv"),
                "--state-path",
                str(repo / "autoresearch-state.json"),
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base123",
                "--baseline-description",
                "baseline failures",
                env=env,
            )
            self.assertEqual(init_result["progress_snapshot_status"], "persisted")

            status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--results-path",
                str(repo / "research-results.tsv"),
                "--state-path",
                str(repo / "autoresearch-state.json"),
                cwd=outer,
                env=env,
            )

            self.assertEqual(status["progress_snapshot_status"], "calculated")
            self.assertIsNotNone(status["progress_snapshot"])
            self.assertEqual(
                Path(status["runtime_path"]).resolve(),
                (repo / "autoresearch-runtime.json").resolve(),
            )
            self.assertEqual(
                Path(status["progress_snapshot"]["project_root"]).resolve(),
                repo.resolve(),
            )

    def test_runtime_status_calculates_snapshot_without_appending_history(self) -> None:
        with self.make_tempdir() as tmp:
            repo = Path(tmp)
            env = self.script_env(repo)
            self.run_script_text("init_project_system.py", str(repo), env=env)
            self.run_script_text("validate_project_system.py", str(repo), env=env)
            self.seed_progress_docs(repo)

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(repo / "research-results.tsv"),
                "--state-path",
                str(repo / "autoresearch-state.json"),
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base123",
                "--baseline-description",
                "baseline failures",
                env=env,
            )

            initial_history_len = len(self.read_snapshot(repo)["history"])
            first_status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--repo",
                str(repo),
                env=env,
            )
            second_status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--repo",
                str(repo),
                env=env,
            )

            self.assertEqual(first_status["progress_snapshot_status"], "calculated")
            self.assertEqual(second_status["progress_snapshot_status"], "calculated")
            self.assertEqual(len(self.read_snapshot(repo)["history"]), initial_history_len)

    def test_missing_progress_group_fails_snapshot_generation(self) -> None:
        with self.make_tempdir() as tmp:
            repo = Path(tmp)
            env = self.script_env(repo)
            self.run_script_text("init_project_system.py", str(repo), env=env)
            self.run_script_text("validate_project_system.py", str(repo), env=env)
            (repo / ".agent-os" / "architecture-milestones.md").write_text(
                """# Architecture And Milestones

## Milestones

- `MS-001` `[ready]`: Verified milestone
  - short_label: M1
  - track_progress: true
  - progress_scope: milestone-1
  - evidence_status: verified
  - evidence_ref: EV-001
""",
                encoding="utf-8",
            )
            (repo / ".agent-os" / "todo.md").write_text(
                """# TODO

## Verified

- `TD-001` `[verified]`: Verified todo
  - short_label: T1
  - track_progress: true
  - progress_group: G1
  - progress_scope: todo-1
  - evidence_status: verified
  - evidence_ref: EV-002
""",
                encoding="utf-8",
            )
            (repo / ".agent-os" / "acceptance-report.md").write_text(
                """# Acceptance Report

## Passed Checks

- `EV-001` related to `TD-001`: Acceptance
  - short_label: G1
  - track_progress: true
  - progress_group: G1
  - progress_scope: acceptance-1
  - evidence_status: verified
  - evidence_ref: EV-001
""",
                encoding="utf-8",
            )

            completed = self.run_script_completed(
                "autoresearch_init_run.py",
                "--results-path",
                str(repo / "research-results.tsv"),
                "--state-path",
                str(repo / "autoresearch-state.json"),
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base123",
                "--baseline-description",
                "baseline failures",
                env=env,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("progress_group", completed.stderr)

    def test_full_progress_snapshot_flow_regression(self) -> None:
        with self.make_tempdir() as tmp:
            base = Path(tmp)
            env = self.script_env(base)

            project = base / "project"
            self.run_script_text("init_project_system.py", str(project), env=env)
            self.run_script_text("validate_project_system.py", str(project), env=env)
            self.seed_progress_docs(project)

            results_path = project / "research-results.tsv"
            state_path = project / "autoresearch-state.json"

            init_result = self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base123",
                "--baseline-description",
                "baseline failures",
                env=env,
            )
            self.assertEqual(init_result["progress_snapshot_status"], "persisted")

            snapshot_path = project / ".agent-os" / "progress-snapshots.json"
            self.assertEqual(len(self.read_snapshot(project)["history"]), 1)

            for _ in range(2):
                status = self.run_script(
                    "autoresearch_runtime_ctl.py",
                    "status",
                    "--results-path",
                    str(results_path),
                    "--state-path",
                    str(state_path),
                    cwd=base,
                    env=env,
                )
                self.assertEqual(status["progress_snapshot_status"], "calculated")
                self.assertEqual(
                    Path(status["progress_snapshot"]["project_root"]).resolve(),
                    project.resolve(),
                )
                self.assertEqual(
                    Path(status["runtime_path"]).resolve(),
                    (project / "autoresearch-runtime.json").resolve(),
                )

            self.assertEqual(len(self.read_snapshot(project)["history"]), 1)

            todo_path = project / ".agent-os" / "todo.md"
            todo_path.write_text(
                todo_path.read_text(encoding="utf-8").replace(
                    "- `TD-001` `[backlog]`: Pending todo\n  - short_label: T1\n  - track_progress: true\n  - progress_group: S1-3\n  - progress_scope: todo-1\n  - evidence_status: pending\n  - evidence_ref:",
                    "- `TD-001` `[verified]`: Pending todo\n  - short_label: T1\n  - track_progress: true\n  - progress_group: S1-3\n  - progress_scope: todo-1\n  - evidence_status: verified\n  - evidence_ref: EV-004",
                ),
                encoding="utf-8",
            )

            first = self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "keep",
                "--metric",
                "9",
                "--commit",
                "keep111",
                "--description",
                "verified one more item",
                env=env,
            )
            self.assertEqual(first["progress_snapshot_status"], "persisted")
            self.assertEqual(first["progress_snapshot"]["history"]["project_verified"], [3, 4])

            for idx in range(2, 5):
                self.run_script(
                    "autoresearch_record_iteration.py",
                    "--results-path",
                    str(results_path),
                    "--state-path",
                    str(state_path),
                    "--status",
                    "discard",
                    "--metric",
                    str(9 + idx),
                    "--commit",
                    f"disc{idx}",
                    "--description",
                    f"no numeric progress {idx}",
                    env=env,
                )

            current_snapshot = self.read_snapshot(project)["current_snapshot"]
            assert isinstance(current_snapshot, dict)
            self.assertIn("STALL", {entry["code"] for entry in current_snapshot["alerts"]})
            self.assertEqual(current_snapshot["history"]["project_verified"], [4, 4, 4])

            self.run_script_text("validate_project_system.py", str(project), env=env)

            outer = base / "outer-repo"
            outer.mkdir()
            (outer / ".git").mkdir()
            nested = outer / "nested-project"
            self.run_script_text("init_project_system.py", str(nested), env=env)
            self.seed_progress_docs(nested)

            nested_init = self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(nested / "research-results.tsv"),
                "--state-path",
                str(nested / "autoresearch-state.json"),
                "--mode",
                "loop",
                "--goal",
                "Reduce failures",
                "--scope",
                "src/**/*.py",
                "--metric-name",
                "failure count",
                "--direction",
                "lower",
                "--verify",
                "pytest -q",
                "--baseline-metric",
                "10",
                "--baseline-commit",
                "base123",
                "--baseline-description",
                "baseline failures",
                cwd=outer,
                env=env,
            )
            self.assertEqual(nested_init["progress_snapshot_status"], "persisted")

            nested_status = self.run_script(
                "autoresearch_runtime_ctl.py",
                "status",
                "--results-path",
                str(nested / "research-results.tsv"),
                "--state-path",
                str(nested / "autoresearch-state.json"),
                cwd=outer,
                env=env,
            )
            self.assertEqual(nested_status["progress_snapshot_status"], "calculated")
            self.assertEqual(
                Path(nested_status["progress_snapshot"]["project_root"]).resolve(),
                nested.resolve(),
            )
            self.assertEqual(
                Path(nested_status["runtime_path"]).resolve(),
                (nested / "autoresearch-runtime.json").resolve(),
            )
            self.assertEqual(nested_status["reason"], "fresh_start_required")
