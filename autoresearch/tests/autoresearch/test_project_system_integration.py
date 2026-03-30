from __future__ import annotations

import tempfile
from pathlib import Path

from .base import AutoresearchScriptsTestBase


class AutoresearchProjectSystemIntegrationTest(AutoresearchScriptsTestBase):
    maxDiff = None

    def test_init_project_system_creates_unified_autoresearch_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            self.run_script_text("init_project_system.py", str(repo))
            self.run_script_text("validate_project_system.py", str(repo))

            self.assertTrue((repo / "AGENTS.md").exists())
            self.assertTrue((repo / "CLAUDE.md").exists())
            self.assertTrue((repo / ".agent-os" / "project-index.md").exists())
            self.assertTrue((repo / ".agent-os" / "autoresearch-config.md").exists())
            self.assertTrue((repo / ".agent-os" / "autoresearch-runtime.md").exists())

    def test_launch_gate_requires_plan_when_project_system_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            decision = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(repo),
            )

            self.assertEqual(decision["decision"], "needs_human")
            self.assertEqual(decision["reason"], "plan_required")
            self.assertFalse(decision["project_system"]["initialized"])

    def test_init_and_iteration_sync_project_docs_when_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            results_path = repo / "research-results.tsv"
            state_path = repo / "autoresearch-state.json"

            self.init_project_system(repo)

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

            config_text = (repo / ".agent-os" / "autoresearch-config.md").read_text(encoding="utf-8")
            runtime_text = (repo / ".agent-os" / "autoresearch-runtime.md").read_text(encoding="utf-8")
            index_text = (repo / ".agent-os" / "project-index.md").read_text(encoding="utf-8")
            run_log_text = (repo / ".agent-os" / "run-log.md").read_text(encoding="utf-8")
            acceptance_text = (repo / ".agent-os" / "acceptance-report.md").read_text(encoding="utf-8")

            self.assertIn("Reduce failures", config_text)
            self.assertIn("baseline failures", run_log_text)
            self.assertIn("Autoresearch Managed Summary", index_text)
            self.assertIn("Retained metric", runtime_text)
            self.assertIn("baseline", acceptance_text)

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
                "discarded attempt after baseline",
            )

            run_log_text = (repo / ".agent-os" / "run-log.md").read_text(encoding="utf-8")
            acceptance_text = (repo / ".agent-os" / "acceptance-report.md").read_text(encoding="utf-8")
            lessons_text = (repo / ".agent-os" / "lessons-learned.md").read_text(encoding="utf-8")
            runtime_text = (repo / ".agent-os" / "autoresearch-runtime.md").read_text(encoding="utf-8")

            self.assertIn("discarded attempt after baseline", run_log_text)
            self.assertIn("discarded attempt after baseline", lessons_text)
            self.assertIn("last status `discard`".lower(), acceptance_text.lower())
            self.assertIn("Last reconciliation", runtime_text)
