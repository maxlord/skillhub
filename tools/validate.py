#!/usr/bin/env python3
"""Validate hub skills: spec-lint (Agent Skills spec and skill card) + security-lint (secrets, addresses, dangerous operations).

Usage:
    tools/validate.py [--no-git] [--security-out dist/security.json] [paths ...]   # defaults to skills/

Exit code 1 if spec-lint finds an error or security-lint flags a skill `blocked`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import security_lint  # noqa: E402
import spec_lint  # noqa: E402

REPO = TOOLS.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", type=Path, default=[REPO / "skills"])
    ap.add_argument("--catalog", type=Path, default=REPO / "catalog")
    ap.add_argument("--no-git", action="store_true", help="do not compare metadata.updated with git log")
    ap.add_argument("--security-out", type=Path, help="write security-lint flags (dist/security.json)")
    args = ap.parse_args(argv)

    dirs = spec_lint.find_skill_dirs(args.paths)
    if not dirs:
        print("validate: no skills found", file=sys.stderr)
        return 1

    spec_issues = []
    for d in dirs:
        spec_issues.extend(spec_lint.lint_skill(d, args.catalog, use_git=not args.no_git))
    verdicts = security_lint.lint(dirs, args.catalog / "public-hosts.yaml")

    for i in spec_issues:
        print(f"spec     {i}")
    for v in verdicts:
        for f in v.findings:
            print(f"security BLOCKED {v.skill}: {f}")
    if args.security_out:
        args.security_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {v.skill: {"flag": v.flag, "reasons": v.reasons} for v in verdicts}
        args.security_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_err = sum(i.level == "error" for i in spec_issues)
    n_warn = len(spec_issues) - n_err
    n_blocked = sum(v.flag == "blocked" for v in verdicts)
    print(f"validate: {len(dirs)} skill(s); spec-lint: {n_err} error(s), {n_warn} warning(s); "
          f"security-lint: {n_blocked} blocked")
    return 1 if n_err or n_blocked else 0


if __name__ == "__main__":
    sys.exit(main())
