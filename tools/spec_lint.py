#!/usr/bin/env python3
"""Spec-lint for SKILL.md: the Agent Skills spec plus the hub skill card (see README.md).

Usage:
    tools/spec_lint.py [--catalog DIR] [--no-git] [--json] SKILL_DIR|skills/ ...

Exit code 1 if there is at least one error (warnings do not fail).
Dependencies: python3 stdlib; pyyaml if installed (otherwise a built-in parser for simple YAML).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

try:  # pyyaml is optional
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised on machines without pyyaml
    yaml = None

REPO = Path(__file__).resolve().parent.parent

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_DESCRIPTION_SPEC = 1024
MAX_DESCRIPTION_HUB = 400
MAX_COMPATIBILITY = 500
MAX_LINES = 300
MAX_TOKENS = 4000

SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
# Claude Code extensions: allowed, but Codex does not understand them.
CLAUDE_FIELDS = {
    "when_to_use", "disable-model-invocation", "user-invocable", "context", "agent",
    "model", "paths", "hooks", "arguments",
}
CLAUDE_ONLY_BEHAVIOUR = {"context", "agent", "hooks"}

REQUIRED_METADATA = ("category", "owner", "maturity", "added", "updated", "projects")
KNOWN_METADATA = set(REQUIRED_METADATA) | {
    "source", "depends", "cluster", "leader", "decided-by", "review-by",
}
MATURITY = {"draft", "trial", "stable", "deprecated"}

ENV_CHECK_RE = re.compile(r"^##\s+(Environment check|Проверка окружения)\b", re.I | re.M)
H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
WHEN_RE = re.compile(r"\b(use when|when|whenever|if)\b", re.I)
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
CODE_REF_RE = re.compile(r"`((?:references|scripts|assets|evals)/[^`\s]+)`")

# Action verb at the start of the description: "Guides", "Reviews", "Creates", "Run".
# Base forms; the third person (-s/-es/-ies) is derived in starts_with_verb().
EN_VERBS = {
    "add", "apply", "audit", "build", "bump", "capture", "check", "choose", "close", "configure",
    "create", "cut", "decide", "define", "deploy", "describe", "document", "draft", "drive",
    "enforce", "ensure", "explain", "find", "fix", "gate", "generate", "guide", "handle", "help",
    "keep", "land", "lead", "lint", "list", "make", "manage", "merge", "open", "pick", "plan",
    "prepare", "produce", "publish", "rebase", "record", "release", "resolve", "review", "route",
    "run", "scaffold", "select", "set", "ship", "size", "split", "start", "stop", "sweep", "sync",
    "tag", "test", "track", "triage", "turn", "update", "use", "validate", "verify", "walk",
    "write",
}


@dataclass
class Issue:
    level: str  # "error" | "warning"
    skill: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper()} {self.skill}: {self.message}"


# --- YAML -----------------------------------------------------------------

def _scalar(raw: str):
    raw = raw.strip()
    if raw == "":
        return None
    if (raw[0] == raw[-1]) and raw[0] in "\"'" and len(raw) >= 2:
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    if DATE_RE.match(raw):
        return dt.date.fromisoformat(raw)
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if raw.startswith("[") and raw.endswith("]"):
        return [_scalar(x) for x in raw[1:-1].split(",") if x.strip()]
    return raw


def _strip_comment(line: str) -> str:
    """Strip a `# comment` outside quotes; a `#` without a preceding space is part of the value."""
    quote = None
    for idx, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (idx == 0 or line[idx - 1] in " \t"):
            return line[:idx].rstrip()
    return line.rstrip()


def _mini_yaml(text: str) -> dict:
    """Parse a YAML subset: `k: v`, `k: >`/`|` blocks, a one-level nested mapping, `- item`.

    Comments are stripped only outside quotes and outside `>`/`|` blocks (there `#` is text).
    """
    out: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = _strip_comment(lines[i])
        if not line.strip():
            i += 1
            continue
        if line.startswith(" "):
            raise ValueError(f"unexpected indent: {line!r}")
        key, _, rest = line.partition(":")
        key, rest = key.strip(), rest.strip()
        i += 1
        block = []
        while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
            block.append(lines[i])
            i += 1
        while block and not block[-1].strip():
            block.pop()
        if rest in (">", "|", ">-", "|-"):
            parts = [b.strip() for b in block]
            joined = (" " if rest.startswith(">") else "\n").join(p for p in parts if p or rest.startswith("|"))
            out[key] = joined if rest.endswith("-") else joined + "\n"
            continue
        block = [c for c in (_strip_comment(b) for b in block) if c.strip()]
        if rest:
            out[key] = _scalar(rest)
        elif block and block[0].strip().startswith("- "):
            items: list = []
            for b in (b.strip() for b in block):
                item = b[2:] if b.startswith("- ") else None
                text_kv = item if item is not None else b
                is_kv = re.match(r"^[\w.-]+:(\s|$)", text_kv)
                if item is not None:
                    items.append({} if is_kv else _scalar(item))
                if is_kv and isinstance(items[-1], dict):
                    k, _, v = text_kv.partition(":")
                    items[-1][k.strip()] = _scalar(v)
            out[key] = items
        elif block:
            sub = {}
            for b in block:
                k, _, v = b.strip().partition(":")
                sub[k.strip()] = _scalar(v)
            out[key] = sub
        else:
            out[key] = None
    return out


def load_yaml(text: str):
    if yaml is not None:
        return yaml.safe_load(text)
    return _mini_yaml(text)


def split_frontmatter(text: str):
    """Return (frontmatter_text, body, body_start_line) or (None, text, 1)."""
    if not text.startswith("---"):
        return None, text, 1
    lines = text.splitlines(keepends=True)
    if lines[0].strip() != "---":
        return None, text, 1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "".join(lines[1:idx]), "".join(lines[idx + 1:]), idx + 2
    return None, text, 1


def load_catalog_ids(path: Path, key: str) -> set[str] | None:
    """`categories.yaml`/`owners.yaml`: {key: [ {id: ..}, .. ]} or {key: [str, ..]} or {id: {...}}."""
    if not path.is_file():
        return None
    data = load_yaml(path.read_text(encoding="utf-8")) or {}
    items = data.get(key, data) if isinstance(data, dict) else data
    ids: set[str] = set()
    if isinstance(items, dict):
        ids = {str(k) for k in items}
    elif isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and "id" in it:
                ids.add(str(it["id"]))
            elif isinstance(it, str):
                ids.add(it)
    return ids


# --- checks -----------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rough estimate: ~4 UTF-8 bytes per token."""
    return (len(text.encode("utf-8")) + 3) // 4


def starts_with_verb(description: str) -> bool:
    m = re.match(r"\s*([A-Za-z]+)", description)
    if not m:
        return False
    w = m.group(1).lower()
    candidates = {w}
    if w.endswith("ies"):
        candidates.add(w[:-3] + "y")  # applies -> apply
    if w.endswith("es"):
        candidates.add(w[:-2])  # fixes -> fix
    if w.endswith("s"):
        candidates.add(w[:-1])  # guides -> guide, cuts -> cut
    return bool(candidates & EN_VERBS)


def git_date(skill_dir: Path) -> str | None:
    """Date for `metadata.updated`: today if the directory is dirty, else the author date of the last commit."""
    try:
        top = subprocess.run(["git", "-C", str(skill_dir), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    dirty = subprocess.run(["git", "-C", top, "status", "--porcelain", "--", str(skill_dir.resolve())],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        return dt.date.today().isoformat()
    out = subprocess.run(["git", "-C", top, "log", "-1", "--format=%as", "--", str(skill_dir.resolve())],
                         capture_output=True, text=True).stdout.strip()
    return out or None


def _as_str(value):
    if isinstance(value, dt.date):
        return value.isoformat()
    return value


def lint_skill(skill_dir: Path, catalog: Path | None = None, use_git: bool = True) -> list[Issue]:
    skill_dir = Path(skill_dir)
    catalog = catalog if catalog is not None else REPO / "catalog"
    label = skill_dir.name
    issues: list[Issue] = []

    def err(msg):
        issues.append(Issue("error", label, msg))

    def warn(msg):
        issues.append(Issue("warning", label, msg))

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        err("no SKILL.md")
        return issues
    text = skill_md.read_text(encoding="utf-8")
    fm_text, body, _ = split_frontmatter(text)
    if fm_text is None:
        err("no frontmatter between `---` lines")
        return issues
    try:
        fm = load_yaml(fm_text)
    except Exception as exc:  # noqa: BLE001 - any parse error
        err(f"frontmatter is not valid YAML: {exc}")
        return issues
    if not isinstance(fm, dict):
        err("frontmatter must be a mapping")
        return issues

    # top-level fields
    for key in fm:
        if key in SPEC_FIELDS:
            continue
        if key in CLAUDE_FIELDS:
            if key in CLAUDE_ONLY_BEHAVIOUR:
                warn(f"field `{key}` is understood only by Claude Code; Codex will not see it, so repeat the meaning in the text")
            continue
        err(f"invalid frontmatter field `{key}` (Agent Skills spec + Claude Code extensions)")

    # name
    name = fm.get("name")
    if not isinstance(name, str) or not name:
        err("no `name`")
    else:
        if len(name) > 64:
            err(f"`name` is longer than 64 characters ({len(name)})")
        if not NAME_RE.match(name):
            err("`name` allows only a-z0-9 and single `-`, no leading or trailing `-`")
        if name != skill_dir.name:
            err(f"`name` ({name}) does not match the directory name ({skill_dir.name})")

    # description
    desc = fm.get("description")
    when = fm.get("when_to_use")
    if not isinstance(desc, str) or not desc.strip():
        err("no `description`")
    else:
        desc = desc.strip()
        if len(desc) > MAX_DESCRIPTION_SPEC:
            err(f"`description` is longer than {MAX_DESCRIPTION_SPEC} characters (spec limit): {len(desc)}")
        elif len(desc) > MAX_DESCRIPTION_HUB:
            err(f"`description` is longer than {MAX_DESCRIPTION_HUB} characters (hub limit): {len(desc)}")
        if not starts_with_verb(desc):
            err("`description` must start with an action verb (\"Guides…\", \"Reviews…\", \"Creates…\")")
        if not WHEN_RE.search(desc) and not when:
            err("`description` does not say when to use the skill (\"Use when…\")")
    if isinstance(when, str) and isinstance(desc, str) and len(desc) + len(when) > 1536:
        err("`description` + `when_to_use` is longer than 1536 characters; Claude Code will truncate it")

    compat = fm.get("compatibility")
    if compat is not None and (not isinstance(compat, str) or len(compat) > MAX_COMPATIBILITY):
        err(f"`compatibility` must be a string of at most {MAX_COMPATIBILITY} characters")
    if "version" in fm:
        err("field `version` is forbidden: always the latest from main")

    # metadata
    meta = fm.get("metadata")
    maturity = None
    if not isinstance(meta, dict):
        err("no `metadata` (skill card)")
        meta = {}
    norm: dict[str, str] = {}
    for key, value in meta.items():
        value = _as_str(value)
        if not isinstance(value, str):
            err(f"`metadata.{key}` must be a string (spec: string to string); quote the value")
            continue
        norm[str(key)] = value
        if key not in KNOWN_METADATA:
            warn(f"unknown field `metadata.{key}`")
    for key in REQUIRED_METADATA:
        if key in meta and key not in norm:
            continue  # already a type error
        if not norm.get(key):
            err(f"no `metadata.{key}`")

    categories = load_catalog_ids(catalog / "categories.yaml", "categories")
    if norm.get("category"):
        if categories is None:
            warn(f"no {catalog / 'categories.yaml'}: nothing to check the category against")
        elif norm["category"] not in categories:
            err(f"`metadata.category` ({norm['category']}) is not in catalog/categories.yaml")
    owners = load_catalog_ids(catalog / "owners.yaml", "owners")
    if norm.get("owner") and owners is not None and norm["owner"] not in owners:
        err(f"`metadata.owner` ({norm['owner']}) is not in catalog/owners.yaml")

    maturity = norm.get("maturity")
    if maturity and maturity not in MATURITY:
        err(f"`metadata.maturity` must be one of {sorted(MATURITY)}")
    for key in ("added", "updated", "review-by"):
        if norm.get(key) and not DATE_RE.match(norm[key]):
            err(f"`metadata.{key}` must be a date YYYY-MM-DD")
    if all(DATE_RE.match(norm.get(k, "")) for k in ("added", "updated")) and norm["added"] > norm["updated"]:
        err("`metadata.added` is later than `metadata.updated`")
    if norm.get("projects"):
        bad = [p for p in norm["projects"].split(",") if not NAME_RE.match(p.strip())]
        if bad:
            err(f"`metadata.projects` must be comma-separated names, bad ones: {bad}")
    if norm.get("depends"):
        for dep in norm["depends"].split(","):
            if not NAME_RE.match(dep.strip()):
                err(f"`metadata.depends`: bad skill name {dep.strip()!r}")
    if "leader" in norm:
        if norm["leader"] not in ("true", "false"):
            err("`metadata.leader` must be \"true\" or \"false\"")
        if not norm.get("cluster"):
            err("`metadata.leader` without `metadata.cluster`")
    if use_git and DATE_RE.match(norm.get("updated", "")):
        expected = git_date(skill_dir)
        if expected and expected != norm["updated"]:
            err(f"`metadata.updated` ({norm['updated']}) differs from the directory's git log date ({expected})")

    # size
    n_lines = len(text.splitlines())
    if n_lines > MAX_LINES:
        err(f"SKILL.md is longer than {MAX_LINES} lines ({n_lines}); move history and rationale to references/")
    tokens = estimate_tokens(text)
    if tokens > MAX_TOKENS:
        err(f"SKILL.md is about {tokens} tokens (> {MAX_TOKENS})")

    # links: one level from SKILL.md, inside the directory, file exists
    targets = [m.group(1) for m in MD_LINK_RE.finditer(body)] + [m.group(1) for m in CODE_REF_RE.finditer(body)]
    for target in targets:
        if re.match(r"^[a-z]+://|^mailto:|^#", target):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        parts = Path(path).parts
        if path.startswith("/") or ".." in parts:
            err(f"link `{target}` points outside the skill directory")
            continue
        if len(parts) > 2:
            err(f"link `{target}` is deeper than one level from SKILL.md")
            continue
        if not (skill_dir / path).exists():
            err(f"link `{target}`: file does not exist")

    # self-containment: the "Environment check" section comes first
    h2 = H2_RE.findall(body)
    if not ENV_CHECK_RE.search(body):
        (warn if maturity == "draft" else err)("no `## Environment check` section (self-containment criterion)")
    elif h2 and not re.match(r"(Environment check|Проверка окружения)", h2[0], re.I):
        (warn if maturity == "draft" else err)("`## Environment check` must be the first section")

    return issues


def find_skill_dirs(paths: list[Path]) -> list[Path]:
    dirs: list[Path] = []
    for p in paths:
        if (p / "SKILL.md").is_file():
            dirs.append(p)
        elif p.is_dir():
            dirs.extend(sorted(d for d in p.iterdir() if d.is_dir() and not d.name.startswith(".")))
        else:
            dirs.append(p)
    return dirs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", type=Path, default=[REPO / "skills"])
    ap.add_argument("--catalog", type=Path, default=REPO / "catalog", help="directory with categories.yaml/owners.yaml")
    ap.add_argument("--no-git", action="store_true", help="do not compare metadata.updated with git log")
    ap.add_argument("--json", action="store_true", help="print a JSON list")
    args = ap.parse_args(argv)

    issues: list[Issue] = []
    dirs = find_skill_dirs(args.paths)
    for d in dirs:
        issues.extend(lint_skill(d, args.catalog, use_git=not args.no_git))
    if args.json:
        print(json.dumps([asdict(i) for i in issues], ensure_ascii=False, indent=2))
    else:
        for i in issues:
            print(i)
        n_err = sum(i.level == "error" for i in issues)
        print(f"spec-lint: {len(dirs)} skill(s), {n_err} error(s), {len(issues) - n_err} warning(s)")
    return 1 if any(i.level == "error" for i in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
