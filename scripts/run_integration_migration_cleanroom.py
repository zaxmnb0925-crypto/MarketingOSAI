#!/usr/bin/env python3
"""Authorize migration; execute only after separate explicit authorization."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from _integration_execute_flows import execute_migration
from _integration_execute_orchestration import SubprocessCommandExecutor
from _integration_resource_lifecycle import authorize_migration


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sentinel", required=True, type=Path)
    parser.add_argument("--observation", type=Path)
    parser.add_argument("--image")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    password = os.environ.get("POSTGRES_TEST_PASSWORD", "")
    if args.execute:
        if not args.image:
            raise SystemExit("STOP: --image immutable reference is required")
        execute_migration(
            sentinel_path=args.sentinel, run_id=args.run_id, image=args.image,
            runtime_password=password, executor=SubprocessCommandExecutor(),
        )
        print(json.dumps({"mode": "EXECUTE", "MIGRATION_COMPLETE": "YES",
                          "run_id": args.run_id}, sort_keys=True))
        return 0
    if args.observation is None:
        raise SystemExit("STOP: --observation is required for dry-run fixture validation")
    command = authorize_migration(
        sentinel_path=args.sentinel, observation_path=args.observation,
        run_id=args.run_id, runtime_password=password,
    )
    print(json.dumps({
        "mode": "DRY_RUN", "MIGRATION_AUTHORIZED": "YES",
        "run_id": args.run_id, "target_head": command[-1],
        "command": list(command), "credential_url_logged": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
