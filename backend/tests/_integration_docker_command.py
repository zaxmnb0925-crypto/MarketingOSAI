"""Exact, Docker-only privilege boundary for disposable integration resources."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Sequence
import re

SUDO = "/usr/bin/sudo"
DOCKER = "/usr/bin/docker"
DOCKER_PRIVILEGE_PREFIX = (SUDO, "--", DOCKER)
DOCKER_SUBCOMMANDS = frozenset({"ps", "create", "start", "inspect", "stop", "rm"})


class DockerCommandPolicyError(ValueError):
    pass


def docker_command(subcommand: str, *arguments: str) -> tuple[str, ...]:
    """Build only the exact privileged Docker command shape reviewed here."""
    if subcommand not in DOCKER_SUBCOMMANDS:
        raise DockerCommandPolicyError("Docker subcommand is not allowlisted")
    if any(not isinstance(value, str) or "\x00" in value
           for value in (subcommand, *arguments)):
        raise DockerCommandPolicyError("Docker argv must contain safe strings")
    return (*DOCKER_PRIVILEGE_PREFIX, subcommand, *arguments)


def _valid_docker_arguments(subcommand: str, arguments: tuple[object, ...]) -> bool:
    cid = re.compile(r"[0-9a-f]{64}")
    if subcommand == "ps":
        return (len(arguments) == 4 and arguments[:3] == ("-a", "--no-trunc", "--format")
                and isinstance(arguments[3], str) and bool(arguments[3]))
    if subcommand in {"start", "stop", "rm"}:
        return (len(arguments) == 1 and isinstance(arguments[0], str)
                and cid.fullmatch(arguments[0]) is not None)
    if subcommand == "inspect":
        return (len(arguments) == 5 and arguments[:3] == ("--type", "container", "--format")
                and isinstance(arguments[3], str) and bool(arguments[3])
                and isinstance(arguments[4], str) and cid.fullmatch(arguments[4]) is not None)
    if subcommand != "create" or len(arguments) < 12:
        return False
    allowed_options = {
        "--pull", "--name", "--network", "--label", "--publish", "--mount",
        "--env", "--env-file", "--tmpfs",
    }
    index = 0
    values: dict[str, list[str]] = {}
    while index < len(arguments) and isinstance(arguments[index], str) and arguments[index].startswith("--"):
        option = arguments[index]
        if option not in allowed_options or index + 1 >= len(arguments):
            return False
        value = arguments[index + 1]
        if not isinstance(value, str) or not value or "\x00" in value:
            return False
        values.setdefault(option, []).append(value)
        index += 2
    if index >= len(arguments) or not isinstance(arguments[index], str):
        return False
    image = arguments[index]
    remainder = arguments[index + 1:]
    if not re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", image):
        return False
    names = values.get("--name", [])
    labels = values.get("--label", [])
    publishes = values.get("--publish", [])
    if (len(names) != 1 or re.fullmatch(r"marketingos-r22-[0-9a-f]{16}-(?:postgres|redis)", names[0]) is None
            or values.get("--pull") != ["never"]
            or values.get("--network") != ["bridge"]
            or len(publishes) != 1
            or re.fullmatch(r"127\.0\.0\.1:[0-9]{4,5}:(?:5432|6379)", publishes[0]) is None
            or len(labels) != 3
            or {label.split("=", 1)[0] for label in labels} != {
                "com.marketingos.test-resource", "com.marketingos.test-run-id",
                "com.marketingos.test-resource-type",
            }):
        return False
    if remainder == ():
        mounts = values.get("--mount", [])
        environment = values.get("--env", [])
        env_files = values.get("--env-file", [])

        if len(mounts) != 1:
            return False

        mount_match = re.fullmatch(
            r"type=bind,src=(/tmp/[^,]+),dst=/var/lib/postgresql/data",
            mounts[0],
        )

        if mount_match is None:
            return False

        source = PurePosixPath(mount_match.group(1))

        if (
            not source.is_absolute()
            or ".." in source.parts
            or source.name != "data"
            or source.parent.name != "postgres"
        ):
            return False

        name_match = re.fullmatch(
            r"marketingos-(r22-[0-9a-f]{16})-postgres",
            names[0],
        )

        if name_match is None:
            return False

        run_id = name_match.group(1)

        if source.parent.parent.name != run_id:
            return False

        expected_env_file = str(
            source.parent / "postgres-docker.env"
        )

        return (
            len(environment) == 2
            and {
                entry.split("=", 1)[0]
                for entry in environment
            } == {"POSTGRES_DB", "POSTGRES_USER"}
            and env_files == [expected_env_file]
            and "--tmpfs" not in values
        )
    return (remainder == ("redis-server", "--save", "", "--appendonly", "no")
            and values.get("--tmpfs") == ["/data:rw,size=67108864,mode=0700"]
            and "--mount" not in values
            and "--env" not in values
            and "--env-file" not in values)


def is_privileged_docker_command(argv: Sequence[object]) -> bool:
    command = tuple(argv)
    return (
        len(command) >= 4
        and command[:3] == DOCKER_PRIVILEGE_PREFIX
        and command[3] in DOCKER_SUBCOMMANDS
        and all(isinstance(value, str) and "\x00" not in value for value in command)
        and _valid_docker_arguments(str(command[3]), command[4:])
    )


def docker_subcommand(argv: Sequence[object]) -> str | None:
    return str(tuple(argv)[3]) if is_privileged_docker_command(argv) else None
