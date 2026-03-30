from __future__ import annotations

import importlib.util
import sys
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


if __name__ == "__main__":
    unittest.main()
