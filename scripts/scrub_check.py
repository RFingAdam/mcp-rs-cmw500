#!/usr/bin/env python3
"""Fail if any customer/project identifier leaks into the published tree.

This project generalizes knowledge from internal test scripts; no customer name,
project codename, person, instrument serial, or hard-coded developer path may
appear in the repository. Run in CI and locally:

    python scripts/scrub_check.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Case-insensitive forbidden tokens (regex fragments).
FORBIDDEN = [
    r"trimble",
    r"remora",
    r"porpoise",
    r"sanders2",
    r"stefan",
    r"andersson",
    r"166526",
    r"CMW50050-\d+",  # hard-coded instrument hostname+serial
    r"/home/swamp",  # developer-specific path
]

# Directories to skip.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".coverage",
}
# Only scan text-like files.
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".txt",
    ".cfg",
    ".ini",
    ".rst",
    ".svg",
}


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    self_path = Path(__file__).resolve()
    pattern = re.compile("|".join(f"({p})" for p in FORBIDDEN), re.IGNORECASE)
    hits: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.resolve() == self_path:
            continue  # this file names the tokens on purpose
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                rel = path.relative_to(root)
                hits.append(f"{rel}:{lineno}: {line.strip()[:120]}")

    if hits:
        print("SCRUB CHECK FAILED - forbidden identifiers found:")
        for h in hits:
            print(f"  {h}")
        return 1
    print("Scrub check passed: no customer/project identifiers found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
