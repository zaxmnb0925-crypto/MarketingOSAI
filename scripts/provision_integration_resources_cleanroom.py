#!/usr/bin/env python3
"""Plan by default; execute only after separate explicit authorization."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from _integration_execute_flows import provision_resource
from _integration_execute_orchestration import SubprocessCommandExecutor
from _integration_resource_lifecycle import (
    build_docker_spec,
    generate_run_id,
    postgres_password_file_path,
    read_postgres_password_file,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("resource_type", choices=("postgres", "redis"))
    parser.add_argument("--image", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--redis-db", type=int, default=15)
    parser.add_argument("--postgres-password-file", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.resource_type == "redis" and args.postgres_password_file is not None:
        raise SystemExit("STOP: Redis does not accept a PostgreSQL password file")
    if args.resource_type == "postgres":
        expected_password_file = (
            postgres_password_file_path(args.run_id)
            if args.run_id
            else None
        )
        if args.postgres_password_file is None:
            raise SystemExit("STOP: PostgreSQL requires --postgres-password-file")
        if expected_password_file is None or args.postgres_password_file != expected_password_file:
            raise SystemExit("STOP: PostgreSQL password file path is not run-scoped")
    spec = build_docker_spec(
        run_id=args.run_id or generate_run_id(), resource_type=args.resource_type,
        image=args.image, port=args.port, redis_db=args.redis_db,
    )
    if args.execute:
        if os.geteuid() == 0:
            raise SystemExit("STOP_BEFORE_DOCKER_MUTATION: ROOT_EXECUTE_FORBIDDEN")
        postgres_password = None
        if args.resource_type == "postgres":
            postgres_password = read_postgres_password_file(
                args.postgres_password_file,
                run_id=spec.run_id,
            )
        result = provision_resource(
            spec, executor=SubprocessCommandExecutor(),
            secret_factory=(
                (lambda: postgres_password)
                if postgres_password is not None
                else None
            ),
        )
        postgres_password = None
        print(json.dumps({"mode": "EXECUTE", **result}, sort_keys=True))
        return 0
    plan = spec.sanitized_plan()
    plan["mode"] = "DRY_RUN"
    if args.resource_type == "postgres":
        plan["postgres_password_file_handoff"] = "REQUIRED_PRESENT"
    plan["docker_argv"] = list(spec.argv)
    print(json.dumps(plan, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
