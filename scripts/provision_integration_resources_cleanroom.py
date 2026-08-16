#!/usr/bin/env python3
"""Build a sanitized disposable-resource plan; never contacts Docker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from _integration_resource_lifecycle import build_docker_spec, generate_run_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("resource_type", choices=("postgres", "redis"))
    parser.add_argument("--image", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--redis-db", type=int, default=15)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute:
        raise SystemExit("STOP: Docker execution is not implemented or authorized")
    spec = build_docker_spec(
        run_id=args.run_id or generate_run_id(), resource_type=args.resource_type,
        image=args.image, port=args.port, redis_db=args.redis_db,
    )
    plan = spec.sanitized_plan()
    plan["mode"] = "DRY_RUN"
    plan["docker_argv"] = list(spec.argv)
    print(json.dumps(plan, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
