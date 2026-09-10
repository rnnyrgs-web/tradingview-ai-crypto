from pathlib import Path


def test_ffrizz_v2_predeclaration_document_exists():
    text = Path("docs/FFRIZZ_V2_OI_ALIGNMENT.md").read_text(encoding="utf-8")
    assert "FFRIZZ_SECONDARY_V2_OI_CLOSE_END" in text
    assert "No nearest-neighbour matching" in text
