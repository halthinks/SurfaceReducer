from __future__ import annotations

import argparse
import json
from pathlib import Path

from .detector import detect_hook_opportunities
from .events import Event
from .harness import build_hook_tasks
from .journal import EventJournal
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
    p_append = sub.add_parser("journal-append", help="atomically add events from JSONL")
    p_append.add_argument("database")
    p_append.add_argument("events")
    p_state = sub.add_parser("journal-state", help="checkpoint/catch up the projection")
    p_state.add_argument("database")
    p_state.add_argument("--surface")
    p_state.add_argument("--stale-after", type=float)
    p_replay = sub.add_parser("journal-replay", help="full replay independent of checkpoint")
    p_replay.add_argument("database")
    args = parser.parse_args(argv)

    if args.cmd == "reduce":
        events = [Event(**row) for row in _jsonl(args.events)]
        payload = reduce_events(events).to_dict()
    elif args.cmd == "journal-append":
        events = [Event(**row) for row in _jsonl(args.events)]
        journal = EventJournal(args.database)
        payload = {"accepted": journal.append_many(events), "stored": journal.count()}
    elif args.cmd in ("journal-state", "journal-replay"):
        journal = EventJournal(args.database)
        state = journal.project() if args.cmd == "journal-state" else journal.replay()
        if args.cmd == "journal-state" and args.surface is not None:
            payload = state.surface_status(args.surface, stale_after=args.stale_after)
        else:
            payload = state.to_dict()
    else:
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
