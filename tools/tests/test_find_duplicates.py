"""Tests for scripts/find-duplicates.py of the skill-creator skill, on fixtures (mechanics only)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO / "skills" / "skill-creator" / "scripts" / "find-duplicates.py"
SKILLS = Path(__file__).resolve().parent / "fixtures" / "duplicates" / "skills"

_spec = importlib.util.spec_from_file_location("find_duplicates", SCRIPT)
fd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fd)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--skills", str(SKILLS), *args],
                          capture_output=True, text=True)


class FindDuplicatesTest(unittest.TestCase):
    def test_review_pr_request_points_to_cluster_leader(self):
        r = run("--query", "make a skill about reviewing a PR")
        self.assertEqual(3, r.returncode, r.stderr)
        self.assertIn("review-by-complexity", r.stdout)
        self.assertIn("review-checklist", r.stdout)
        self.assertNotIn("retrospective", r.stdout)

    def test_ranking_prefers_leader(self):
        names = [i["name"] for i in fd.find("review pull requests", fd.load_skills(SKILLS), 0.3)]
        self.assertEqual("review-by-complexity", names[0])

    def test_unrelated_request_has_no_duplicates(self):
        r = run("--query", "a skill about publishing iOS builds to the App Store")
        self.assertEqual(0, r.returncode, r.stdout)

    def test_non_leader_match_suggests_leader(self):
        found = fd.find("security checklist", fd.load_skills(SKILLS), 0.3)
        self.assertEqual("review-checklist", found[0]["name"])
        self.assertEqual("review-by-complexity", found[0]["cluster_leader"])

    def test_fallback_frontmatter_parser_without_yaml(self):
        saved = sys.modules.get("yaml")
        sys.modules["yaml"] = None  # import yaml -> ImportError
        try:
            skills = fd.load_skills(SKILLS)
        finally:
            if saved is None:
                sys.modules.pop("yaml", None)
            else:
                sys.modules["yaml"] = saved
        by_name = {s["name"]: s for s in skills}
        self.assertTrue(by_name["review-by-complexity"]["leader"])
        self.assertEqual("review", by_name["review-checklist"]["cluster"])
        self.assertIn("review depth", by_name["review-by-complexity"]["description"])

    def test_missing_skills_dir_is_error(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--skills", "/nonexistent", "--query", "x"],
                           capture_output=True, text=True)
        self.assertEqual(2, r.returncode)


if __name__ == "__main__":
    unittest.main()
