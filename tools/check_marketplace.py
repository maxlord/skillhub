#!/usr/bin/env python3
"""Check `.claude-plugin/marketplace.json` and each `plugin.json` without the claude CLI (fallback for `claude plugin validate .`).

Usage:
    tools/check_marketplace.py [ROOT]

Rules follow https://code.claude.com/docs/en/plugin-marketplaces: `name`, `owner.name`, a non-empty `plugins[]`;
each entry has a unique kebab-case `name` and a `source`; a relative `source` starts with `./`, has no `..` and
points to an existing directory; the plugin's `plugin.json` is valid JSON with the same `name`; every `plugins/*`
directory is listed in the marketplace. Exit code 1 on any error.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESERVED = {"claude-plugins-official", "claude-code-marketplace", "anthropic-marketplace", "anthropic-plugins"}


def _load(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path}: file does not exist")
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
    return None


def check(root: Path) -> list[str]:
    errors: list[str] = []
    data = _load(root / ".claude-plugin" / "marketplace.json", errors)
    if not isinstance(data, dict):
        return errors or ["marketplace.json: an object is expected"]
    name = data.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append("marketplace: `name` must be a kebab-case string")
    elif name in RESERVED:
        errors.append(f"marketplace: name {name!r} is reserved by Anthropic")
    owner = data.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("name"), str) or not owner["name"]:
        errors.append("marketplace: `owner.name` is required")
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append("marketplace: `plugins` must be a non-empty list")
        return errors
    seen: set[str] = set()
    listed: set[Path] = set()
    for i, entry in enumerate(plugins):
        where = f"plugins[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where}: an object is expected")
            continue
        pname = entry.get("name")
        if not isinstance(pname, str) or not NAME_RE.match(pname):
            errors.append(f"{where}: `name` must be a kebab-case string")
        elif pname in seen:
            errors.append(f"{where}: duplicate name {pname}")
        seen.add(str(pname))
        src = entry.get("source")
        if isinstance(src, dict):
            if "source" not in src:
                errors.append(f"{where}: the `source` object has no `source` field")
            continue
        if not isinstance(src, str) or not src.startswith("./"):
            errors.append(f"{where}: `source` must be a path from the marketplace root like ./plugins/<name>, or an object")
            continue
        if ".." in Path(src).parts:
            errors.append(f'{where}: Path contains "..": {src}')
            continue
        pdir = (root / src).resolve()
        listed.add(pdir)
        if not pdir.is_dir():
            errors.append(f"{where}: directory {src} does not exist")
            continue
        manifest = _load(pdir / ".claude-plugin" / "plugin.json", errors)
        if isinstance(manifest, dict):
            if manifest.get("name") != pname:
                errors.append(f"{where}: name in plugin.json ({manifest.get('name')!r}) differs from the entry name ({pname!r})")
        elif manifest is not None:
            errors.append(f"{where}: plugin.json must be an object")
    pl_root = root / "plugins"
    if pl_root.is_dir():
        for d in sorted(pl_root.iterdir()):
            if d.is_dir() and d.resolve() not in listed:
                errors.append(f"plugins/{d.name}: not listed in marketplace.json")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else REPO
    errors = check(root)
    for e in errors:
        print(f"check-marketplace: {e}", file=sys.stderr)
    if errors:
        return 1
    print("check-marketplace: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
