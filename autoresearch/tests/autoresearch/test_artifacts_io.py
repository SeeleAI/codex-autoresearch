from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from autoresearch_artifacts import make_row, parse_decimal, write_json_atomic, write_results_log


class AutoresearchArtifactsIoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp(prefix="tmp-artifacts-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scripts_module_alias_points_to_loaded_artifacts_module(self) -> None:
        self.assertIs(sys.modules["scripts.autoresearch_artifacts"], sys.modules["autoresearch_artifacts"])

    def test_write_json_atomic_falls_back_when_replace_is_denied(self) -> None:
        path = self.tmpdir / "state.json"

        with patch("scripts.autoresearch_artifacts.os.replace", side_effect=PermissionError("replace denied")):
            write_json_atomic(path, {"a": 1, "b": 2})

        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1, "b": 2})
        temps = list(self.tmpdir.glob("state.json.*.tmp"))
        self.assertEqual(temps, [])

    def test_write_results_log_falls_back_when_replace_is_denied(self) -> None:
        path = self.tmpdir / "research-results.tsv"
        row = make_row(
            iteration="0",
            commit="abc123",
            metric=parse_decimal("10", "metric"),
            delta=parse_decimal("0", "delta"),
            guard="-",
            status="baseline",
            description="baseline",
            labels=[],
        )

        with patch("scripts.autoresearch_artifacts.os.replace", side_effect=PermissionError("replace denied")):
            write_results_log(path, ["# metric_direction: lower"], [row])

        text = path.read_text(encoding="utf-8")
        self.assertIn("iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription", text)
        self.assertIn("0\tabc123\t10\t0\t-\tbaseline\tbaseline", text)
        temps = list(self.tmpdir.glob("research-results.tsv.*.tmp"))
        self.assertEqual(temps, [])
