"""Offline, zero-new-cost completion, snapshot and portable archive commands."""
import argparse
import json
from pathlib import Path

from .contracts import canonical
from .memory import Memory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Explicit persistent SQLite path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("snapshot")
    complete = sub.add_parser("complete")
    complete.add_argument("input")
    complete.add_argument("--ablation")
    for cmd in ("export", "import"):
        sub.add_parser(cmd).add_argument("archive")
    args = parser.parse_args(argv)
    memory = Memory(args.db, create=args.command == "init")
    if args.command == "complete":
        artifact = json.loads(Path(args.input).read_text())
        ablation = json.loads(Path(args.ablation).read_text()) if args.ablation else None
        result = memory.complete(artifact, ablation=ablation)
    elif args.command == "export":
        result = memory.export()
        # Exclusive create prevents clobbering previously archived evidence.
        with Path(args.archive).open("x", encoding="utf-8") as handle:
            handle.write(canonical(result) + "\n")
        result = {"status": "EXPORTED", "sha256": result["sha256"]}
    elif args.command == "import":
        memory.import_archive(json.loads(Path(args.archive).read_text()))
        result = {"status": "IMPORTED"}
    elif args.command == "snapshot":
        result = memory.snapshot()
    else:
        result = {"status": "INITIALIZED"}
    print(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
