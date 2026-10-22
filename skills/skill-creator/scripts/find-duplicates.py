#!/usr/bin/env python3
"""Finds hub skills similar to the intended one: name, description, cluster and key body phrases.

Usage:
    find-duplicates.py --query "make a skill about PR review" [--name my-skill] [--skills DIR] [--json] [--threshold 0.3]

DIR defaults to `skills/` at the root of the git repo of the current directory (otherwise `./skills`).
Output: "similar: X (leader of cluster c), Y (cluster c, leader - Z)" plus advice to edit the leader, or "no similar skills".
Exit code: 0 - none found, 3 - similar skills found, 2 - usage error. Stdlib only, pyyaml optional.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

STOP = {
    "make", "create", "add", "new", "need", "needed", "skill", "skills", "about", "for", "the", "and", "with",
    "use", "when", "how", "what", "this", "that", "from", "into", "its", "are", "any", "all", "only", "without",
    "please", "want", "build", "write",
}
# Synonyms and near-forms map to one key so that "retro" matches "retrospective".
SYNONYMS = {
    "retrospective": "retro", "retrospectives": "retro", "deploy": "release", "deployment": "release",
    "tests": "test", "testing": "test", "pr": "pull", "prs": "pull", "specs": "spec", "stories": "story",
}
FIELD_WEIGHT = {"name": 3.0, "cluster": 3.0, "description": 2.0, "body": 1.0}
WORD_RE = re.compile(r"[a-z0-9]+", re.I)
PHRASE_RE = re.compile(r"^#{1,3}\s+(.+)$|\*\*(.+?)\*\*|^\s*\d+\.\s+(.+)$", re.M)


def stem(word: str) -> str:
    w = word.lower()
    if w in SYNONYMS:
        return SYNONYMS[w]
    return SYNONYMS.get(w[:6], w[:6])


def tokens(text: str) -> set[str]:
    out = set()
    for w in WORD_RE.findall(text or ""):
        if w.lower() in STOP or len(w) < 2:
            continue
        out.add(stem(w))
    return out


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm_text, body = text[3:end], text[end + 4:]
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(fm_text)
        return (data if isinstance(data, dict) else {}), body
    except Exception:  # noqa: BLE001 - no pyyaml or unusual YAML: parse by hand
        pass
    data: dict = {}
    nested, block = None, None
    for line in fm_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        m = re.match(r"\s*([\w-]+):\s*(.*)$", line)
        if block is not None and indent > 0:
            data[block] = (data.get(block, "") + " " + line.strip()).strip()
            continue
        block = None
        if not m:
            continue
        k, v = m.group(1), m.group(2).split(" #")[0].strip().strip("\"'")
        if indent == 0:
            nested = None
            if v in (">", "|", ">-", "|-"):
                block, data[k] = k, ""
            elif v:
                data[k] = v
            else:
                nested = data[k] = {}
        elif nested is not None:
            nested[k] = v
    return data, body


def load_skills(skills_dir: Path) -> list[dict]:
    skills = []
    for md in sorted(skills_dir.glob("*/SKILL.md")):
        fm, body = parse_frontmatter(md.read_text(encoding="utf-8"))
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        phrases = " ".join(next(g for g in m.groups() if g) for m in PHRASE_RE.finditer(body))
        skills.append({
            "name": str(fm.get("name") or md.parent.name),
            "description": str(fm.get("description") or ""),
            "cluster": str(meta.get("cluster") or ""),
            "leader": str(meta.get("leader") or "").lower() == "true",
            "body": phrases,
        })
    return skills


def score(query: set[str], skill: dict) -> tuple[float, list[str]]:
    if not query:
        return 0.0, []
    fields = {f: tokens(skill[f].replace("-", " ")) for f in FIELD_WEIGHT}
    total, hits = 0.0, []
    for t in sorted(query):
        best = max((FIELD_WEIGHT[f] for f, toks in fields.items() if t in toks), default=0.0)
        if best:
            hits.append(t)
        total += best
    return total / (len(query) * max(FIELD_WEIGHT.values())), hits


def find(query_text: str, skills: list[dict], threshold: float) -> list[dict]:
    q = tokens(query_text.replace("-", " "))
    leaders = {s["cluster"]: s["name"] for s in skills if s["cluster"] and s["leader"]}
    found = []
    for s in skills:
        sc, hits = score(q, s)
        if sc >= threshold:
            found.append({"name": s["name"], "score": round(sc, 2), "hits": hits, "cluster": s["cluster"],
                          "leader": s["leader"], "cluster_leader": leaders.get(s["cluster"])})
    return sorted(found, key=lambda x: (-x["score"], not x["leader"], x["name"]))


def describe(item: dict) -> str:
    if item["leader"]:
        return f"{item['name']} (leader of cluster {item['cluster']})"
    if item["cluster"]:
        lead = item["cluster_leader"] or "none - assign one"
        return f"{item['name']} (cluster {item['cluster']}, leader - {lead})"
    return item["name"]


def default_skills_dir() -> Path:
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             check=True).stdout.strip()
        return Path(top) / "skills"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path("skills")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--query", default="", help="the user request or the purpose of the future skill")
    ap.add_argument("--name", default="", help="intended skill name")
    ap.add_argument("--skills", type=Path, help="hub skills directory")
    ap.add_argument("--threshold", type=float, default=0.3)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    skills_dir = args.skills or default_skills_dir()
    if not skills_dir.is_dir():
        print(f"find-duplicates: no directory {skills_dir}", file=sys.stderr)
        return 2
    found = find(f"{args.name} {args.query}", load_skills(skills_dir), args.threshold)
    if args.json:
        print(json.dumps(found, ensure_ascii=False, indent=2))
    elif not found:
        print("no similar skills - a new skill can be created")
    else:
        print("similar: " + ", ".join(describe(i) for i in found))
        top = found[0]
        target = top["name"] if top["leader"] or not top["cluster_leader"] else top["cluster_leader"]
        print(f"suggestion: edit {target} instead of adding a new skill")
        for i in found:
            print(f"  {i['name']}: score {i['score']}, matched: {', '.join(i['hits'])}")
    return 3 if found else 0


if __name__ == "__main__":
    sys.exit(main())
