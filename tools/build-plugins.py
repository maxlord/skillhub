#!/usr/bin/env python3
"""Build marketplace plugins: copy skills/<skill> to plugins/<plugin>/skills/<skill>.

Usage:
    tools/build-plugins.py [--check] [--security-json dist/security.json]

A skill's plugin is the `plugin` of its category (`metadata.category`) in `catalog/categories.yaml`; the plugin
must be listed in `.claude-plugin/marketplace.json` with a relative `source`. A skill flagged `blocked` by
security-lint (or by a ready `dist/security.json`) is left out of the build. `evals/` is not copied into a plugin.
`--check` writes nothing: exit code 1 if the copies under plugins/ differ from the build (edited by hand or not rebuilt).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import security_lint  # noqa: E402
import spec_lint  # noqa: E402

REPO = TOOLS.parent
SKIP_PARTS = {"evals", "__pycache__", ".DS_Store"}


class BuildError(Exception):
    pass


def load_plugins(root: Path) -> dict[str, Path]:
    """Plugin name to directory, from marketplace.json (relative sources only)."""
    data = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    out: dict[str, Path] = {}
    for entry in data.get("plugins", []):
        src = entry.get("source")
        if isinstance(src, str) and src.startswith("./"):
            out[entry["name"]] = root / src[2:]
    return out


def category_plugins(catalog: Path) -> dict[str, str]:
    data = spec_lint.load_yaml((catalog / "categories.yaml").read_text(encoding="utf-8")) or {}
    return {str(c["id"]): str(c["plugin"]) for c in data.get("categories", [])
            if isinstance(c, dict) and c.get("plugin")}


def skill_category(skill_dir: Path) -> str | None:
    fm_text, _, _ = spec_lint.split_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    fm = spec_lint.load_yaml(fm_text or "") or {}
    meta = fm.get("metadata") if isinstance(fm, dict) else None
    return str(meta["category"]) if isinstance(meta, dict) and meta.get("category") else None


def blocked_skills(root: Path, skill_dirs: list[Path], security_json: Path | None) -> dict[str, list[str]]:
    if security_json is not None:
        data = json.loads(security_json.read_text(encoding="utf-8"))
        return {k: v.get("reasons", []) for k, v in data.items() if v.get("flag") == "blocked"}
    verdicts = security_lint.lint(skill_dirs, root / "catalog" / "public-hosts.yaml")
    return {v.skill: v.reasons for v in verdicts if v.flag == "blocked"}


def skill_files(skill_dir: Path) -> dict[str, bytes]:
    files = {}
    for p in sorted(skill_dir.rglob("*")):
        rel = p.relative_to(skill_dir)
        if p.is_file() and not SKIP_PARTS.intersection(rel.parts):
            files[rel.as_posix()] = p.read_bytes()
    return files


def plan(root: Path, security_json: Path | None = None) -> tuple[dict[str, dict[str, bytes]], list[str]]:
    """Expected content: {plugin: {"<skill>/<rel>": bytes}} plus notes about skipped skills."""
    plugins = load_plugins(root)
    by_category = category_plugins(root / "catalog")
    skills_root = root / "skills"
    dirs = sorted(d for d in skills_root.iterdir() if (d / "SKILL.md").is_file()) if skills_root.is_dir() else []
    blocked = blocked_skills(root, dirs, security_json)
    expected: dict[str, dict[str, bytes]] = {name: {} for name in plugins}
    notes, errors = [], []
    for d in dirs:
        if d.name in blocked:
            notes.append(f"skipped {d.name}: security-lint blocked ({', '.join(blocked[d.name])})")
            continue
        category = skill_category(d)
        plugin = by_category.get(category or "")
        if plugin is None:
            errors.append(f"{d.name}: category {category!r} has no plugin in catalog/categories.yaml")
        elif plugin not in plugins:
            errors.append(f"{d.name}: plugin {plugin} is not in .claude-plugin/marketplace.json")
        else:
            for rel, data in skill_files(d).items():
                expected[plugin][f"{d.name}/{rel}"] = data
    if errors:
        raise BuildError("\n".join(errors))
    return expected, notes


def actual_files(plugin_dir: Path) -> dict[str, bytes]:
    base = plugin_dir / "skills"
    if not base.is_dir():
        return {}
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def diff(root: Path, expected: dict[str, dict[str, bytes]]) -> list[str]:
    plugins = load_plugins(root)
    out = []
    for name, want in expected.items():
        have = actual_files(plugins[name])
        prefix = f"plugins/{plugins[name].name}/skills"
        out += [f"missing copy: {prefix}/{k}" for k in sorted(want.keys() - have.keys())]
        out += [f"extra file: {prefix}/{k}" for k in sorted(have.keys() - want.keys())]
        out += [f"copy edited by hand: {prefix}/{k}" for k in sorted(want.keys() & have.keys()) if want[k] != have[k]]
    return out


def write(root: Path, expected: dict[str, dict[str, bytes]]) -> None:
    plugins = load_plugins(root)
    for name, files in expected.items():
        base = plugins[name] / "skills"
        if base.exists():
            shutil.rmtree(base)
        for rel, data in files.items():
            target = base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            src = root / "skills" / rel
            if src.stat().st_mode & 0o111:
                target.chmod(src.stat().st_mode & 0o777)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="only compare plugins/ with the build")
    ap.add_argument("--security-json", type=Path, help="read security-lint flags from a file instead of running the lint")
    ap.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        expected, notes = plan(args.root, args.security_json)
    except BuildError as exc:
        print(f"build-plugins: {exc}", file=sys.stderr)
        return 1
    for n in notes:
        print(f"build-plugins: {n}")
    summary = ", ".join(f"{p}: {len({k.split('/')[0] for k in f})}" for p, f in expected.items())
    if args.check:
        problems = diff(args.root, expected)
        for p in problems:
            print(f"build-plugins --check: {p}", file=sys.stderr)
        if problems:
            print("build-plugins --check: copies differ; run tools/build-plugins.py and commit",
                  file=sys.stderr)
            return 1
        print(f"build-plugins --check: ok ({summary})")
        return 0
    write(args.root, expected)
    print(f"build-plugins: built ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
