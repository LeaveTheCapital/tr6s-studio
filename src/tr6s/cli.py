"""Read-only TR-6S inspection commands."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .kit import Kit
from .sequencer import SequencerTransport
from .transport import BLOB_SIZES, TransportError


def _slot(value: int, kind: str) -> int:
    top = 0 if kind == "system" else 127
    if not 0 <= value <= top:
        raise ValueError(f"{kind} slot must be 0..{top}")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tr6s", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("info", help="read firmware and playing status")

    read = commands.add_parser("read-blob", help="save one raw bulk blob")
    read.add_argument("kind", choices=tuple(BLOB_SIZES))
    read.add_argument("slot", type=int, help="zero-based slot; system is 0")
    read.add_argument("output", type=Path, help="new output file")

    inspect = commands.add_parser("inspect-kit", help="inspect verified and candidate kit fields")
    inspect.add_argument("slot", type=int, help="zero-based kit slot")
    inspect.add_argument("--file", type=Path, help="inspect a saved blob instead of reading MIDI")

    diff = commands.add_parser("diff-kit", help="compare two saved kit blobs")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "info":
            with SequencerTransport() as transport:
                result = transport.info()
        elif args.command == "read-blob":
            _slot(args.slot, args.kind)
            with SequencerTransport() as transport:
                blob = transport.read_blob(args.kind, args.slot)
            if len(blob) != BLOB_SIZES[args.kind]:
                raise TransportError(f"incomplete {args.kind} read")
            with args.output.open("xb") as output:
                output.write(blob)
            result = {"kind": args.kind, "slot": args.slot,
                      "bytes": len(blob), "output": str(args.output)}
        elif args.command == "inspect-kit":
            _slot(args.slot, "kit")
            if args.file:
                blob = args.file.read_bytes()
                source = str(args.file)
            else:
                with SequencerTransport() as transport:
                    blob = transport.read_blob("kit", args.slot)
                source = "TR-6S MIDI 1"
            result = {"slot": args.slot, "source": source, **Kit.from_bytes(blob).inspect()}
        else:
            before = Kit.from_bytes(args.before.read_bytes())
            after = Kit.from_bytes(args.after.read_bytes())
            changes = before.diff(after)
            result = {"before": str(args.before), "after": str(args.after),
                      "changed_bytes": len(changes), "changes": changes}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, TransportError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
