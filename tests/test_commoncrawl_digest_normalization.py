import pytest

from commoncrawl_digest_normalization import (
    commoncrawl_sha1_digests_match,
    normalize_commoncrawl_sha1_digest,
)


def test_commoncrawl_digest_normalization_matches_provider_formats():
    bare = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    assert normalize_commoncrawl_sha1_digest(bare, field="cdx") == bare
    assert normalize_commoncrawl_sha1_digest("sha1:" + bare.lower(), field="warc") == bare
    assert commoncrawl_sha1_digests_match(bare, "sha1:" + bare)


def test_commoncrawl_digest_normalization_rejects_wrong_algorithm_and_shape():
    bare = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    with pytest.raises(ValueError, match="algorithm"):
        normalize_commoncrawl_sha1_digest("sha256:" + bare, field="bad")
    with pytest.raises(ValueError, match="32-char Base32"):
        normalize_commoncrawl_sha1_digest("sha1:ABC", field="bad")
