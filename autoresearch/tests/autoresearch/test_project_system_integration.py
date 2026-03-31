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
            config_text = (repo / ".agent-os" / "autoresearch-config.md").read_text(encoding="utf-8")
            milestones_text = (repo / ".agent-os" / "architecture-milestones.md").read_text(encoding="utf-8")
            todo_text = (repo / ".agent-os" / "todo.md").read_text(encoding="utf-8")
            self.assertIn("## Planning Strategy", config_text)
            self.assertIn("modular_final_path", config_text)
            self.assertIn("decomposition_mode: isolated", milestones_text)
            self.assertIn("decomposition_mode: isolated", todo_text)

    def test_content_matched_claude_copy_is_treated_as_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            self.run_script_text("init_project_system.py", str(repo))
            agents_text = (repo / "AGENTS.md").read_text(encoding="utf-8")
            (repo / "CLAUDE.md").unlink()
            (repo / "CLAUDE.md").write_text(agents_text, encoding="utf-8")

            validation = self.run_script_text("validate_project_system.py", str(repo))
            self.assertIn("Project state document system is valid", validation)

            decision = self.run_script(
                "autoresearch_launch_gate.py",
                "--repo",
                str(repo),
            )
            self.assertNotEqual(decision["reason"], "plan_required")
            self.assertTrue(decision["project_system"]["initialized"])
            self.assertFalse(decision["project_system"]["claude_samefile"])
            self.assertTrue(decision["project_system"]["claude_matches_agents"])

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
                "--planning-strategy",
                "bootstrap_combined_prototype",
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
            self.assertIn("## Managed Git Policy", config_text)
            self.assertIn("bootstrap_combined_prototype", config_text)
            self.assertIn('"auto_commit_enabled": false', config_text)
            self.assertIn("baseline failures", run_log_text)
            self.assertIn("Autoresearch Managed Summary", index_text)
            self.assertIn("Retained metric", runtime_text)
            self.assertIn("Selected planning strategy: `bootstrap_combined_prototype`", runtime_text)
            self.assertIn("Planning strategy: `bootstrap_combined_prototype`", index_text)
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

    def test_validate_project_system_rejects_missing_decomposition_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            self.run_script_text("init_project_system.py", str(repo))
            todo_path = repo / ".agent-os" / "todo.md"
            todo_text = todo_path.read_text(encoding="utf-8").replace(
                "  - decomposition_mode: isolated\n",
                "",
                1,
            )
            todo_path.write_text(todo_text, encoding="utf-8")

            completed = self.run_script_completed("validate_project_system.py", str(repo))
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("missing decomposition_mode", completed.stdout.lower())

    def test_parallel_batch_syncs_project_docs_when_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            results_path = repo / "research-results.tsv"
            state_path = repo / "autoresearch-state.json"
            batch_path = repo / "batch.json"

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
                "--parallel-mode",
                "parallel",
            )
            batch_path.write_text(
                '[{"worker_id":"a","commit":"keep222","metric":7,"guard":"pass","description":"parallel kept improvement"}]',
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

            self.assertEqual(result["progress_snapshot_status"], "persisted")
            run_log_text = (repo / ".agent-os" / "run-log.md").read_text(encoding="utf-8")
            runtime_text = (repo / ".agent-os" / "autoresearch-runtime.md").read_text(encoding="utf-8")
            self.assertIn("parallel kept improvement", run_log_text)
            self.assertIn("Retained metric: `7`", runtime_text)
