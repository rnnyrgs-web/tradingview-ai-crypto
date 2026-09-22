from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
SEMANTIC_REGISTRY = ROOT / "orchestration" / "rejected_semantic_designs.json"


def _docker_copies_source(dockerfile: str, source: str) -> bool:
    return any(
        line.strip().startswith(f"COPY {source} ")
        for line in dockerfile.splitlines()
    )


def test_production_image_packages_semantic_rejected_memory_import_closure() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    required = {
        "orchestration/rejected_fingerprints.py",
        "orchestration/rejected_fingerprints.json",
        "orchestration/rejected_semantic_designs.json",
        "orchestration/scientific_design_identity.py",
        "orchestration/strategy_behavior_data_projection.py",
        "orchestration/strategy_behavior_schema.py",
        "orchestration/strategy_behavior_value_contract.py",
    }
    missing = sorted(source for source in required if not _docker_copies_source(dockerfile, source))
    assert not missing, f"Dockerfile omits rejected-memory runtime dependency: {missing}"


def test_production_image_packages_every_authenticated_semantic_source_artifact() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    registry = json.loads(SEMANTIC_REGISTRY.read_text(encoding="utf-8"))

    sources = {
        record["source_artifact"]
        for record in registry["records"]
        if record.get("semantic_identity_status") == "BACKFILLED_STRUCTURED_CONTRACT"
    }
    missing = sorted(source for source in sources if not _docker_copies_source(dockerfile, source))
    assert not missing, f"Dockerfile omits authenticated semantic source artifact: {missing}"
