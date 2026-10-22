"""validate.py and new-skill.sh tests: the scaffold passes both lints, an offender fails the check."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import validate  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


class ValidateTest(unittest.TestCase):
    def test_good_spec_fixture_passes(self):
        good = FIX / "spec" / "good" / "good-skill"
        self.assertEqual(0, validate.main(["--no-git", "--catalog", str(FIX / "spec" / "catalog"), str(good)]))

    def test_leaky_fixture_fails(self):
        bad = FIX / "security" / "bad" / "leaky-skill"
        self.assertEqual(1, validate.main(["--no-git", "--catalog", str(FIX / "spec" / "catalog"), str(bad)]))

    def test_new_skill_scaffold_validates(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(REPO / "tools", tmp / "tools", ignore=shutil.ignore_patterns("__pycache__", "tests"))
        shutil.copytree(FIX / "spec" / "catalog", tmp / "catalog")
        subprocess.run([str(tmp / "tools" / "new-skill.sh"), "demo-skill", "--category", "process"],
                       check=True, capture_output=True)
        rc = subprocess.run([sys.executable, str(tmp / "tools" / "validate.py"), "--no-git",
                             str(tmp / "skills" / "demo-skill")], capture_output=True, text=True)
        self.assertEqual(0, rc.returncode, rc.stdout + rc.stderr)
        dup = subprocess.run([str(tmp / "tools" / "new-skill.sh"), "demo-skill"], capture_output=True)
        self.assertEqual(1, dup.returncode)


if __name__ == "__main__":
    unittest.main()
