#!/usr/bin/env python3
"""Authorize exact-ID teardown; execution remains disabled."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from _integration_resource_lifecycle import authorize_teardown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("resource_type", choices=("postgres", "redis"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sentinel", required=True, type=Path)
    parser.add_argument("--observation", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        commands = authorize_teardown(
            sentinel_path=args.sentinel, observation_path=args.observation,
            run_id=args.run_id, resource_type=args.resource_type,
        )
    except Exception:
        print(json.dumps({
            "TEARDOWN_AUTHORIZED": "NO", "RESOURCE_PRESERVED": "YES",
            "run_id": args.run_id, "resource_type": args.resource_type,
        }, sort_keys=True))
        raise
    if args.execute:
        raise SystemExit("STOP: Docker teardown execution is not implemented or authorized")
    print(json.dumps({
        "mode": "DRY_RUN", "TEARDOWN_AUTHORIZED": "YES",
        "RESOURCE_PRESERVED": "YES", "run_id": args.run_id,
        "resource_type": args.resource_type,
        "exact_commands": [list(command) for command in commands],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
