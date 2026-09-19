"""Local-only command for a predeclared DEVELOPMENT dataset."""
import argparse
import json
import sys

from . import build_dataset
from .artifacts import read_json, write_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--expected-contract-sha256", required=True)
    parser.add_argument("--input", required=True, help="JSON object with snapshots and bars arrays")
    parser.add_argument("--as-of", required=True, help="Explicit UTC research observation cutoff")
    parser.add_argument("--output", required=True, help="New immutable artifact directory")
    parser.add_argument("--parquet", action="store_true", help="Also export Parquet using already installed pyarrow")
    args = parser.parse_args()
    try:
        contract, source = read_json(args.contract), read_json(args.input)
        if not isinstance(source, dict) or set(source) != {"snapshots", "bars"}:
            raise ValueError("input requires exactly snapshots and bars")
        if not all(isinstance(source[key], list) for key in source):
            raise ValueError("snapshots and bars must be arrays")
        result = build_dataset(contract, source["snapshots"], source["bars"], as_of=args.as_of,
                               expected_contract_hash=args.expected_contract_sha256)
        write_bundle(args.output, contract, result, parquet=args.parquet)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"RESEARCH_INPUT_OR_ARTIFACT_BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"dataset_hash": result["dataset_hash"], **result["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
