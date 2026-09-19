"""Immutable local artifacts; never sends bulk research data to Supabase."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from .core import canonical_bytes, digest, validate_contract

TABLES = ("snapshots", "matching_pools", "labels", "cases", "controls")
MAX_BYTES = 100 * 1024 * 1024


def read_json(path):
    with Path(path).open("rb") as source:
        raw = source.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError("input exceeds bounded 100 MiB batch size")
    return json.loads(raw)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _check_data(contract, data, expected_dataset_hash):
    validate_contract(contract, data["hashes"]["contract"])
    if data["target"] != contract["target"] or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("artifact identity differs from the frozen contract")
    for name in (*TABLES, "summary"):
        if digest(data[name]) != data["hashes"][name]:
            raise ValueError(f"{name} logical hash mismatch")
    actual = digest({"hashes": data["hashes"], "as_of": data["as_of"]})
    if actual != expected_dataset_hash or actual != data["dataset_hash"]:
        raise ValueError("dataset hash mismatch")


def write_bundle(path, contract, data, *, parquet=False):
    """Create exclusively; manifest written last marks a completed bundle.

    Keep incomplete outputs after a disk/write interruption for diagnosis;
    choose a new path on retry. Never overwrite a prior evidence directory.
    """
    _check_data(contract, data, data["dataset_hash"])
    if parquet:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ValueError("optional Parquet export requires an already installed pyarrow") from exc
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    files = {}
    for name in TABLES:
        raw = b"".join(canonical_bytes(row)+b"\n" for row in data[name])
        if len(raw) > MAX_BYTES:
            raise ValueError("output table exceeds bounded 100 MiB batch size")
        compressed = gzip.compress(raw, mtime=0)
        filename = f"{name}.jsonl.gz"
        (path/filename).write_bytes(compressed)
        files[filename] = {"sha256": _sha(compressed), "rows": len(data[name])}
        if parquet:
            filename = f"{name}.parquet"
            pq.write_table(pa.Table.from_pylist(data[name]), path/filename, compression="zstd")
            files[filename] = {"sha256": _sha((path/filename).read_bytes()), "rows": len(data[name])}
    manifest = {key: data[key] for key in ("schema_version", "target", "as_of", "hashes", "dataset_hash", "summary")}
    manifest.update(contract=contract, files=files, parquet=parquet,
                    provenance_note="Input source assertions require independent audit; hashes prove identity, not historical availability.")
    (path/"manifest.json").write_bytes(canonical_bytes(manifest)+b"\n")
    return manifest


def verify_bundle(path, *, expected_dataset_hash):
    """Verify against a digest retained outside the bundle, not its own claim."""
    path = Path(path)
    manifest = read_json(path/"manifest.json")
    expected_files = {f"{name}.jsonl.gz" for name in TABLES}
    if type(manifest["parquet"]) is not bool:
        raise ValueError("invalid parquet flag")
    if manifest["parquet"]:
        expected_files |= {f"{name}.parquet" for name in TABLES}
    if set(manifest["files"]) != expected_files:
        raise ValueError("unexpected artifact files")
    data = {k: manifest[k] for k in ("schema_version", "target", "as_of", "hashes", "dataset_hash", "summary")}
    for filename in sorted(expected_files):
        file_path = path/filename
        with file_path.open("rb") as source:
            raw = source.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES or _sha(raw) != manifest["files"][filename]["sha256"]:
            raise ValueError(f"artifact file hash mismatch: {filename}")
    for name in TABLES:
        with gzip.open(path/f"{name}.jsonl.gz", "rb") as source:
            raw = source.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            raise ValueError("decompressed artifact exceeds bounded batch size")
        data[name] = [json.loads(line) for line in raw.splitlines()]
        if len(data[name]) != manifest["files"][f"{name}.jsonl.gz"]["rows"]:
            raise ValueError("artifact row count mismatch")
    _check_data(manifest["contract"], data, expected_dataset_hash)
    if manifest["parquet"]:
        import pyarrow.parquet as pq
        for name in TABLES:
            if pq.read_table(path/f"{name}.parquet").to_pylist() != data[name]:
                raise ValueError("Parquet content differs from canonical JSONL")
    return data
