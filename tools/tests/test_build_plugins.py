"""build-plugins.py tests: layout by category, skipping blocked skills, --check catches hand edits."""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
FIX = Path(__file__).resolve().parent / "fixtures"

_spec = importlib.util.spec_from_file_location("build_plugins", TOOLS / "build-plugins.py")
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)

PLUGINS = ("process", "dev")


class BuildPluginsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copytree(FIX / "spec" / "catalog", self.root / "catalog")
        manifest = {"name": "skillhub", "owner": {"name": "Test"},
                    "plugins": [{"name": p, "source": f"./plugins/{p}"} for p in PLUGINS]}
        (self.root / ".claude-plugin").mkdir()
        (self.root / ".claude-plugin" / "marketplace.json").write_text(json.dumps(manifest), encoding="utf-8")
        for p in PLUGINS:
            pj = self.root / "plugins" / p / ".claude-plugin"
            pj.mkdir(parents=True)
            (pj / "plugin.json").write_text(json.dumps({"name": p}), encoding="utf-8")
        skills = self.root / "skills"
        good = skills / "good-skill"
        shutil.copytree(FIX / "spec" / "good" / "good-skill", good)  # category: development
        (good / "evals").mkdir()
        (good / "evals" / "cases.yaml").write_text("cases: []\n", encoding="utf-8")
        shutil.copytree(FIX / "security" / "bad" / "leaky-skill", skills / "leaky-skill")

    def run_tool(self, *args) -> tuple[int, str]:
        out = StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = bp.main(["--root", str(self.root), *args])
        return rc, out.getvalue()

    def test_build_copies_by_category_and_skips_blocked(self):
        rc, out = self.run_tool()
        self.assertEqual(0, rc, out)
        dev = self.root / "plugins" / "dev" / "skills"
        self.assertTrue((dev / "good-skill" / "SKILL.md").is_file())
        self.assertTrue((dev / "good-skill" / "references" / "rationale.md").is_file())
        self.assertFalse((dev / "good-skill" / "evals").exists())
        self.assertFalse((dev / "leaky-skill").exists())
        self.assertIn("skipped leaky-skill", out)
        self.assertEqual(0, self.run_tool("--check")[0])

    def test_check_fails_on_hand_edit_extra_and_missing(self):
        self.assertEqual(0, self.run_tool()[0])
        copy = self.root / "plugins" / "dev" / "skills" / "good-skill" / "SKILL.md"
        copy.write_text(copy.read_text(encoding="utf-8") + "\nedited by hand\n", encoding="utf-8")
        rc, out = self.run_tool("--check")
        self.assertEqual(1, rc)
        self.assertIn("copy edited by hand", out)
        self.run_tool()
        extra = self.root / "plugins" / "process" / "skills" / "stray" / "SKILL.md"
        extra.parent.mkdir(parents=True)
        extra.write_text("x", encoding="utf-8")
        rc, out = self.run_tool("--check")
        self.assertEqual(1, rc)
        self.assertIn("extra file", out)
        shutil.rmtree(self.root / "plugins" / "process" / "skills")
        shutil.rmtree(self.root / "plugins" / "dev" / "skills")
        rc, out = self.run_tool("--check")
        self.assertEqual(1, rc)
        self.assertIn("missing copy", out)

    def test_security_json_overrides_lint(self):
        sec = self.root / "security.json"
        sec.write_text(json.dumps({"good-skill": {"flag": "blocked", "reasons": ["secret-jwt"]},
                                   "leaky-skill": {"flag": "ok", "reasons": []}}), encoding="utf-8")
        shutil.rmtree(self.root / "skills" / "leaky-skill")
        rc, out = self.run_tool("--security-json", str(sec))
        self.assertEqual(0, rc, out)
        self.assertFalse((self.root / "plugins" / "dev" / "skills" / "good-skill").exists())

    def test_category_without_plugin_fails(self):
        md = self.root / "skills" / "good-skill" / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8").replace("category: development", "category: infra"),
                      encoding="utf-8")
        rc, out = self.run_tool()
        self.assertEqual(1, rc)
        self.assertIn("has no plugin", out)

    @unittest.skipUnless((REPO / ".claude-plugin" / "marketplace.json").is_file(), "no marketplace.json in the repo")
    def test_repo_plugins_are_in_sync(self):
        self.assertEqual(0, bp.main(["--check"]))


if __name__ == "__main__":
    unittest.main()
