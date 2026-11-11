"""Scan files that would be published for personal data and secrets.

Everything in this repo is public, so a leaked email, phone number or token
can't be taken back. Run before every push (see .githooks/pre-push) and in CI.

    python scripts/pii_check.py            # every tracked file
    python scripts/pii_check.py --staged   # only what is staged for commit

Exit code 1 if anything suspicious is found.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Emails that are fine to publish (public contact, bot addresses).
ALLOWED_EMAILS = {"41898282+github-actions[bot]@users.noreply.github.com"}
ALLOWED_EMAIL_DOMAINS = {"users.noreply.github.com", "example.com"}

SKIP_DIRS = ("static/covers/", "static/doodles/", "site/", ".venv/")
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".json", ".html", ".js", ".css",
                 ".txt", ".csv", ".toml", ".ini", ".sh", ".example", ""}

PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "Taiwan mobile": re.compile(r"(?<![\d-])(?:\+?886[- ]?9|09)\d{2}[- ]?\d{3}[- ]?\d{3}(?![\d-])"),
    "Taiwan national ID": re.compile(r"(?<![A-Za-z0-9])[A-Z][12]\d{8}(?![A-Za-z0-9])"),
    "Notion token": re.compile(r"\b(?:ntn_|secret_)[A-Za-z0-9]{20,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def tracked_files(staged: bool) -> list[str]:
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"] if staged \
        else ["git", "ls-files"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f]


def scan_text(name: str, text: str) -> list[str]:
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, pattern in PATTERNS.items():
            for m in pattern.finditer(line):
                hit = m.group(0)
                if label == "email":
                    if hit in ALLOWED_EMAILS or hit.split("@")[1] in ALLOWED_EMAIL_DOMAINS:
                        continue
                problems.append(f"{name}:{lineno}: {label}: {hit}")
    return problems


def main(argv: list[str]) -> int:
    files = tracked_files("--staged" in argv)
    problems = []
    if ".env" in files:
        problems.append(".env is tracked by git: it holds secrets")
    for name in files:
        if name.startswith(SKIP_DIRS) or Path(name).suffix not in TEXT_SUFFIXES:
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        problems += scan_text(name, text)
    if problems:
        print("PII / secret check FAILED:")
        for p in problems:
            print("  " + p)
        print("Everything here is public. Remove it, or allow-list it in scripts/pii_check.py.")
        return 1
    print(f"PII / secret check passed ({len(files)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
