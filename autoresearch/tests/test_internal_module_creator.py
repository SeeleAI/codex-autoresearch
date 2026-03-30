from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT.parent
    / "autoresearch-internal-skill-creator"
    / "scripts"
    / "manage_internal_modules.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("manage_internal_modules", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InternalModuleCreatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        base = REPO_ROOT.parent / ".tmp-tests"
        base.mkdir(exist_ok=True)
        self.tmpdir = base / f"tmp-internal-modules-{uuid.uuid4().hex[:8]}"
        self.tmpdir.mkdir()
        self.repo_root = self.tmpdir / "codex-autoresearch"
        self.repo_root.mkdir()
        self.write_repo_skeleton()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir)

    def write_repo_skeleton(self) -> None:
        (self.repo_root / "SKILL.md").write_text(
            """---
name: codex-autoresearch
description: Root wrapper.
---

# Root

## Internal Governance

<!-- INTERNAL-MODULES:ROOT-SKILL-START -->
<!-- INTERNAL-MODULES:ROOT-SKILL-END -->
""",
            encoding="utf-8",
        )
        (self.repo_root / "README.md").write_text(
            """# Root

<!-- INTERNAL-MODULES:ROOT-README-START -->
<!-- INTERNAL-MODULES:ROOT-README-END -->
""",
            encoding="utf-8",
        )
        for module_name, module_type in (
            ("autoresearch", "engine-protocol"),
            ("env-bootstrap", "environment-collaboration"),
        ):
            module_root = self.repo_root / module_name
            module_root.mkdir()
            (module_root / "SKILL.md").write_text(
                f"""---
name: {module_name}
description: {module_name} summary.
---

# {module_name}

## Internal Module Metadata

Visibility: internal
Module type: {module_type}
Primary caller: codex-autoresearch

## Internal Module Map

<!-- INTERNAL-MODULES:{'ENGINE' if module_name == 'autoresearch' else 'ENV'}-SKILL-START -->
<!-- INTERNAL-MODULES:{'ENGINE' if module_name == 'autoresearch' else 'ENV'}-SKILL-END -->
""",
                encoding="utf-8",
            )

        creator_root = self.repo_root / "autoresearch-internal-skill-creator"
        (creator_root / "agents").mkdir(parents=True)
        (creator_root / "SKILL.md").write_text(
            """---
name: autoresearch-internal-skill-creator
description: Visible governance skill.
---

# Creator
""",
            encoding="utf-8",
        )
        (creator_root / "agents" / "openai.yaml").write_text(
            """interface:
  display_name: "Autoresearch Internal Skill Creator"
  short_description: "Create and sync internal autoresearch modules"
  default_prompt: "Use $autoresearch-internal-skill-creator to create modules and sync INTERNAL-MODULES.md."
""",
            encoding="utf-8",
        )

    def test_create_internal_module_creates_scaffold_without_agents_metadata(self) -> None:
        self.module.create_internal_module(
            self.repo_root,
            "runtime-planner",
            "engine-protocol",
            "Plan detached runtime coordination for internal autoresearch flows.",
            "autoresearch",
        )

        created = self.repo_root / "runtime-planner"
        self.assertTrue((created / "SKILL.md").exists())
        self.assertTrue((created / "scripts" / ".gitkeep").exists())
        self.assertTrue((created / "references" / ".gitkeep").exists())
        self.assertTrue((created / "assets" / ".gitkeep").exists())
        self.assertFalse((created / "agents" / "openai.yaml").exists())

        registry = (self.repo_root / "INTERNAL-MODULES.md").read_text(encoding="utf-8")
        self.assertIn("runtime-planner", registry)
        self.assertIn("autoresearch-internal-skill-creator", registry)

    def test_sync_removes_deleted_module_from_registry(self) -> None:
        self.module.create_internal_module(
            self.repo_root,
            "runtime-planner",
            "engine-protocol",
            "Plan detached runtime coordination for internal autoresearch flows.",
            "autoresearch",
        )
        shutil.rmtree(self.repo_root / "runtime-planner")

        self.module.sync_registry(self.repo_root)

        registry = (self.repo_root / "INTERNAL-MODULES.md").read_text(encoding="utf-8")
        self.assertNotIn("runtime-planner", registry)


if __name__ == "__main__":
    unittest.main()
