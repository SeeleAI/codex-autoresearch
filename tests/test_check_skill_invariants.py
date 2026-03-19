from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_skill_invariants.py"


class CheckSkillInvariantsTest(unittest.TestCase):
    def test_exec_expect_improvement_supports_higher_direction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "research-results.tsv").write_text(
                "\n".join(
                    [
                        "# metric_direction: higher",
                        "iteration\tcommit\tmetric\tdelta\tguard\tstatus\tdescription",
                        "0\tbase123\t10\t0\t-\tbaseline\tbaseline score",
                        "1\tkeep123\t12\t+2\tpass\tkeep\timproved score",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (repo / "autoresearch-lessons.md").write_text("# lessons\n", encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "exec", "--repo", str(repo), "--expect-improvement"],
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("exec invariants: OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()
