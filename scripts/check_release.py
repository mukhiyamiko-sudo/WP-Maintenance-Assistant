"""Fail safely when a public release contains likely private material."""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "build", "dist", ".release-assets", "__pycache__", "chrome_profile", "logs"}
SENSITIVE_NAMES = re.compile(r"(?i)(cookies?|sessions?|login data|local state|credentials?|\.env)")
RULES = {
    "credential": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "user-path": re.compile(r"[A-Za-z]:[\\/]" + r"Users[\\/][^\s/\\]+|/" + r"Users/[^/\s]+"),
    "sensitive-url": re.compile(r"https?://[^\s<>]+[?&](?:token|access_token|password|auth|sso|key)=", re.I),
}
HOST = re.compile(r"(?<![\w.-])(?:[a-z0-9-]+\.)+(?:com|net|org|io|cn|co|xyz|site|online|store|shop|example|invalid)\b", re.I)
PUBLIC_HOSTS = {
    "cloudflare.com", "context.site", "example.com", "example.invalid", "facebook.com",
    "github.com", "google.com", "hostinger.com", "hpanel.hostinger.com", "self.site",
    "site-a.example", "site-b.example", "site-c.example", "site-one.example",
    "site-two.example", "site-zero.example", "wordpress.org", "www.cloudflare.com",
    "www.facebook.com", "www.google.com", "www.hostinger.com", "www.w3.org", "www.youtube.com",
    "youtube.com",
}


def scan(root: Path) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.is_symlink():
            findings.append((rel.as_posix(), "symlink"))
            continue
        if not path.is_file():
            continue
        name = rel.as_posix()
        if SENSITIVE_NAMES.search(path.name):
            findings.append((name, "sensitive-filename"))
        if path.suffix.lower() in {".exe", ".dll", ".pyc", ".zip"}:
            findings.append((name, "binary-in-repository"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        for rule, pattern in RULES.items():
            if pattern.search(text):
                findings.append((name, rule))
        for match in HOST.finditer(text):
            host = match.group().lower()
            if host not in PUBLIC_HOSTS:
                findings.append((name, "unapproved-host"))
                break
    return sorted(set(findings))


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings = scan(root)
    for name, rule in findings:
        print(f"FAIL {name}: {rule}")
    print(f"Release check: {'FAIL' if findings else 'PASS'}; {len(findings)} findings")
    raise SystemExit(bool(findings))
