from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from autoresearch_paths import find_repo_root, resolve_repo_path, results_repo_root


class AutoresearchRepoPathResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="tmp-paths-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_prefers_nested_agent_os_over_outer_git(self) -> None:
        outer = self.tmpdir / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()

        project = outer / "nested-project"
        project.mkdir()
        (project / ".agent-os").mkdir()

        deeper = project / "src" / "pkg"
        deeper.mkdir(parents=True)

        self.assertEqual(find_repo_root(deeper).resolve(), project.resolve())
        self.assertEqual(resolve_repo_path(str(deeper)).resolve(), project.resolve())
        self.assertEqual(results_repo_root(project / "research-results.tsv").resolve(), project.resolve())

    def test_falls_back_to_git_repo_when_no_project_system_exists(self) -> None:
        outer = self.tmpdir / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        deeper = outer / "src" / "pkg"
        deeper.mkdir(parents=True)

        self.assertEqual(find_repo_root(deeper).resolve(), outer.resolve())
        self.assertEqual(resolve_repo_path(str(deeper)).resolve(), outer.resolve())
