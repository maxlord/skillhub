"""spec-lint tests: a good skill passes, each kind of bad one is caught.

Run: `python3 -m pytest tools/` or `python3 -m unittest discover -s tools/tests`.
"""
from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import spec_lint  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "spec"
CATALOG = FIX / "catalog"
GOOD = FIX / "good" / "good-skill"


class SpecLintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def make(self, replace: dict[str, str] | None = None, name: str = "good-skill",
             append: str = "") -> Path:
        """Copy of the good fixture with replacements in SKILL.md."""
        dst = self.tmp / name
        shutil.copytree(GOOD, dst)
        text = (dst / "SKILL.md").read_text(encoding="utf-8")
        for old, new in (replace or {}).items():
            self.assertIn(old, text, f"fixture does not contain {old!r}")
            text = text.replace(old, new)
        (dst / "SKILL.md").write_text(text + append, encoding="utf-8")
        return dst

    def errors(self, skill_dir: Path) -> list[str]:
        issues = spec_lint.lint_skill(skill_dir, CATALOG, use_git=False)
        return [i.message for i in issues if i.level == "error"]

    def assertError(self, skill_dir: Path, needle: str):
        errs = self.errors(skill_dir)
        self.assertTrue(any(needle in e for e in errs), f"expected an error with {needle!r}, got {errs}")

    # --- good -------------------------------------------------------------

    def test_good_fixture_passes(self):
        issues = spec_lint.lint_skill(GOOD, CATALOG, use_git=False)
        self.assertEqual([], issues)

    def test_cli_exit_codes(self):
        self.assertEqual(0, spec_lint.main(["--no-git", "--catalog", str(CATALOG), str(GOOD)]))
        bad = self.make({"category: development": "category: nope"})
        self.assertEqual(1, spec_lint.main(["--no-git", "--catalog", str(CATALOG), str(bad)]))

    # --- structure -----------------------------------------------------------

    def test_missing_skill_md(self):
        d = self.tmp / "empty"
        d.mkdir()
        self.assertError(d, "no SKILL.md")

    def test_missing_frontmatter(self):
        d = self.make()
        text = (d / "SKILL.md").read_text(encoding="utf-8")
        (d / "SKILL.md").write_text(text.replace("---\n", "", 2), encoding="utf-8")
        self.assertError(d, "no frontmatter")

    def test_unknown_field(self):
        self.assertError(self.make({"license:": "flavour: x\nlicense:"}), "invalid frontmatter field")

    def test_version_forbidden(self):
        self.assertError(self.make({"license:": "version: \"1.0\"\nlicense:"}), "`version`")

    def test_claude_only_field_warns(self):
        d = self.make({"license:": "context: fork\nlicense:"})
        issues = spec_lint.lint_skill(d, CATALOG, use_git=False)
        self.assertEqual(["warning"], [i.level for i in issues])

    # --- name ----------------------------------------------------------------

    def test_name_mismatch(self):
        self.assertError(self.make({"name: good-skill": "name: other"}), "does not match")

    def test_name_double_dash(self):
        d = self.make({"name: good-skill": "name: bad--name"}, name="bad--name")
        self.assertError(d, "single `-`")

    def test_name_uppercase(self):
        d = self.make({"name: good-skill": "name: Bad-Name"}, name="Bad-Name")
        self.assertError(d, "only a-z0-9")

    def test_name_too_long(self):
        long = "a" * 65
        self.assertError(self.make({"name: good-skill": f"name: {long}"}, name=long), "longer than 64")

    # --- description ---------------------------------------------------------

    def test_description_too_long_for_hub(self):
        long = "Guides " + "very " * 80 + "Use when needed."
        self.assertError(self.make({"Guides an example skill card for spec-lint tests.": long}), "hub limit")

    def test_description_too_long_for_spec(self):
        long = "Guides " + "very " * 200 + "Use when needed."
        self.assertError(self.make({"Guides an example skill card for spec-lint tests.": long}), "spec limit")

    def test_description_not_verb(self):
        self.assertError(self.make({"Guides an example": "Git flow example"}), "action verb")

    def test_description_without_when(self):
        d = self.make({"Use when checking the linter against a good skill.": "Just an example."})
        self.assertError(d, "when to use")

    def test_description_missing(self):
        d = self.make({"description: >\n  Guides an example skill card for spec-lint tests.\n"
                       "  Use when checking the linter against a good skill.\n": ""})
        self.assertError(d, "no `description`")

    # --- metadata ------------------------------------------------------------

    def test_category_not_in_catalog(self):
        self.assertError(self.make({"category: development": "category: nope"}), "categories.yaml")

    def test_owner_not_in_catalog(self):
        self.assertError(self.make({"owner: maintainer": "owner: someone"}), "owners.yaml")

    def test_bad_maturity(self):
        self.assertError(self.make({"maturity: stable": "maturity: beta"}), "maturity")

    def test_missing_required_metadata(self):
        self.assertError(self.make({"  projects: all\n": ""}), "metadata.projects")

    def test_bad_date(self):
        self.assertError(self.make({"added: 2026-10-22": "added: 22.10.2026"}), "YYYY-MM-DD")

    def test_added_after_updated(self):
        self.assertError(self.make({"added: 2026-10-22": "added: 2026-11-01"}), "later than")

    def test_leader_must_be_string(self):
        self.assertError(self.make({'leader: "true"': "leader: true"}), "must be a string")

    def test_leader_without_cluster(self):
        self.assertError(self.make({"  cluster: example\n": ""}), "without `metadata.cluster`")

    # --- size and links -------------------------------------------------------

    def test_too_many_lines(self):
        self.assertError(self.make(append="\n" + "line\n" * 300), "longer than 300 lines")

    def test_too_many_tokens(self):
        self.assertError(self.make(append="\n" + ("word " * 200 + "\n") * 20), "tokens")

    def test_link_two_levels_deep(self):
        self.assertError(self.make(append="\nSee `references/deep/x.md`.\n"), "deeper than one level")

    def test_link_outside_skill(self):
        self.assertError(self.make(append="\nSee [x](../other/SKILL.md).\n"), "outside the skill directory")

    def test_link_missing_file(self):
        self.assertError(self.make(append="\nSee [x](references/missing.md).\n"), "file does not exist")

    # --- self-containment ---------------------------------------------------------

    def test_env_check_missing(self):
        self.assertError(self.make({"## Environment check": "## Environment"}), "Environment check")

    def test_env_check_not_first(self):
        d = self.make({"## Environment check": "## Also when"})
        d2 = d / "SKILL.md"
        d2.write_text(d2.read_text(encoding="utf-8") + "\n## Environment check\n\nOk.\n", encoding="utf-8")
        self.assertError(d, "first section")

    def test_env_check_missing_is_warning_for_draft(self):
        d = self.make({"## Environment check": "## Environment", "maturity: stable": "maturity: draft"})
        self.assertEqual([], self.errors(d))

    # --- git ---------------------------------------------------------------------

    def test_updated_matches_git_log(self):
        repo = self.tmp / "repo"
        skill = repo / "skills" / "good-skill"
        shutil.copytree(GOOD, skill)
        env = ["-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), *env, "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), *env, "commit", "-q", "-m", "x",
                        "--date", "2026-10-22T10:00:00+00:00"], check=True)
        self.assertEqual([], [i for i in spec_lint.lint_skill(skill, CATALOG) if i.level == "error"])
        subprocess.run(["git", "-C", str(repo), *env, "commit", "-q", "--amend", "-m", "x",
                        "--date", "2026-10-25T10:00:00+00:00"], check=True)
        errs = [i.message for i in spec_lint.lint_skill(skill, CATALOG) if i.level == "error"]
        self.assertTrue(any("2026-10-25" in e for e in errs), errs)
        # dirty directory: today's date is expected
        (skill / "references" / "new.md").write_text("x", encoding="utf-8")
        today = dt.date.today().isoformat()
        errs = [i.message for i in spec_lint.lint_skill(skill, CATALOG) if i.level == "error"]
        self.assertTrue(today == "2026-10-22" or any(today in e for e in errs), errs)

    # --- fallback YAML parser ------------------------------------------------------

    def test_mini_yaml_matches_pyyaml_on_good_fixture(self):
        fm, _, _ = spec_lint.split_frontmatter((GOOD / "SKILL.md").read_text(encoding="utf-8"))
        mini = spec_lint._mini_yaml(fm)
        self.assertEqual("good-skill", mini["name"])
        self.assertTrue(mini["description"].startswith("Guides an example"))
        self.assertEqual("true", mini["metadata"]["leader"])
        self.assertEqual(dt.date(2026, 10, 22), mini["metadata"]["added"])
        if spec_lint.yaml is not None:
            self.assertEqual(spec_lint.yaml.safe_load(fm), mini)

    def test_mini_yaml_hash_inside_quotes_and_blocks(self):
        text = ('description: >\n  Checks issue #12 and PR #3.\n  # not a comment in a block\n'
                'note: "a #b"  # tail\nplain: x#y # tail\n'
                'metadata:\n  source: \'repo:docs #2\'  # tail\n  # comment\n  owner: maintainer\n')
        mini = spec_lint._mini_yaml(text)
        self.assertEqual("Checks issue #12 and PR #3. # not a comment in a block\n", mini["description"])
        self.assertEqual("a #b", mini["note"])
        self.assertEqual("x#y", mini["plain"])
        self.assertEqual({"source": "repo:docs #2", "owner": "maintainer"}, mini["metadata"])
        if spec_lint.yaml is not None:
            self.assertEqual(spec_lint.yaml.safe_load(text), mini)

    def test_mini_yaml_list_of_dicts(self):
        text = "categories:\n  - id: process\n    title: Process\n  - id: development\n"
        self.assertEqual({"categories": [{"id": "process", "title": "Process"}, {"id": "development"}]},
                         spec_lint._mini_yaml(text))


if __name__ == "__main__":
    unittest.main()
