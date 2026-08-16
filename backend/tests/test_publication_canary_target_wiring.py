import ast
import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException, Response

import sys as _publication_compat_sys
from pathlib import Path as _publication_compat_Path

_publication_compat_dir = str(
    _publication_compat_Path(
        __file__
    ).resolve().parent
)

if (
    _publication_compat_dir
    not in _publication_compat_sys.path
):
    _publication_compat_sys.path.insert(
        0,
        _publication_compat_dir,
    )

from _publication_test_compat import (
    publication_publishing_source_path,
    publication_source_paths,
    publication_source_text,
    publications,
)
import app.services.publication_activation_execution as execution

from app.core.config import settings
from app.models.publication import PublicationStatus
from app.schemas.publication import PublicationPublishRequest


WORKSPACE_ID = uuid.uuid4()
PUBLICATION_ID = uuid.uuid4()
WRONG_WORKSPACE_ID = uuid.uuid4()
WRONG_PUBLICATION_ID = uuid.uuid4()
USER_ID = uuid.uuid4()

CONTENT_HASH = "a" * 64


def call_name(node):
    if not isinstance(node, ast.Call):
        return None

    func = node.func

    if isinstance(func, ast.Name):
        return func.id

    if isinstance(func, ast.Attribute):
        return func.attr

    return None


def get_function(path, name):
    tree = ast.parse(
        path.read_text(),
        filename=str(path),
    )

    hits = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name == name
        )
    ]

    if len(hits) != 1:
        raise AssertionError(
            f"{name} count={len(hits)}"
        )

    return hits[0]


def call_line(fn, name):
    hits = [
        node.lineno
        for node in ast.walk(fn)
        if (
            isinstance(node, ast.Call)
            and call_name(node) == name
        )
    ]

    if len(hits) != 1:
        raise AssertionError(
            f"{name} calls={hits}"
        )

    return hits[0]


def setting_if_line(fn, name):
    hits = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue

        if name in ast.dump(
            node.test,
            include_attributes=False,
        ):
            hits.append(node.lineno)

    if len(hits) != 1:
        raise AssertionError(
            f"{name} if-lines={hits}"
        )

    return hits[0]


def static_gate():
    api = publication_publishing_source_path()

    exec_path = Path(
        "/app/app/services/"
        "publication_activation_execution.py"
    )

    activation = get_function(
        api,
        "create_publication_activation_endpoint",
    )

    assert (
        call_line(
            activation,
            "require_workspace_publish_activation",
        )
        <
        call_line(
            activation,
            "require_allowed_publication_publish_target",
        )
        <
        call_line(
            activation,
            "build_publication_meta_dry_run",
        )
        <
        call_line(
            activation,
            "create_publication_activation",
        )
    )

    publish = get_function(
        api,
        "publish_publication_endpoint",
    )

    assert (
        call_line(
            publish,
            "require_workspace_publish",
        )
        <
        setting_if_line(
            publish,
            "real_publish_enabled",
        )
        <
        call_line(
            publish,
            "require_allowed_publication_publish_target",
        )
        <
        call_line(
            publish,
            "get_publication_publish_transport",
        )
        <
        call_line(
            publish,
            "verify_and_consume_publication_activation_for_execution",
        )
        <
        call_line(
            publish,
            "execute_confirmed_meta_publication_with_transport",
        )
    )

    gate = get_function(
        exec_path,
        "verify_and_consume_publication_activation_for_execution",
    )

    assert (
        setting_if_line(
            gate,
            "real_publish_enabled",
        )
        <
        setting_if_line(
            gate,
            "meta_publish_transport_enabled",
        )
        <
        call_line(
            gate,
            "require_allowed_publication_publish_target",
        )
        <
        call_line(
            gate,
            "build_publication_meta_dry_run",
        )
        <
        call_line(
            gate,
            "consume_and_verify_publication_activation",
        )
    )

    total = 0

    for path in Path("/app/app").rglob("*.py"):
        tree = ast.parse(
            path.read_text(),
            filename=str(path),
        )

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and call_name(node)
                == "require_allowed_publication_publish_target"
            ):
                total += 1

    if total != 3:
        raise AssertionError(
            f"exact-target call sites={total}"
        )

    print(
        "Activation issuance ordering: PASS"
    )

    print(
        "/publish ordering: PASS"
    )

    print(
        "Activation execution ordering: PASS"
    )

    print(
        "Exact-target application call sites: 3"
    )


async def runtime_gate():
    original_real = (
        settings.real_publish_enabled
    )

    original_transport = (
        settings.meta_publish_transport_enabled
    )

    original_workspace = (
        settings.meta_publish_canary_workspace_id
    )

    original_publication = (
        settings.meta_publish_canary_publication_id
    )

    pub_originals = {
        "publish_auth":
            publications.require_workspace_publish,
        "activation_auth":
            publications.require_workspace_publish_activation,
        "dry_run":
            publications.build_publication_meta_dry_run,
        "issue":
            publications.create_publication_activation,
        "factory":
            publications.get_publication_publish_transport,
        "activation":
            publications.verify_and_consume_publication_activation_for_execution,
        "controlled":
            publications.execute_confirmed_meta_publication_with_transport,
    }

    exec_dry_run = (
        execution.build_publication_meta_dry_run
    )

    exec_consume = (
        execution.consume_and_verify_publication_activation
    )

    counts = {
        "factory": 0,
        "dry_run": 0,
        "issue": 0,
        "activation": 0,
        "controlled": 0,
        "exec_dry": 0,
        "exec_consume": 0,
    }

    async def auth(
        db,
        user,
        workspace_id,
    ):
        return SimpleNamespace(
            role="owner"
        )

    async def dry_run(
        db,
        workspace_id,
        publication_id,
    ):
        counts["dry_run"] += 1

        return SimpleNamespace(
            content_hash=CONTENT_HASH
        )

    async def issue(**kwargs):
        counts["issue"] += 1
        return "A" * 40

    def factory():
        counts["factory"] += 1
        return object()

    async def activation(**kwargs):
        counts["activation"] += 1

    async def controlled(**kwargs):
        counts["controlled"] += 1

        return SimpleNamespace(
            provider_post_id="mock",
            provider_permalink=None,
        )

    async def execution_dry(
        db,
        workspace_id,
        publication_id,
    ):
        counts["exec_dry"] += 1

        return SimpleNamespace(
            content_hash=CONTENT_HASH
        )

    async def execution_consume(
        **kwargs,
    ):
        counts["exec_consume"] += 1

    publications.require_workspace_publish = auth
    publications.require_workspace_publish_activation = auth
    publications.build_publication_meta_dry_run = dry_run
    publications.create_publication_activation = issue
    publications.get_publication_publish_transport = factory
    publications.verify_and_consume_publication_activation_for_execution = activation
    publications.execute_confirmed_meta_publication_with_transport = controlled

    execution.build_publication_meta_dry_run = execution_dry
    execution.consume_and_verify_publication_activation = execution_consume

    user = SimpleNamespace(
        id=USER_ID
    )

    payload = PublicationPublishRequest(
        activation="A" * 40,
        confirmation="C" * 40,
        content_hash=CONTENT_HASH,
    )

    try:
        settings.real_publish_enabled = True
        settings.meta_publish_transport_enabled = True

        settings.meta_publish_canary_workspace_id = None
        settings.meta_publish_canary_publication_id = None

        try:
            await publications.create_publication_activation_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                response=Response(),
                current_user=user,
                db=None,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError(
                "unset activation target accepted"
            )

        assert counts["dry_run"] == 0
        assert counts["issue"] == 0

        print(
            "Unset activation target blocks issuance: PASS"
        )

        settings.meta_publish_canary_workspace_id = (
            WORKSPACE_ID
        )

        settings.meta_publish_canary_publication_id = (
            PUBLICATION_ID
        )

        result = (
            await publications.create_publication_activation_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                response=Response(),
                current_user=user,
                db=None,
            )
        )

        assert result.activation == "A" * 40
        assert counts["dry_run"] == 1
        assert counts["issue"] == 1

        print(
            "Exact activation target issuance: PASS"
        )

        settings.meta_publish_canary_publication_id = (
            WRONG_PUBLICATION_ID
        )

        try:
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload,
                response=Response(),
                current_user=user,
                db=None,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError(
                "wrong /publish target accepted"
            )

        assert counts["factory"] == 0
        assert counts["activation"] == 0
        assert counts["controlled"] == 0

        print(
            "Wrong /publish target blocks provider factory: PASS"
        )

        settings.meta_publish_canary_publication_id = (
            PUBLICATION_ID
        )

        result = (
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload,
                response=Response(),
                current_user=user,
                db=None,
            )
        )

        assert result.status == PublicationStatus.published
        assert counts["factory"] == 1
        assert counts["activation"] == 1
        assert counts["controlled"] == 1

        print(
            "Exact /publish target continues chain: PASS"
        )

        #
        # Execution defense-in-depth wrong target.
        #
        settings.meta_publish_canary_publication_id = (
            WRONG_PUBLICATION_ID
        )

        try:
            await execution.verify_and_consume_publication_activation_for_execution(
                db=None,
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                activation_value="A" * 40,
                expected_content_hash=CONTENT_HASH,
            )
        except execution.ControlledPublicationActivationRejected:
            pass
        else:
            raise AssertionError(
                "wrong execution target accepted"
            )

        assert counts["exec_dry"] == 0
        assert counts["exec_consume"] == 0

        print(
            "Wrong execution target before dry-run/GETDEL: PASS"
        )

        settings.meta_publish_canary_publication_id = (
            PUBLICATION_ID
        )

        await execution.verify_and_consume_publication_activation_for_execution(
            db=None,
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            user_id=USER_ID,
            activation_value="A" * 40,
            expected_content_hash=CONTENT_HASH,
        )

        assert counts["exec_dry"] == 1
        assert counts["exec_consume"] == 1

        print(
            "Exact execution target reaches GETDEL layer: PASS"
        )

    finally:
        settings.real_publish_enabled = (
            original_real
        )

        settings.meta_publish_transport_enabled = (
            original_transport
        )

        settings.meta_publish_canary_workspace_id = (
            original_workspace
        )

        settings.meta_publish_canary_publication_id = (
            original_publication
        )

        publications.require_workspace_publish = (
            pub_originals["publish_auth"]
        )

        publications.require_workspace_publish_activation = (
            pub_originals["activation_auth"]
        )

        publications.build_publication_meta_dry_run = (
            pub_originals["dry_run"]
        )

        publications.create_publication_activation = (
            pub_originals["issue"]
        )

        publications.get_publication_publish_transport = (
            pub_originals["factory"]
        )

        publications.verify_and_consume_publication_activation_for_execution = (
            pub_originals["activation"]
        )

        publications.execute_confirmed_meta_publication_with_transport = (
            pub_originals["controlled"]
        )

        execution.build_publication_meta_dry_run = (
            exec_dry_run
        )

        execution.consume_and_verify_publication_activation = (
            exec_consume
        )

    print(
        "Process-local overrides restored: PASS"
    )


async def main():
    static_gate()
    await runtime_gate()

    print()
    print(
        "v0.13E-E-D EXACT CANARY TARGET WIRING: PASS"
    )

    print(
        "Real Redis calls: NONE"
    )

    print(
        "Credential decrypt calls: NONE"
    )

    print(
        "Real Meta calls: NONE"
    )

    print(
        "Facebook posts created: NONE"
    )


asyncio.run(
    main()
)
