from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


class AutoresearchScriptsTest(unittest.TestCase):
    maxDiff = None

    def run_script(
        self, script_name: str, *args: str, cwd: Path | None = None
    ) -> dict[str, object]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script_name), *args],
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return json.loads(completed.stdout)

    def run_script_text(
        self, script_name: str, *args: str, cwd: Path | None = None
    ) -> str:
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script_name), *args],
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return completed.stdout.strip()

    def test_init_and_serial_iteration_state_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

            self.run_script(
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "discard",
                "--metric",
                "12",
                "--commit",
                "deadbee",
                "--description",
                "worse attempt",
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "b2c3d4e",
                "--guard",
                "pass",
                "--description",
                "better attempt",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["iteration"], 2)
            self.assertEqual(state["state"]["current_metric"], 8)
            self.assertEqual(state["state"]["best_metric"], 8)
            self.assertEqual(state["state"]["best_iteration"], 2)
            self.assertEqual(state["state"]["keeps"], 1)
            self.assertEqual(state["state"]["discards"], 1)
            self.assertEqual(state["state"]["last_commit"], "b2c3d4e")
            self.assertEqual(state["state"]["last_trial_metric"], 8)

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "full_resume")
            self.assertEqual(resume["tsv_summary"]["iteration"], 2)

    def test_parallel_batch_selects_best_worker_and_appends_main_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"
            batch_path = tmpdir / "batch.json"

            self.run_script(
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                "--parallel-mode",
                "parallel",
            )
            batch_path.write_text(
                json.dumps(
                    [
                        {
                            "worker_id": "a",
                            "commit": "c3d4e5f",
                            "metric": 7,
                            "guard": "pass",
                            "description": "narrowed hot path",
                            "diff_size": 12,
                        },
                        {
                            "worker_id": "b",
                            "commit": "d4e5f6a",
                            "metric": 9,
                            "guard": "pass",
                            "description": "wrapper experiment",
                            "diff_size": 4,
                        },
                        {
                            "worker_id": "c",
                            "status": "crash",
                            "description": "timeout after 20m",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            result = self.run_script(
                "autoresearch_select_parallel_batch.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--batch-file",
                str(batch_path),
            )
            self.assertEqual(result["selected_worker"], "a")
            self.assertEqual(result["status"], "keep")

            log_text = results_path.read_text(encoding="utf-8")
            self.assertIn("1a\tc3d4e5f\t7\t-3\tpass\tkeep", log_text)
            self.assertIn("1b\t-\t9\t-1\tpass\tdiscard", log_text)
            self.assertIn("1c\t-\t10\t0\t-\tcrash", log_text)
            self.assertIn("1\tc3d4e5f\t7\t-3\tpass\tkeep\t[PARALLEL batch] selected worker-a", log_text)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["iteration"], 1)
            self.assertEqual(state["state"]["current_metric"], 7)

    def test_resume_check_can_rebuild_missing_state_from_tsv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

            self.run_script(
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "b2c3d4e",
                "--guard",
                "pass",
                "--description",
                "better attempt",
            )
            state_path.unlink()

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
                "--write-repaired-state",
            )
            self.assertEqual(resume["decision"], "tsv_fallback")
            self.assertTrue(resume["repaired_state"])

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["state"]["iteration"], 1)
            self.assertEqual(state["state"]["current_metric"], 8)

    def test_resume_check_detects_json_tsv_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

            self.run_script(
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["state"]["current_metric"] = 999
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "mini_wizard")
            self.assertTrue(any("current_metric" in reason for reason in resume["reasons"]))

    def test_resume_check_keeps_json_path_when_tsv_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            state_path = tmpdir / "autoresearch-state.json"

            self.run_script(
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
            )
            results_path.unlink()

            resume = self.run_script(
                "autoresearch_resume_check.py",
                "--results-path",
                str(results_path),
                "--state-path",
                str(state_path),
            )
            self.assertEqual(resume["decision"], "mini_wizard")
            self.assertTrue(any("results log is missing" in reason for reason in resume["reasons"]))

    def test_exec_mode_uses_scratch_state_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            results_path = tmpdir / "research-results.tsv"
            repo_state_path = tmpdir / "autoresearch-state.json"
            scratch_state_path = Path(
                self.run_script_text(
                    "autoresearch_exec_state.py",
                    "--repo-root",
                    str(tmpdir),
                )
            )

            self.run_script(
                "autoresearch_init_run.py",
                "--results-path",
                str(results_path),
                "--mode",
                "exec",
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
                "a1b2c3d",
                "--baseline-description",
                "baseline failures",
                cwd=tmpdir,
            )
            self.run_script(
                "autoresearch_record_iteration.py",
                "--results-path",
                str(results_path),
                "--status",
                "keep",
                "--metric",
                "8",
                "--commit",
                "b2c3d4e",
                "--guard",
                "pass",
                "--description",
                "better attempt",
                cwd=tmpdir,
            )

            self.assertFalse(repo_state_path.exists())
            self.assertTrue(scratch_state_path.exists())

            state = json.loads(scratch_state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["mode"], "exec")
            self.assertEqual(state["state"]["iteration"], 1)
            self.assertEqual(state["state"]["current_metric"], 8)

            cleanup = self.run_script(
                "autoresearch_exec_state.py",
                "--repo-root",
                str(tmpdir),
                "--cleanup",
                "--json",
            )
            self.assertTrue(cleanup["removed"])
            self.assertEqual(cleanup["state_path"], str(scratch_state_path))
            self.assertFalse(scratch_state_path.exists())


if __name__ == "__main__":
    unittest.main()
