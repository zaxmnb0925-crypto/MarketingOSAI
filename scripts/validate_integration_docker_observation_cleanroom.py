#!/usr/bin/env python3
"""Normalize a supplied synthetic/trusted observation; never calls Docker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from _integration_resource_lifecycle import build_docker_spec, normalize_docker_observation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("resource_type", choices=("postgres", "redis"))
    parser.add_argument("--image", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--redis-db", type=int, default=15)
    args = parser.parse_args()
    spec = build_docker_spec(run_id=args.run_id, resource_type=args.resource_type,
                             image=args.image, port=args.port, redis_db=args.redis_db)
    raw = json.loads(args.fixture.read_text(encoding="utf-8"))
    normalized = normalize_docker_observation(raw, spec)
    print(json.dumps({
        "mode": "FIXTURE_VALIDATION", "attestation": "PASS",
        "run_id": normalized["resource_run_id"],
        "resource_type": normalized["resource_type"],
        "container_id": normalized["resource_container_id"][:12],
        "image_digest": normalized["resource_image_digest"],
        "host": normalized["resource_host"], "port": normalized["resource_port"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
