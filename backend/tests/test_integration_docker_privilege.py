"""Fake-only tests for the exact Docker sudo privilege boundary."""
from __future__ import annotations

import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from _integration_docker_command import (
    DOCKER_PRIVILEGE_PREFIX, DockerCommandPolicyError, docker_command,
    docker_subcommand, is_privileged_docker_command,
)
from _integration_execute_orchestration import (
    FailureClass, OrchestrationError, SubprocessCommandExecutor,
)


@pytest.mark.parametrize("command", [
    docker_command("ps", "-a", "--no-trunc", "--format", "{{.ID}}"),
    docker_command("create", "--pull", "never", "--name", "marketingos-r22-0123456789abcdef-redis", "--network", "bridge",
                   "--label", "com.marketingos.test-resource=true",
                   "--label", "com.marketingos.test-run-id=r22-0123456789abcdef",
                   "--label", "com.marketingos.test-resource-type=redis",
                   "--publish", "127.0.0.1:16379:6379",
                   "--tmpfs", "/data:rw,size=67108864,mode=0700",
                   "redis@sha256:" + "a" * 64, "redis-server", "--save", "",
                   "--appendonly", "no"),
    docker_command("start", "c" * 64),
    docker_command("inspect", "--type", "container", "--format", "{{json .Id}}", "c" * 64),
    docker_command("stop", "c" * 64),
    docker_command("rm", "c" * 64),
])
def test_exact_docker_builder_prefix_and_scope(command):
    assert command[:3] == DOCKER_PRIVILEGE_PREFIX
    assert is_privileged_docker_command(command)
    assert docker_subcommand(command) == command[3]


@pytest.mark.parametrize("subcommand", [
    "run", "exec", "kill", "restart", "pull", "build", "compose", "volume", "system",
])
def test_docker_builder_rejects_unreviewed_capabilities(subcommand):
    with pytest.raises(DockerCommandPolicyError):
        docker_command(subcommand)


@pytest.mark.parametrize("command", [
    ("/usr/bin/docker", "ps"),
    ("/usr/bin/sudo", "/usr/bin/docker", "ps"),
    ("/usr/bin/sudo", "-E", "--", "/usr/bin/docker", "ps"),
    ("/usr/bin/sudo", "-S", "--", "/usr/bin/docker", "ps"),
    ("/usr/bin/sudo", "-A", "--", "/usr/bin/docker", "ps"),
    ("/usr/bin/sudo", "--", "/bin/bash", "-c", "true"),
    ("/usr/bin/sudo", "--", "/usr/bin/python3", "script.py"),
    ("/usr/bin/sudo", "--", "/usr/bin/rm", "target"),
    ("/usr/bin/sudo", "--", "/usr/bin/false"),
    ("/usr/bin/sudo", "--", "/usr/bin/docker", "rm", "-f", "c" * 64),
    ("/usr/bin/sudo", "--", "/usr/bin/docker", "create", "--privileged"),
])
def test_executor_rejects_bare_or_generic_sudo_targets(monkeypatch, command):
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: pytest.fail("subprocess invoked"))
    with pytest.raises(OrchestrationError) as error:
        SubprocessCommandExecutor().run(command)
    assert error.value.category is FailureClass.RESOURCE_IDENTITY_MISMATCH


def test_environment_cannot_override_absolute_sudo_or_docker(monkeypatch):
    monkeypatch.setenv("SUDO", "/tmp/untrusted-sudo")
    monkeypatch.setenv("DOCKER", "/tmp/untrusted-docker")
    monkeypatch.setenv("PATH", "/tmp/untrusted-path")
    assert docker_command("ps") == (
        "/usr/bin/sudo", "--", "/usr/bin/docker", "ps",
    )


def test_executor_preserves_shell_false_bounded_policy(monkeypatch):
    observed = {}
    def fake_run(command, **kwargs):
        observed["command"] = command
        observed.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    SubprocessCommandExecutor().run(docker_command("ps", "-a", "--no-trunc", "--format", "{{.ID}}"))
    assert observed["command"] == docker_command("ps", "-a", "--no-trunc", "--format", "{{.ID}}")
    assert observed["shell"] is False
    assert observed["timeout"] == 30.0
    assert observed["capture_output"] is True
    assert observed["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}


@pytest.mark.parametrize("script_name, argv", [
    ("provision_integration_resources_cleanroom.py", [
        "redis", "--image", "redis@sha256:" + "a" * 64,
        "--port", "16379", "--run-id", "r22-0123456789abcdef", "--execute",
    ]),
    ("teardown_integration_resources_cleanroom.py", [
        "redis", "--run-id", "r22-0123456789abcdef",
        "--sentinel", "/tmp/not-read", "--image", "redis@sha256:" + "a" * 64,
        "--execute",
    ]),
])
def test_execute_mode_rejects_uid_zero_before_subprocess(monkeypatch, script_name, argv):
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / script_name
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: pytest.fail("subprocess invoked"))
    monkeypatch.setattr(sys, "argv", [str(script), *argv])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(script), run_name="__main__")
    assert str(error.value) == "STOP_BEFORE_DOCKER_MUTATION: ROOT_EXECUTE_FORBIDDEN"
