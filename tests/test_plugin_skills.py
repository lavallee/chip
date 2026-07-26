"""The Claude Code plugin's skills/ tree is a synced copy of the canonical skills
packaged with the library (src/chip/skills). RELEASING.md says `cp -r`; this test
is what makes that instruction load-bearing — any drift between the two trees
fails the suite byte-for-byte in both directions.

It also checks the skills against the CLI they document: a command map that names
a verb the CLI does not have is worse than no command map.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from chip.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "src" / "chip" / "skills"
PLUGIN = ROOT / "skills"

EXPECTED = {
    "chip-candidate",
    "chip-author",
    "chip-fixtures",
    "chip-evaluate",
    "chip-install",
    "chip-audit",
    "chip-outcome",
}


def _tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_plugin_skills_match_canonical():
    canonical, plugin = _tree(CANONICAL), _tree(PLUGIN)
    assert plugin.keys() == canonical.keys(), (
        "plugin skills/ and src/chip/skills differ in file set; "
        "re-sync with: rm -rf skills && cp -r src/chip/skills skills"
    )
    stale = [name for name, body in canonical.items() if plugin[name] != body]
    assert not stale, (
        f"plugin skills/ out of date for {stale}; "
        "re-sync with: rm -rf skills && cp -r src/chip/skills skills"
    )


def test_every_expected_skill_ships():
    assert {p.name for p in CANONICAL.iterdir() if p.is_dir()} == EXPECTED


@pytest.mark.parametrize("skill", sorted(EXPECTED))
def test_skill_frontmatter(skill):
    text = (CANONICAL / skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{skill}: missing frontmatter"
    _, frontmatter, _ = text.split("---", 2)
    assert re.search(rf"^name: {re.escape(skill)}$", frontmatter, re.M), (
        f"{skill}: frontmatter name must match the directory"
    )
    description = re.search(r"^description: (.+)$", frontmatter, re.M)
    assert description, f"{skill}: missing description"
    # A description is a trigger, not a title: it has to say when to invoke.
    assert "invoke" in description.group(1), (
        f"{skill}: description must say when to invoke the skill"
    )


def _cli_verbs() -> set[str]:
    parser = build_parser()
    actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
    return set(actions[0].choices) if actions else set()


@pytest.mark.parametrize("skill", sorted(EXPECTED))
def test_command_maps_name_only_real_cli_verbs(skill):
    """A skill may not document a `chip <verb>` the CLI does not implement."""
    text = (CANONICAL / skill / "SKILL.md").read_text(encoding="utf-8")
    verbs = _cli_verbs()
    cited = set(re.findall(r"`chip ([a-z][a-z-]*)[ `]", text))
    cited -= {"--help"}
    unknown = cited - verbs
    assert not unknown, f"{skill}: documents non-existent chip verb(s) {sorted(unknown)}"
