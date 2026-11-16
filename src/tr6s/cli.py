"""
Layer 4 — command line. A thin shell over the same tool registry an LLM uses,
so the two can never drift apart.

    tr6s tools                       list every tool and its schema
    tr6s call <tool> '<json>'        invoke one
    tr6s info                        firmware and connection
    tr6s patterns [lo] [hi]          list patterns
    tr6s kits [lo] [hi]              list kits
    tr6s tones --category BASS       search the catalogue
    tr6s backup                      pull every pattern and kit to disk
    tr6s capture-template <slot>     save an empty slot as the authoring base
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config
from .tools import ToolError, call, close, schemas


def _print(obj):
    print(json.dumps(obj, indent=2, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tr6s", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("tools", help="list tools and JSON schemas")
    c = sub.add_parser("call", help="invoke a tool")
    c.add_argument("tool")
    c.add_argument("args", nargs="?", default="{}")

    sub.add_parser("info", help="firmware and connection")

    rb = sub.add_parser("read-blob", help="read an opaque TR-6S blob to a file")
    rb.add_argument("kind", choices=("system", "pattern", "kit"))
    rb.add_argument("slot", type=int, help="zero-based slot (system is 0)")
    rb.add_argument("output", help="destination file; must not exist")

    p = sub.add_parser("patterns", help="list patterns")
    p.add_argument("lo", nargs="?", default=0)
    p.add_argument("hi", nargs="?", default=15)

    kk = sub.add_parser("kits", help="list kits")
    kk.add_argument("lo", nargs="?", type=int, default=0)
    kk.add_argument("hi", nargs="?", type=int, default=15)

    tn = sub.add_parser("tones", help="search the tone catalogue")
    tn.add_argument("--category")
    tn.add_argument("--melodic", action="store_true")
    tn.add_argument("--root")
    tn.add_argument("--name-contains")
    tn.add_argument("--limit", type=int, default=25)

    b = sub.add_parser("backup", help="pull patterns and kits to disk")
    b.add_argument("--lo", type=int, default=0)
    b.add_argument("--hi", type=int, default=127)

    an = sub.add_parser("analyse-tones",
                        help="measure every tone: root pitch, loudness, decay, "
                             "brightness (long-running, unattended)")
    an.add_argument("--lo", type=int, default=0)
    an.add_argument("--hi", type=int, default=1023)
    an.add_argument("--category", help="restrict to one category")

    pr = sub.add_parser("probe-byte",
                        help="sweep an unidentified kit-record byte and report "
                             "what moved in the audio")
    pr.add_argument("offset", type=int, nargs="?", default=None,
                    help="omit to probe every unidentified offset in turn")
    pr.add_argument("--tone", type=int, default=None)
    pr.add_argument("--report", action="store_true",
                    help="print the accumulated findings and exit")

    ct = sub.add_parser("capture-template",
                        help="save an empty pattern slot as the authoring base")
    ct.add_argument("slot")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 0

    if args.cmd not in ("info", "read-blob"):
        print("This TR-6S port currently supports only info and read-blob. "
              "The editor commands still depend on unverified TR-8S layouts.",
              file=sys.stderr)
        return 2

    try:
        if args.cmd == "tools":
            for t in schemas():
                flag = "  [mutates device]" if t["mutates_device"] else ""
                print(f"{t['name']}{flag}\n    {t['description']}")
                props = t["input_schema"]["properties"]
                req = set(t["input_schema"]["required"])
                for k, v in props.items():
                    mark = "*" if k in req else " "
                    print(f"      {mark} {k}: {v.get('type')}")
            return 0

        if args.cmd == "call":
            _print(call(args.tool, json.loads(args.args)))
        elif args.cmd == "info":
            from .sequencer import SequencerTransport
            with SequencerTransport() as transport:
                _print(transport.info())
        elif args.cmd == "read-blob":
            from pathlib import Path
            from .sequencer import SequencerTransport
            from .transport import BLOB_SIZES, TransportError
            if not 0 <= args.slot <= (0 if args.kind == "system" else 127):
                ap.error("slot is out of range for this blob kind")
            with SequencerTransport() as transport:
                blob = transport.read_blob(args.kind, args.slot)
            if blob is None or len(blob) != BLOB_SIZES[args.kind]:
                raise TransportError(f"incomplete {args.kind} read")
            path = Path(args.output)
            with path.open("xb") as destination:
                destination.write(blob)
            _print({"kind": args.kind, "slot": args.slot,
                    "bytes": len(blob), "output": str(path)})
        elif args.cmd == "patterns":
            _print(call("pattern.list", {"lo": args.lo, "hi": args.hi}))
        elif args.cmd == "kits":
            _print(call("kit.list", {"lo": args.lo, "hi": args.hi}))
        elif args.cmd == "tones":
            q = {"limit": args.limit}
            if args.category:
                q["category"] = args.category
            if args.melodic:
                q["melodic"] = True
            if args.root:
                q["root"] = args.root
            if args.name_contains:
                q["name_contains"] = args.name_contains
            _print(call("tones.search", q))
        elif args.cmd == "backup":
            _print(call("device.backup", {"lo": args.lo, "hi": args.hi}))
        elif args.cmd == "analyse-tones":
            from .analysis import catalogue_tones
            from .device import Device
            with Device() as d:
                only = {args.category.upper()} if args.category else None
                res = catalogue_tones(d, args.lo, args.hi, only=only)
            _print({"measured": len(res),
                    "catalogue": str(config.tone_catalog_path())})
        elif args.cmd == "probe-byte":
            import json as _json
            from .analysis import probe_kit_byte, probe_many, probe_report
            from .device import Device
            path = config.data_dir() / "kit_byte_probe.json"
            if args.report:
                if not path.exists():
                    print("no probe results yet; run `tr6s probe-byte`",
                          file=sys.stderr)
                    return 1
                print(probe_report(_json.loads(path.read_text())))
                return 0
            with Device() as d:
                if args.offset is None:
                    probe_many(d, tone=args.tone)
                    print()
                    print(probe_report(_json.loads(path.read_text())))
                else:
                    _print(probe_kit_byte(d, args.offset, tone=args.tone))
        elif args.cmd == "capture-template":
            from .device import Device
            from .tools import _slot
            with Device() as d:
                p = d.read_pattern(_slot(args.slot))
                summary = p.describe()["variations"]
                if summary:
                    print(f"warning: slot {args.slot} is not empty "
                          f"({sorted(summary)} have steps). A template should be "
                          f"an unused slot.", file=sys.stderr)
                config.template_path().write_bytes(p.to_bytes())
                _print({"template": str(config.template_path()),
                        "from_slot": args.slot, "name": p.name})
        return 0
    except (ToolError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        close()


if __name__ == "__main__":
    sys.exit(main())
