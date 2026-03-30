from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class SkillContractTest(unittest.TestCase):
    def test_frontmatter_is_minimal_and_names_are_distinct(self) -> None:
        root_skill = (REPO_ROOT.parent / "SKILL.md").read_text(encoding="utf-8")
        engine_skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("name: codex-autoresearch", root_skill)
        self.assertIn("name: codex-autoresearch-engine", engine_skill)
        self.assertNotIn("\nmetadata:\n", root_skill)
        self.assertNotIn("\nmetadata:\n", engine_skill)

    def test_root_skill_has_standard_agents_metadata(self) -> None:
        metadata_path = REPO_ROOT.parent / "agents" / "openai.yaml"
        content = metadata_path.read_text(encoding="utf-8")

        self.assertTrue(metadata_path.exists())
        self.assertIn('display_name: "Codex Autoresearch"', content)
        self.assertIn('short_description: "Unified entrypoint', content)
        self.assertIn('default_prompt: "Use $codex-autoresearch as the public entrypoint', content)
        self.assertNotIn("codex-autoresearch-engine", content)

    def test_visible_governance_skill_has_public_metadata(self) -> None:
        metadata_path = REPO_ROOT.parent / "autoresearch-internal-skill-creator" / "agents" / "openai.yaml"
        content = metadata_path.read_text(encoding="utf-8")

        self.assertTrue(metadata_path.exists())
        self.assertIn('display_name: "Autoresearch Internal Skill Creator"', content)
        self.assertIn('short_description: "Create and sync internal autoresearch modules"', content)
        self.assertIn("INTERNAL-MODULES.md", content)

    def test_nested_modules_do_not_expose_separate_agents_metadata(self) -> None:
        self.assertFalse((REPO_ROOT / "agents" / "openai.yaml").exists())
        self.assertFalse((REPO_ROOT.parent / "env-bootstrap" / "agents" / "openai.yaml").exists())
        self.assertFalse((REPO_ROOT.parent / "git-runtime-governor" / "agents" / "openai.yaml").exists())

    def test_only_root_and_governance_skill_are_visible(self) -> None:
        visible = {
            path.relative_to(REPO_ROOT.parent).as_posix()
            for path in REPO_ROOT.parent.rglob("openai.yaml")
            if path.parent.name == "agents"
        }
        self.assertEqual(
            visible,
            {
                "agents/openai.yaml",
                "autoresearch-internal-skill-creator/agents/openai.yaml",
            },
        )

    def test_internal_module_registry_exists_and_mentions_current_modules(self) -> None:
        registry = (REPO_ROOT.parent / "INTERNAL-MODULES.md").read_text(encoding="utf-8")

        self.assertIn("autoresearch-internal-skill-creator", registry)
        self.assertIn("autoresearch", registry)
        self.assertIn("env-bootstrap", registry)
        self.assertIn("git-runtime-governor", registry)
        self.assertIn("Type: `engine-protocol`", registry)
        self.assertIn("Type: `environment-collaboration`", registry)
        self.assertIn("Type: `shared-tooling`", registry)

    def test_root_docs_require_registry_sync_via_visible_creator(self) -> None:
        root_skill = (REPO_ROOT.parent / "SKILL.md").read_text(encoding="utf-8")
        root_readme = (REPO_ROOT.parent / "README.md").read_text(encoding="utf-8")

        self.assertIn("$autoresearch-internal-skill-creator", root_skill)
        self.assertIn("call the creator in `sync` mode", root_skill)
        self.assertIn("INTERNAL-MODULES.md", root_skill)
        self.assertIn("$autoresearch-internal-skill-creator", root_readme)
        self.assertIn("INTERNAL-MODULES.md", root_readme)
        self.assertIn("git-runtime-governor/SKILL.md", root_skill)
        self.assertIn("after verification and before the final keep/discard/blocker resolution", root_skill)
        self.assertIn("git-runtime-governor", root_readme)
        self.assertIn("after verification and before keep/discard/blocker finalization", root_readme)

    def test_engine_docs_use_nested_helper_path_contract(self) -> None:
        expected = ".agents/skills/codex-autoresearch/autoresearch/scripts"
        for relative in (
            Path("SKILL.md"),
            Path("references") / "autonomous-loop-protocol.md",
            Path("references") / "results-logging.md",
        ):
            content = (REPO_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(expected, content)
            self.assertNotIn(".agents/skills/codex-autoresearch/scripts", content)

    def test_env_bootstrap_sources_are_portable(self) -> None:
        for relative in (
            REPO_ROOT.parent / "env-bootstrap" / "SKILL.md",
            REPO_ROOT.parent / "env-bootstrap" / "references" / "environment-playbook.md",
            REPO_ROOT.parent / "env-bootstrap" / "scripts" / "probe_env.ps1",
            REPO_ROOT.parent / "env-bootstrap" / "scripts" / "probe_env.sh",
        ):
            content = relative.read_text(encoding="utf-8")
            self.assertNotIn("/home/vice/", content)

    def test_interaction_wizard_surfaces_execution_policy(self) -> None:
        wizard = (REPO_ROOT / "references" / "interaction-wizard.md").read_text(encoding="utf-8")
        self.assertIn("Background execution policy: `workspace_write` by default", wizard)
        self.assertIn("Run mode: foreground, or background with `workspace_write` / `danger_full_access`?", wizard)

    def test_git_runtime_governor_contract_is_wired(self) -> None:
        engine_skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        protocol = (REPO_ROOT / "references" / "autonomous-loop-protocol.md").read_text(encoding="utf-8")
        governor_skill = (REPO_ROOT.parent / "git-runtime-governor" / "SKILL.md").read_text(encoding="utf-8")
        template_path = (
            REPO_ROOT.parent
            / "git-runtime-governor"
            / "references"
            / "general-gitignore-template.md"
        )

        self.assertIn("../git-runtime-governor/SKILL.md", engine_skill)
        self.assertIn("after verification and any guard handling", engine_skill)
        self.assertIn("## Phase 6.7: Git Governance Auto-Commit", protocol)
        self.assertIn(".agent-os/autoresearch-config.md", protocol)
        self.assertTrue(template_path.exists())
        self.assertIn("per-iteration auto-commit", governor_skill)
        self.assertIn("Do not add `agents/openai.yaml`", governor_skill)


if __name__ == "__main__":
    unittest.main()
