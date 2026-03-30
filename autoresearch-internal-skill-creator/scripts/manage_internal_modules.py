from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TYPE_LABELS = {
    "root-routing": "Root Routing",
    "engine-protocol": "Engine Protocol",
    "environment-collaboration": "Environment Collaboration",
    "shared-tooling": "Shared Tooling",
}
VALID_PRIMARY_CALLERS = {"codex-autoresearch", "autoresearch", "env-bootstrap"}
VISIBLE_CREATOR_NAME = "autoresearch-internal-skill-creator"
REGISTRY_PATH = "INTERNAL-MODULES.md"
ROOT_MARKER = ("<!-- INTERNAL-MODULES:ROOT-SKILL-START -->", "<!-- INTERNAL-MODULES:ROOT-SKILL-END -->")
README_MARKER = ("<!-- INTERNAL-MODULES:ROOT-README-START -->", "<!-- INTERNAL-MODULES:ROOT-README-END -->")
ENGINE_MARKER = ("<!-- INTERNAL-MODULES:ENGINE-SKILL-START -->", "<!-- INTERNAL-MODULES:ENGINE-SKILL-END -->")
ENV_MARKER = ("<!-- INTERNAL-MODULES:ENV-SKILL-START -->", "<!-- INTERNAL-MODULES:ENV-SKILL-END -->")


@dataclass(frozen=True)
class InternalModule:
    directory_name: str
    skill_name: str
    summary: str
    module_type: str
    primary_caller: str
    relative_path: str
    visibility: str = "internal"


@dataclass(frozen=True)
class VisibleGovernanceEntry:
    directory_name: str
    summary: str
    relative_path: str
    primary_caller: str = "codex-autoresearch"
    visibility: str = "visible"
    entry_type: str = "visible-governance"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def parse_frontmatter(skill_path: Path) -> dict[str, str]:
    text = read_text(skill_path)
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise ValueError(f"Missing YAML frontmatter in {skill_path}")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Unterminated YAML frontmatter in {skill_path}")
    result: dict[str, str] = {}
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def parse_internal_metadata(skill_path: Path) -> dict[str, str]:
    text = read_text(skill_path)
    match = re.search(
        r"^## Internal Module Metadata\s*$\n(?P<body>.*?)(?:^\s*## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"Missing internal metadata block in {skill_path}")
    metadata: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip()
    required = {"visibility", "module type", "primary caller"}
    missing = sorted(required - metadata.keys())
    if missing:
        raise ValueError(f"Missing internal metadata keys {missing} in {skill_path}")
    return metadata


def discover_internal_modules(repo_root: Path) -> list[InternalModule]:
    modules: list[InternalModule] = []
    for child in sorted(repo_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or child.name.startswith(".") or child.name == "agents":
            continue
        skill_path = child / "SKILL.md"
        agents_path = child / "agents" / "openai.yaml"
        if not skill_path.exists() or agents_path.exists():
            continue
        frontmatter = parse_frontmatter(skill_path)
        metadata = parse_internal_metadata(skill_path)
        module_type = metadata["module type"]
        primary_caller = metadata["primary caller"]
        if module_type not in TYPE_LABELS:
            raise ValueError(f"Unsupported module type '{module_type}' in {skill_path}")
        if primary_caller not in VALID_PRIMARY_CALLERS:
            raise ValueError(f"Unsupported primary caller '{primary_caller}' in {skill_path}")
        modules.append(
            InternalModule(
                directory_name=child.name,
                skill_name=frontmatter["name"],
                summary=frontmatter["description"],
                module_type=module_type,
                primary_caller=primary_caller,
                relative_path=child.name.replace("\\", "/"),
                visibility=metadata["visibility"],
            )
        )
    return modules


def load_visible_governance_entry(repo_root: Path) -> VisibleGovernanceEntry:
    creator_root = repo_root / VISIBLE_CREATOR_NAME
    if not (creator_root / "SKILL.md").exists() or not (creator_root / "agents" / "openai.yaml").exists():
        raise ValueError(f"Visible governance skill is missing at {creator_root}")
    frontmatter = parse_frontmatter(creator_root / "SKILL.md")
    return VisibleGovernanceEntry(
        directory_name=VISIBLE_CREATOR_NAME,
        summary=frontmatter["description"],
        relative_path=VISIBLE_CREATOR_NAME,
    )


def wiring_targets_for(module_type: str, primary_caller: str) -> list[str]:
    if module_type == "root-routing":
        return ["SKILL.md", "README.md"]
    if module_type == "engine-protocol":
        return ["autoresearch/SKILL.md"]
    if module_type == "environment-collaboration":
        return ["env-bootstrap/SKILL.md"]
    if primary_caller == "autoresearch":
        return ["autoresearch/SKILL.md"]
    if primary_caller == "env-bootstrap":
        return ["env-bootstrap/SKILL.md"]
    return ["SKILL.md", "README.md"]


def format_targets(targets: Iterable[str]) -> str:
    return ", ".join(f"`{target}`" for target in targets)


def group_modules_by_type(modules: Iterable[InternalModule]) -> dict[str, list[InternalModule]]:
    grouped = {module_type: [] for module_type in TYPE_LABELS}
    for module in modules:
        grouped[module.module_type].append(module)
    return grouped


def render_registry(visible_entry: VisibleGovernanceEntry, modules: list[InternalModule]) -> str:
    grouped = group_modules_by_type(modules)
    lines = [
        "# Internal Modules Registry",
        "",
        "This file is generated by `autoresearch-internal-skill-creator`.",
        "After any skill or internal module change in this repository, run the visible governance skill in `sync` mode to rebuild this registry.",
        "",
        "## Visible Governance Entry",
        "",
        f"### {visible_entry.directory_name}",
        f"- Type: `{visible_entry.entry_type}`",
        f"- Path: `{visible_entry.relative_path}/`",
        f"- Visibility: `{visible_entry.visibility}`",
        f"- Primary caller: `{visible_entry.primary_caller}`",
        f"- Summary: {visible_entry.summary}",
        "- Wiring targets: `SKILL.md`, `README.md`",
        "",
        "## Internal Modules",
        "",
    ]
    for module_type, title in TYPE_LABELS.items():
        lines.extend([f"### {title}", ""])
        items = grouped[module_type]
        if not items:
            lines.append("- None registered.")
            lines.append("")
            continue
        for module in items:
            lines.extend(
                [
                    f"#### {module.directory_name}",
                    f"- Type: `{module.module_type}`",
                    f"- Path: `{module.relative_path}/`",
                    f"- Visibility: `{module.visibility}`",
                    f"- Primary caller: `{module.primary_caller}`",
                    f"- Summary: {module.summary}",
                    f"- Wiring targets: {format_targets(wiring_targets_for(module.module_type, module.primary_caller))}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def render_map_lines(entries: list[tuple[str, str, str]]) -> str:
    if not entries:
        return "- No modules registered for this view."
    return "\n".join(f"- `{name}/`: `{entry_type}`. {summary}" for name, entry_type, summary in entries)


def root_view_entries(visible_entry: VisibleGovernanceEntry, modules: list[InternalModule]) -> list[tuple[str, str, str]]:
    entries = [(visible_entry.directory_name, visible_entry.entry_type, visible_entry.summary)]
    for module in modules:
        if module.primary_caller == "codex-autoresearch" or module.module_type == "root-routing":
            entries.append((module.directory_name, module.module_type, module.summary))
    return entries


def engine_view_entries(modules: list[InternalModule]) -> list[tuple[str, str, str]]:
    return [
        (module.directory_name, module.module_type, module.summary)
        for module in modules
        if module.module_type == "engine-protocol"
        or (module.module_type == "shared-tooling" and module.primary_caller == "autoresearch")
    ]


def env_view_entries(modules: list[InternalModule]) -> list[tuple[str, str, str]]:
    return [
        (module.directory_name, module.module_type, module.summary)
        for module in modules
        if module.module_type == "environment-collaboration"
        or (module.module_type == "shared-tooling" and module.primary_caller == "env-bootstrap")
    ]


def replace_between_markers(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), flags=re.DOTALL)
    new_block = f"{start_marker}\n{replacement}\n{end_marker}"
    if not pattern.search(text):
        raise ValueError(f"Missing marker block {start_marker} ... {end_marker}")
    return pattern.sub(new_block, text, count=1)


def update_module_maps(repo_root: Path, visible_entry: VisibleGovernanceEntry, modules: list[InternalModule]) -> list[str]:
    updates: list[tuple[Path, tuple[str, str], str]] = [
        (
            repo_root / "SKILL.md",
            ROOT_MARKER,
            render_map_lines(root_view_entries(visible_entry, modules)),
        ),
        (
            repo_root / "README.md",
            README_MARKER,
            render_map_lines(root_view_entries(visible_entry, modules)),
        ),
        (
            repo_root / "autoresearch" / "SKILL.md",
            ENGINE_MARKER,
            render_map_lines(engine_view_entries(modules)),
        ),
        (
            repo_root / "env-bootstrap" / "SKILL.md",
            ENV_MARKER,
            render_map_lines(env_view_entries(modules)),
        ),
    ]
    changed_files: list[str] = []
    for path, markers, replacement in updates:
        updated = replace_between_markers(read_text(path), markers[0], markers[1], replacement)
        if write_text_if_changed(path, updated):
            changed_files.append(path.relative_to(repo_root).as_posix())
    return changed_files


def extract_registry_module_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    names: set[str] = set()
    current_section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current_section = line
        elif current_section == "## Internal Modules" and line.startswith("#### "):
            names.add(line[5:].strip())
    return names


def sync_registry(repo_root: Path) -> dict[str, object]:
    registry_path = repo_root / REGISTRY_PATH
    old_names = extract_registry_module_names(registry_path)
    modules = discover_internal_modules(repo_root)
    visible_entry = load_visible_governance_entry(repo_root)
    registry_content = render_registry(visible_entry, modules)
    registry_changed = write_text_if_changed(registry_path, registry_content)
    map_changes = update_module_maps(repo_root, visible_entry, modules)
    new_names = {module.directory_name for module in modules}
    return {
        "added": sorted(new_names - old_names),
        "removed": sorted(old_names - new_names),
        "registry_changed": registry_changed,
        "map_changes": map_changes,
    }


def validate_module_name(name: str) -> None:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("Module names must use lowercase letters, digits, and hyphens only.")


def create_internal_module(
    repo_root: Path,
    name: str,
    module_type: str,
    summary: str,
    primary_caller: str,
) -> dict[str, object]:
    validate_module_name(name)
    if module_type not in TYPE_LABELS:
        raise ValueError(f"Unsupported module type '{module_type}'.")
    if primary_caller not in VALID_PRIMARY_CALLERS:
        raise ValueError(f"Unsupported primary caller '{primary_caller}'.")
    module_root = repo_root / name
    if module_root.exists():
        raise ValueError(f"Module directory already exists: {module_root}")

    module_root.mkdir(parents=True)
    for relative in ("scripts", "references", "assets"):
        target = module_root / relative
        target.mkdir()
        (target / ".gitkeep").write_text("", encoding="utf-8")

    title = " ".join(part.capitalize() for part in name.split("-"))
    skill_content = f"""---
name: {name}
description: {summary}
---

# {title}

Internal module for `codex-autoresearch`.

## Internal Module Metadata

Visibility: internal
Module type: {module_type}
Primary caller: {primary_caller}

## Responsibilities

- {summary}
- Keep this module internal. Do not add `agents/openai.yaml`.
"""
    (module_root / "SKILL.md").write_text(skill_content, encoding="utf-8")
    sync_result = sync_registry(repo_root)
    sync_result["created"] = name
    return sync_result


def print_sync_summary(summary: dict[str, object]) -> None:
    added = summary["added"]
    removed = summary["removed"]
    changed_files = summary["map_changes"]
    if added:
        print("Added modules: " + ", ".join(added))
    if removed:
        print("Removed modules: " + ", ".join(removed))
    if changed_files:
        print("Updated wiring: " + ", ".join(changed_files))
    if summary["registry_changed"]:
        print(f"Updated registry: {REGISTRY_PATH}")
    if not added and not removed and not changed_files and not summary["registry_changed"]:
        print("No structural module changes detected; registry and wiring were already up to date.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and sync internal codex-autoresearch modules.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a new internal module and sync the registry.")
    create.add_argument("name")
    create.add_argument("--module-type", required=True, choices=sorted(TYPE_LABELS))
    create.add_argument("--summary", required=True)
    create.add_argument("--primary-caller", required=True, choices=sorted(VALID_PRIMARY_CALLERS))

    subparsers.add_parser("sync", help="Rebuild INTERNAL-MODULES.md and refresh module maps.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo_root = repo_root_from_script()
    if args.command == "create":
        summary = create_internal_module(
            repo_root,
            args.name,
            args.module_type,
            args.summary,
            args.primary_caller,
        )
    else:
        summary = sync_registry(repo_root)
    print_sync_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
