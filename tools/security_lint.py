#!/usr/bin/env python3
"""Security-lint for skills: secrets, tokens in curl/wget, internal addresses, dangerous operations without a stop point.

Usage:
    tools/security_lint.py [--hosts catalog/public-hosts.yaml] [--out dist/security.json] [--json] PATH ...

PATH is a skill directory (with SKILL.md), a directory of skills (`skills/`) or a single file (a draft).
One flag per skill: `ok` or `blocked` plus reasons. Exit code 1 if any skill is `blocked`.
Found values are masked in the output, so the report can go into a PR or CI log.
Suppress a finding on a line with a comment on the same line: `security-lint: allow <rule> - <reason>`.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {"", ".md", ".txt", ".sh", ".py", ".yaml", ".yml", ".json", ".toml", ".js", ".ts",
                 ".go", ".kt", ".env", ".conf", ".cfg", ".ini", ".html", ".j2", ".tmpl"}
STOP_WINDOW = 3  # lines before/after a dangerous operation where a stop point is looked for


@dataclass
class Finding:
    rule: str
    file: str
    line: int
    excerpt: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: [{self.rule}] {self.excerpt}"


@dataclass
class Verdict:
    skill: str
    flag: str = "ok"
    reasons: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


# --- rules ---------------------------------------------------------------------

SECRET_PATTERNS = [
    ("secret-private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*(PRIVATE )?KEY( BLOCK)?-----")),
    ("secret-anthropic-openai-key", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}")),
    ("secret-github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("secret-aws-key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("secret-google-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("secret-slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("secret-telegram-bot-token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("secret-jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    # token=..., password: ..., api_key = "..." with a literal value (not $VAR, not <placeholder>)
    ("secret-assignment", re.compile(
        r"(?i)\b(token|access_token|api[_-]?key|secret|passw(or)?d|pwd)\b[\"']?\s*[:=]\s*[\"']?"
        r"(?![$<{(\[*]|\.\.\.|…|\"|'|$)([^\s\"'`,;)]{6,})")),
]
# A .secrets/* path followed by content: `.secrets/x: value`
SECRETS_CONTENT = re.compile(r"\.secrets/[\w.-]+\s*(=|:)\s*\S{6,}")
ASK_TOKEN = re.compile(
    r"(?i)\b(встав(ь|ьте|ляй)|введи(те)?|укажи(те)?|скопируй|paste|enter|provide)\s+(сюда\s+|here\s+|свой\s+|your\s+|the\s+)*"
    r"(api[ -]?)?(токен|token|пароль|password|ключ|key|секрет|secret)\b")
CURL = re.compile(r"\b(curl|wget|http|xh)\b")
# Authorization header: value is an optional scheme + token. A literal token is not $VAR/${VAR}/$(...), not a <placeholder>.
AUTH_HEADER = re.compile(r"(?i)\b(authorization|private-token|x-api-key|x-auth-token|api-key)\s*:\s*([^\"'\n]*)")
CURL_TOKEN_HEADER = re.compile(r"(?i)(?:-H|--header)\s*[\"']?\s*token\s*:\s*([^\"'\n]*)")
AUTH_SCHEMES = {"bearer", "token", "basic"}
CURL_URL_TOKEN = re.compile(r"(?i)[?&](access_token|token|api_key|key|private_token)=(?!\$)([^\s&\"']{6,})")
CURL_USER = re.compile(r"(?:^|\s)(-u|--user)\s+[\"']?[^\s:\"']+:(?!\$)([^\s\"'@]{4,})")
WGET_PASS = re.compile(r"(?i)--(http-)?password=(?!\$)\S{4,}")

IPV4 = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.]*\d)(?::(\d{2,5}))?")
SSH_CMD = re.compile(r"\b(ssh|scp|sftp|rsync|autossh)\b")
SSH_PORT = re.compile(r"\b(ssh|scp|sftp|autossh)\b[^\n|;&]*?\s-(p|P)\s*(\d{2,5})")
SSH_PORT_CFG = re.compile(r"(?i)^\s*Port\s+(\d{2,5})\s*$")
SSH_TUNNEL = re.compile(r"\b(ssh|autossh)\b[^\n|;&]*?\s-[A-Za-z]*[LRD]\s*[\[\w.:-]*\d")
USER_AT_HOST = re.compile(r"(?<![\w.+-])([A-Za-z_][\w.-]*)@([A-Za-z0-9][\w.-]*)")
SSH_BARE_HOST = re.compile(
    r"\bssh\s+(?:-[A-Za-z]+(?:\s+(?!-)[^\s-][^\s]*)?\s+)*(?![$\"'<{-])([A-Za-z][\w.-]+)(?=\s|$)")
TLDS = ("ru|com|net|org|io|dev|app|club|ai|me|co|cloud|local|internal|lan|xyz|info|tech|site|online|pro|su|"
        "rf|de|fi|nl|eu|us|uk")
HOSTNAME = re.compile(rf"(?<![\w@/.-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:{TLDS}))(?![\w-])", re.I)
# `}` and `]` are not part of the host: `${GITEA_URL:-https://host}` is a shell variable default.
URL_HOST = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://(?:[^\s/@]+@)?([^\s/:?#\"'`)>}\]]+)")

DANGEROUS = [
    ("danger-rm-rf", re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-r\s+-f|-f\s+-r|--recursive\s+--force)\b")),
    ("danger-push-force", re.compile(r"\bpush\b[^\n]*\s(--force(-with-lease)?|-f)\b")),
    ("danger-image-prune-all", re.compile(r"\b(image|system|builder)\s+prune\b[^\n]*\s(-a\w*|--all)\b")),
]
COMPOSE_UP = re.compile(r"\bcompose(?:\s+[^\s|;&]+)*?\s+up\b")
# Evidence that the image is pinned: a `*_IMAGE=` variable, `--no-build`, or an `image@sha256:` digest.
PINNED_IMAGE = re.compile(r"\b[A-Z][A-Z0-9_]*_IMAGE\s*=|--no-build\b|\bimage@sha256\b|@sha256:")
STOP_MARKER = re.compile(
    r"(?i)(stop|confirm|\bask\b|only on (the )?word|wait for (the )?owner|wait for|human|approval|approve"
    r"|стоп|подтвер|спроси|человек)")
ALLOW = re.compile(r"security-lint:\s*allow\s+([\w,-]+)")


# --- host catalog -----------------------------------------------------------------

def load_public_hosts(path: Path) -> dict[str, set[str]]:
    data: dict[str, set[str]] = {"hosts": set(), "domains": set(), "ips": set()}
    if not path.is_file():
        return data
    key = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        m = re.match(r"^([\w-]+):\s*$", line)
        if m:
            key = m.group(1)
            data.setdefault(key, set())
            continue
        m = re.match(r"^\s+-\s+[\"']?([^\"'\s]+)", line)
        if m and key:
            data[key].add(m.group(1).lower())
    return data


def header_token_literal(value: str) -> str | None:
    """Return the literal token from a header value, or None (variable, placeholder, empty)."""
    words = value.strip().split()
    if words and words[0].lower() in AUTH_SCHEMES:
        words = words[1:]
    if not words:
        return None
    tok = words[0]
    if tok[0] in "$<{[(`*" or tok.startswith("…") or tok.startswith("...") or len(tok) < 6:
        return None
    return tok


def auth_literals(line: str, curl: bool) -> list[str]:
    found = [m.group(2) for m in AUTH_HEADER.finditer(line)]
    if curl:
        found += [m.group(1) for m in CURL_TOKEN_HEADER.finditer(line)]
    return [t for t in (header_token_literal(v) for v in found) if t]


def host_allowed(host: str, pub: dict[str, set[str]]) -> bool:
    host = host.lower().rstrip(".")
    if host in pub["hosts"] or host in pub.get("ips", set()):
        return True
    return any(host == d or host.endswith("." + d) for d in pub["domains"])


# --- masking --------------------------------------------------------------------

def mask(value: str) -> str:
    if IPV4.fullmatch(value):
        parts = value.split(".")
        return f"{parts[0]}.x.x.x"
    if len(value) <= 4:
        return "***"
    return value[:3] + "***"


def mask_line(line: str) -> str:
    out = IPV4.sub(lambda m: mask(m.group(1)) + (":" + "*" * len(m.group(2)) if m.group(2) else ""), line)
    for _, rx in SECRET_PATTERNS:
        out = rx.sub(lambda m: m.group(0)[:4] + "***", out)
    out = re.sub(r"(-p|-P|Port)\s*(\d{2,5})", lambda m: m.group(1) + " " + "*" * len(m.group(2)), out)
    out = USER_AT_HOST.sub(lambda m: m.group(1)[:1] + "***@" + m.group(2), out)
    for tok in auth_literals(out, curl=True):
        out = out.replace(tok, tok[:3] + "***")
    for rx in (CURL_URL_TOKEN, CURL_USER, WGET_PASS, SECRET_PATTERNS[-1][1]):
        out = rx.sub(lambda m: m.group(0)[: m.start(m.lastindex) - m.start(0)] + "***"
                     if m.lastindex else m.group(0)[:8] + "***", out)
    # long key-like strings (letters + digits, 16+ characters)
    out = re.sub(r"[A-Za-z0-9_+/=-]{16,}", lambda m: m.group(0)[:3] + "***"
                 if re.search(r"\d", m.group(0)) and re.search(r"[A-Za-z]", m.group(0)) else m.group(0), out)
    out = out.strip()
    return out if len(out) <= 120 else out[:117] + "..."


# --- file scan ---------------------------------------------------------------------

def scan_text(text: str, rel: str, pub: dict[str, set[str]]) -> list[Finding]:
    lines = text.splitlines()
    found: list[Finding] = []

    def add(rule: str, idx: int):
        allow = ALLOW.search(lines[idx])
        if allow and (rule in allow.group(1).split(",") or rule.split("-")[0] in allow.group(1).split(",")):
            return
        if not any(f.rule == rule and f.line == idx + 1 for f in found):
            found.append(Finding(rule, rel, idx + 1, mask_line(lines[idx])))

    def near_stop(idx: int) -> bool:
        lo, hi = max(0, idx - STOP_WINDOW), min(len(lines), idx + STOP_WINDOW + 1)
        return any(STOP_MARKER.search(lines[j]) for j in range(lo, hi))

    for i, line in enumerate(lines):
        # secrets
        for rule, rx in SECRET_PATTERNS:
            if rx.search(line):
                add(rule, i)
        if SECRETS_CONTENT.search(line):
            add("secret-dotsecrets-content", i)
        if ASK_TOKEN.search(line):
            add("ask-for-token", i)
        # curl/wget with a literal token
        is_curl = bool(CURL.search(line))
        if is_curl and (auth_literals(line, curl=True) or CURL_URL_TOKEN.search(line)
                        or CURL_USER.search(line) or WGET_PASS.search(line)):
            add("curl-token-literal", i)
        elif not is_curl and auth_literals(line, curl=False):
            add("auth-header-literal", i)
        # IP
        for m in IPV4.finditer(line):
            ip = m.group(1)
            try:
                ipaddress.IPv4Address(ip)
            except ValueError:
                continue
            if ip not in pub["ips"]:
                add("internal-ip", i)
        # SSH: port, tunnel, account, bare host
        m = SSH_PORT.search(line)
        if m and m.group(3) != "22":
            add("ssh-nonstandard-port", i)
        m = SSH_PORT_CFG.match(line)
        if m and m.group(1) != "22":
            add("ssh-nonstandard-port", i)
        if SSH_TUNNEL.search(line):
            add("ssh-tunnel", i)
        if SSH_CMD.search(line):
            for um in USER_AT_HOST.finditer(line):
                if not host_allowed(um.group(2), pub):
                    add("ssh-account", i)
            for hm in SSH_BARE_HOST.finditer(line):
                h = hm.group(1)
                if "@" not in h and not host_allowed(h, pub) and not IPV4.fullmatch(h):
                    add("ssh-host-alias", i)
        # hosts
        hosts = {h for h in URL_HOST.findall(line)} | {h for h in HOSTNAME.findall(line)}
        for h in hosts:
            h = h.split(":")[0].strip(".").lower()
            if not h or IPV4.fullmatch(h) or "." not in h or h.startswith("$") or "<" in h or "{" in h:
                continue
            if not re.search(rf"\.({TLDS})$", h, re.I) and not URL_HOST.search(line):
                continue
            if not host_allowed(h, pub):
                add("internal-host", i)
        # dangerous operations without a stop point
        for rule, rx in DANGEROUS:
            if rx.search(line) and not near_stop(i):
                add(rule, i)
        if COMPOSE_UP.search(line):
            lo = max(0, i - STOP_WINDOW)
            if not any(PINNED_IMAGE.search(lines[j]) for j in range(lo, i + 1)):
                add("danger-compose-up-without-pinned-image", i)
    return found


def iter_files(root: Path):
    if root.is_file():
        yield root
        return
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and "__pycache__" not in p.parts:
            yield p


def scan_unit(path: Path, pub: dict[str, set[str]]) -> Verdict:
    v = Verdict(skill=path.stem if path.is_file() else path.name)
    base = path.parent if path.is_file() else path
    for f in iter_files(path):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        v.findings.extend(scan_text(text, str(f.relative_to(base.parent)), pub))
    if v.findings:
        v.flag = "blocked"
        v.reasons = sorted({f.rule for f in v.findings})
    return v


def find_units(paths: list[Path]) -> list[Path]:
    units: list[Path] = []
    for p in paths:
        if p.is_file() or (p / "SKILL.md").is_file():
            units.append(p)
        elif p.is_dir():
            units.extend(sorted(d for d in p.iterdir() if d.is_dir() and not d.name.startswith(".")))
    return units


def lint(paths: list[Path], hosts_file: Path) -> list[Verdict]:
    pub = load_public_hosts(hosts_file)
    return [scan_unit(u, pub) for u in find_units(paths)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", type=Path, default=[REPO / "skills"])
    ap.add_argument("--hosts", type=Path, default=REPO / "catalog" / "public-hosts.yaml")
    ap.add_argument("--out", type=Path, help="write flags to JSON (dist/security.json)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = ap.parse_args(argv)

    verdicts = lint(args.paths, args.hosts)
    payload = {v.skill: {"flag": v.flag, "reasons": v.reasons,
                         "findings": [asdict(f) for f in v.findings]} for v in verdicts}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for v in verdicts:
            print(f"{v.flag.upper():8} {v.skill}" + (f" — {', '.join(v.reasons)}" if v.reasons else ""))
            for f in v.findings:
                print(f"         {f}")
        blocked = sum(v.flag == "blocked" for v in verdicts)
        print(f"security-lint: {len(verdicts)} checked, {blocked} blocked")
    return 1 if any(v.flag == "blocked" for v in verdicts) else 0


if __name__ == "__main__":
    sys.exit(main())
