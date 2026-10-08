from __future__ import annotations

import argparse
import json
from pathlib import Path

from .detector import detect_hook_opportunities
from .events import Event
from .harness import build_hook_tasks
from .probes import Probe
from .reducer import reduce_events


def _jsonl(path: str):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="surface-reducer")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_reduce = sub.add_parser("reduce")
    p_reduce.add_argument("events")
    p_detect = sub.add_parser("detect-hooks")
    p_detect.add_argument("probes")
    args = parser.parse_args(argv)

    if args.cmd == "reduce":
        events = [Event(**row) for row in _jsonl(args.events)]
        print(json.dumps(reduce_events(events).to_dict(), indent=2, sort_keys=True))
        return 0

    probes = [Probe(**row) for row in _jsonl(args.probes)]
    opportunities = detect_hook_opportunities(probes)
    payload = {
        "opportunities": [o.__dict__ for o in opportunities],
        "tasks": [t.to_dict() for t in build_hook_tasks(opportunities)],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
