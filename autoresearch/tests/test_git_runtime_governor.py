from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "git-runtime-governor"
    / "scripts"
    / "git_runtime_governor.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("git_runtime_governor", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GitRuntimeGovernorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_render_gitignore_block_deduplicates_and_orders_rules(self) -> None:
        rendered = self.module.render_gitignore_block(
            ["autoresearch-state", "runtime-control"],
            ["custom.cache", "research-results.tsv"],
        )

        self.assertTrue(rendered.startswith(self.module.MANAGED_BLOCK_START))
        self.assertIn("research-results.tsv", rendered)
        self.assertEqual(rendered.count("research-results.tsv"), 1)
        self.assertIn("autoresearch-launch.json", rendered)
        self.assertIn("custom.cache", rendered)
        self.assertTrue(rendered.endswith(self.module.MANAGED_BLOCK_END + "\n"))

    def test_render_gitignore_block_rejects_unknown_category(self) -> None:
        with self.assertRaises(ValueError):
            self.module.render_gitignore_block(["unknown-category"], [])

    def test_merge_gitignore_text_appends_managed_block_when_missing(self) -> None:
        managed = self.module.render_gitignore_block(["build-cache"], [])
        merged = self.module.merge_gitignore_text("node_modules/\n", managed)

        self.assertIn("node_modules/", merged)
        self.assertIn(self.module.MANAGED_BLOCK_START, merged)
        self.assertIn("__pycache__/", merged)

    def test_merge_gitignore_text_replaces_existing_managed_block(self) -> None:
        original = (
            "node_modules/\n\n"
            f"{self.module.MANAGED_BLOCK_START}\n"
            "old-rule\n"
            f"{self.module.MANAGED_BLOCK_END}\n"
        )
        managed = self.module.render_gitignore_block(["document-files"], ["custom.pdf"])
        merged = self.module.merge_gitignore_text(original, managed)

        self.assertIn("node_modules/", merged)
        self.assertNotIn("old-rule", merged)
        self.assertIn("*.pdf", merged)
        self.assertIn("custom.pdf", merged)

    def test_build_commit_message_contains_required_fields(self) -> None:
        message = self.module.build_commit_message(
            iteration=7,
            mode="loop",
            summary="retain faster parser branch",
            policy_fingerprint="abc123",
            categories=["autoresearch-state", "document-files"],
        )

        self.assertIn("autoresearch: iteration 007", message)
        self.assertIn("[mode=loop]", message)
        self.assertIn("[policy=abc123]", message)
        self.assertIn("summary: retain faster parser branch", message)
        self.assertIn("categories: autoresearch-state, document-files", message)

    def test_governed_commit_stages_in_scope_files_and_uses_policy_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
            (repo / ".agent-os").mkdir()
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("print('before')\n", encoding="utf-8")
            (repo / "notes.txt").write_text("ignore me\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True)

            policy = {
                "allowed_categories": [],
                "auto_commit_enabled": True,
                "branch_strategy": "dedicated_experiment_branch",
                "custom_gitignore_rules": [],
                "managed_repo_paths": [str(repo.resolve())],
                "policy_fingerprint": "abc123def456",
            }
            (repo / ".agent-os" / "autoresearch-config.md").write_text(
                "\n".join(
                    [
                        "# Autoresearch Config",
                        "",
                        "## Run Contract",
                        "",
                        "- Scope: `src/**/*.py`",
                        "",
                        "## Managed Git Policy",
                        "",
                        "<!-- AUTORESEARCH-MANAGED-GIT-POLICY START -->",
                        "```json",
                        json.dumps(policy, indent=2, sort_keys=True),
                        "```",
                        "<!-- AUTORESEARCH-MANAGED-GIT-POLICY END -->",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            (repo / "src" / "app.py").write_text("print('after')\n", encoding="utf-8")
            (repo / "notes.txt").write_text("still out of scope\n", encoding="utf-8")

            payload = self.module.governed_commit(
                repo=repo,
                config_path=repo / ".agent-os" / "autoresearch-config.md",
                scope_text="src/**/*.py",
                iteration=1,
                mode="loop",
                summary="keep source change",
            )

            self.assertEqual(payload["policy_fingerprint"], "abc123def456")
            self.assertIn("src/app.py", payload["staged_files"])
            self.assertNotIn("notes.txt", payload["staged_files"])
            message = subprocess.run(
                ["git", "-C", str(repo), "log", "-1", "--format=%B"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertIn("autoresearch: iteration 001", message)
            self.assertIn("[policy=abc123def456]", message)


if __name__ == "__main__":
    unittest.main()
