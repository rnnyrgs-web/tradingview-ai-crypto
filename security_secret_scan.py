"""Lightweight committed-secret scanner used by Security and Reliability CI.

The OpenAI-key detector intentionally requires a token boundary before `sk-`.
Without that boundary, normal prose such as "risk-premium" contains the
substring "sk-" and produces false positives.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

ALLOWED_SUFFIXES = {".py", ".yml", ".yaml", ".json", ".md"}
SKIPPED_PATHS = {".github/workflows/security.yml"}

PATTERNS: tuple[re.Pattern[str], ...] = (
    # Real API keys may be quoted, assigned, or appear after punctuation, but
    # should not match the "sk-" inside ordinary words such as "risk-premium".
    re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r'''SUPABASE_SECRET_KEY\s*=\s*["'][^"']+["']'''),
    re.compile(r'''SCAN_SECRET\s*=\s*["'][^"']+["']'''),
    re.compile(r'''DASHBOARD_SECRET\s*=\s*["'][^"']+["']'''),
)
REUTERS_WORD_SLUG = re.compile(r"sk-(?:(?:[a-z]{1,18}|[0-9]{1,2})-){5,}20\d{2}-\d{2}-\d{2}")
REUTERS_URL_PREFIX = re.compile(
    r"https://(?:www\.)?reuters\.com/(?:[a-z0-9-]+/){2,}$"
)


def line_has_secret_pattern(line: str) -> bool:
    if any(pattern.search(line) for pattern in PATTERNS[1:]):
        return True
    for match in PATTERNS[0].finditer(line):
        # Reuters article slugs can start with the letters "sk" and contain
        # many lowercase words. Keep key-shaped tokens, even in a URL, blocked.
        suffix = line[match.end():]
        article_path_ends = suffix.startswith("/") and (
            len(suffix) == 1 or suffix[1].isspace() or suffix[1] in "\"',"
        )
        if (
            REUTERS_WORD_SLUG.fullmatch(match.group())
            and REUTERS_URL_PREFIX.search(line[: match.start()])
            and article_path_ends
        ):
            continue
        return True
    return False


def scan_paths(paths: Iterable[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if (
            not path.is_file()
            or ".git" in path.parts
            or path.suffix not in ALLOWED_SUFFIXES
            or path.as_posix() in SKIPPED_PATHS
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if line_has_secret_pattern(line):
                hits.append(f"{path}:{line_no}")
    return hits


def scan_tree(root: Path = Path(".")) -> list[str]:
    return scan_paths(root.rglob("*"))


def main() -> int:
    hits = scan_tree()
    if hits:
        print("Potential hard-coded secret pattern found:")
        print("\n".join(hits))
        return 1
    print("No obvious committed secrets detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
