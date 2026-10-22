"""check_marketplace.py tests: a valid layout passes, typical manifest errors are caught."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import check_marketplace as cm  # noqa: E402

PLUGINS = ("process", "dev", "release")


class CheckMarketplaceTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.mp = self.root / ".claude-plugin" / "marketplace.json"
        self.mp.parent.mkdir(parents=True)
        self.data = {"name": "skillhub", "owner": {"name": "Test"},
                     "plugins": [{"name": p, "source": f"./plugins/{p}"} for p in PLUGINS]}
        self.save()
        for p in PLUGINS:
            pj = self.root / "plugins" / p / ".claude-plugin"
            pj.mkdir(parents=True)
            (pj / "plugin.json").write_text(json.dumps({"name": p}), encoding="utf-8")

    def save(self):
        self.mp.write_text(json.dumps(self.data), encoding="utf-8")

    def test_valid_layout_passes(self):
        self.assertEqual([], cm.check(self.root))

    @unittest.skipUnless((REPO / ".claude-plugin" / "marketplace.json").is_file(), "no marketplace.json in the repo")
    def test_repo_passes(self):
        self.assertEqual([], cm.check(REPO))

    def test_missing_owner_and_bad_name(self):
        del self.data["owner"]
        self.data["name"] = "Skill Hub"
        self.save()
        errors = "\n".join(cm.check(self.root))
        self.assertIn("owner.name", errors)
        self.assertIn("kebab-case", errors)

    def test_dotdot_and_missing_dir(self):
        self.data["plugins"][0]["source"] = "./../plugins/process"
        self.data["plugins"][1]["source"] = "./plugins/nope"
        self.save()
        errors = "\n".join(cm.check(self.root))
        self.assertIn('Path contains ".."', errors)
        self.assertIn("directory ./plugins/nope does not exist", errors)

    def test_manifest_name_mismatch_and_unlisted_plugin(self):
        pj = self.root / "plugins" / "dev" / ".claude-plugin" / "plugin.json"
        pj.write_text(json.dumps({"name": "develop"}), encoding="utf-8")
        (self.root / "plugins" / "stray").mkdir()
        errors = "\n".join(cm.check(self.root))
        self.assertIn("differs from the entry name", errors)
        self.assertIn("plugins/stray: not listed", errors)

    def test_invalid_json(self):
        self.mp.write_text("{", encoding="utf-8")
        self.assertIn("invalid JSON", "\n".join(cm.check(self.root)))


if __name__ == "__main__":
    unittest.main()
