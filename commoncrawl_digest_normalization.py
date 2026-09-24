"""Algorithm-aware Common Crawl payload digest normalization.

Common Crawl CDXJ rows expose payload SHA-1 as bare Base32 while WARC headers use
``sha1:<Base32>``. Raw string comparison therefore rejects genuine provider evidence.
This helper normalizes only those two equivalent SHA-1 representations; unsupported
algorithms and malformed values fail closed.
"""

from __future__ import annotations

import re

SHA1_BASE32_RE = re.compile(r"^[A-Z2-7]{32}$")


def normalize_commoncrawl_sha1_digest(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} Common Crawl SHA-1 digest missing")
    text = value.strip()
    if ":" in text:
        algorithm, encoded = text.split(":", 1)
        if algorithm.lower() != "sha1":
            raise ValueError(f"{field} Common Crawl digest algorithm must be sha1")
    else:
        encoded = text
    encoded = encoded.upper()
    if not SHA1_BASE32_RE.fullmatch(encoded):
        raise ValueError(f"{field} Common Crawl SHA-1 digest must be 32-char Base32")
    return encoded


def commoncrawl_sha1_digests_match(index_digest: str, warc_payload_digest: str) -> bool:
    return normalize_commoncrawl_sha1_digest(
        index_digest, field="index_digest"
    ) == normalize_commoncrawl_sha1_digest(
        warc_payload_digest, field="warc_payload_digest"
    )
