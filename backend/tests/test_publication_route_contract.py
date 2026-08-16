import ast
import os
import sys
import unittest
from pathlib import Path
from typing import get_args, get_origin


BACKEND_ROOT = Path(
    os.environ.get(
        "MARKETINGOS_BACKEND_ROOT",
        Path(__file__).resolve().parents[1],
    )
)

sys.path.insert(
    0,
    str(BACKEND_ROOT),
)


PREFIX = (
    "/api/workspaces/"
    "{workspace_id}/publications"
)

UUID = (
    "00000000-0000-0000-"
    "0000-000000000001"
)


def _publication_source_files():
    api_root = (
        BACKEND_ROOT
        / "app"
        / "api"
    )

    result = []

    monolith = (
        api_root
        / "publications.py"
    )

    package = (
        api_root
        / "publications"
    )

    if monolith.exists():
        result.append(
            monolith
        )

    if package.is_dir():
        result.extend(
            sorted(
                package.glob(
                    "*.py"
                )
            )
        )

    return result


def _find_endpoint_function(name):
    matches = []

    for path in _publication_source_files():
        text = path.read_text()

        tree = ast.parse(
            text,
            filename=str(path),
        )

        for node in tree.body:
            if not isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                continue

            if node.name == name:
                matches.append(
                    (
                        path,
                        text,
                        node,
                    )
                )

    if len(matches) != 1:
        raise AssertionError(
            f"{name}: expected exactly "
            f"one endpoint definition; "
            f"got {len(matches)}"
        )

    return matches[0]


def _dotted(node):
    if isinstance(
        node,
        ast.Name,
    ):
        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):
        base = _dotted(
            node.value
        )

        if base:
            return (
                base
                + "."
                + node.attr
            )

        return node.attr

    return ""


def _call_names(node):
    return {
        _dotted(
            child.func
        )
        for child
        in ast.walk(node)
        if isinstance(
            child,
            ast.Call,
        )
        and _dotted(
            child.func
        )
    }


def _attribute_names(node):
    return {
        _dotted(
            child
        )
        for child
        in ast.walk(node)
        if isinstance(
            child,
            ast.Attribute,
        )
        and _dotted(
            child
        )
    }


def _exception_names(node):
    result = set()

    for child in ast.walk(node):
        if not isinstance(
            child,
            ast.ExceptHandler,
        ):
            continue

        if child.type is None:
            result.add(
                "bare"
            )
        else:
            result.add(
                _dotted(
                    child.type
                )
            )

    return result


async def _asgi_status(
    app,
    method,
    path,
):
    body = (
        b"{}"
        if method
        in {
            "POST",
            "PUT",
            "PATCH",
        }
        else b""
    )

    headers = [
        (
            b"host",
            b"testserver",
        ),
    ]

    if body:
        headers.extend(
            [
                (
                    b"content-type",
                    b"application/json",
                ),
                (
                    b"content-length",
                    str(
                        len(body)
                    ).encode(),
                ),
            ]
        )

    scope = {
        "type": "http",
        "asgi": {
            "version": "3.0",
            "spec_version": "2.3",
        },
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": (
            "127.0.0.1",
            12345,
        ),
        "server": (
            "testserver",
            80,
        ),
    }

    first_receive = True
    messages = []

    async def receive():
        nonlocal first_receive

        if first_receive:
            first_receive = False

            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        return {
            "type": "http.disconnect",
        }

    async def send(message):
        messages.append(
            message
        )

    await app(
        scope,
        receive,
        send,
    )

    for message in messages:
        if (
            message.get(
                "type"
            )
            == "http.response.start"
        ):
            return message[
                "status"
            ]

    raise AssertionError(
        "ASGI request produced "
        "no response.start"
    )


class PublicationRouteContractTests(
    unittest.IsolatedAsyncioTestCase
):
    @classmethod
    def setUpClass(cls):
        from fastapi.routing import (
            APIRoute,
        )

        from app.main import app

        from app.api.publications import (
            router,
        )

        cls.APIRoute = APIRoute
        cls.app = app
        cls.router = router

        cls.routes = [
            route
            for route
            in router.routes
            if isinstance(
                route,
                APIRoute,
            )
        ]

    def test_exact_router_contract(self):
        self.assertEqual(
            self.router.prefix,
            PREFIX,
        )

        expected = {
            (
                "POST",
                PREFIX
                + "/drafts",
                "create_draft",
            ),
            (
                "GET",
                PREFIX,
                "list_publications",
            ),
            (
                "GET",
                PREFIX
                + "/{publication_id}",
                "get_publication",
            ),
            (
                "POST",
                PREFIX
                + "/{publication_id}/approve",
                "approve_publication_endpoint",
            ),
            (
                "POST",
                PREFIX
                + "/{publication_id}/dry-run",
                "dry_run_publication_endpoint",
            ),
            (
                "POST",
                PREFIX
                + "/{publication_id}/"
                "publish-confirmation",
                "issue_publish_confirmation_endpoint",
            ),
            (
                "POST",
                PREFIX
                + "/{publication_id}/publish",
                "publish_publication_endpoint",
            ),
            (
                "POST",
                PREFIX
                + "/{publication_id}/reconcile",
                "reconcile_publication_endpoint",
            ),
            (
                "POST",
                PREFIX
                + "/{publication_id}/"
                "publish-activation",
                "create_publication_activation_endpoint",
            ),
        }

        actual = set()

        allowed = {
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }

        for route in self.routes:
            for method in (
                route.methods
                or set()
            ):
                if method not in allowed:
                    continue

                actual.add(
                    (
                        method,
                        route.path,
                        route.endpoint.__name__,
                    )
                )

        self.assertEqual(
            actual,
            expected,
        )

        self.assertEqual(
            len(self.routes),
            9,
        )

    def test_response_model_contract(self):
        from app.schemas.publication import (
            PublicationActivationResponse,
            PublicationConfirmationResponse,
            PublicationDryRunResponse,
            PublicationPublishResponse,
            PublicationReconciliationResultResponse,
            PublicationResponse,
        )

        by_name = {
            route.endpoint.__name__: route
            for route
            in self.routes
        }

        expected = {
            "create_draft":
                PublicationResponse,
            "get_publication":
                PublicationResponse,
            "approve_publication_endpoint":
                PublicationResponse,
            "dry_run_publication_endpoint":
                PublicationDryRunResponse,
            "issue_publish_confirmation_endpoint":
                PublicationConfirmationResponse,
            "publish_publication_endpoint":
                PublicationPublishResponse,
            "reconcile_publication_endpoint":
                PublicationReconciliationResultResponse,
            "create_publication_activation_endpoint":
                PublicationActivationResponse,
        }

        for name, model in (
            expected.items()
        ):
            self.assertIn(
                name,
                by_name,
            )

            self.assertIs(
                by_name[
                    name
                ].response_model,
                model,
                name,
            )

        list_model = by_name[
            "list_publications"
        ].response_model

        if list_model is not None:
            self.assertIs(
                get_origin(
                    list_model
                ),
                list,
            )

            self.assertEqual(
                get_args(
                    list_model
                ),
                (
                    PublicationResponse,
                ),
            )

    async def test_app_level_routes_reach_auth_pipeline(
        self
    ):
        probes = [
            (
                "POST",
                f"{PREFIX}/drafts",
            ),
            (
                "GET",
                PREFIX,
            ),
            (
                "GET",
                (
                    f"{PREFIX}/"
                    f"{UUID}"
                ),
            ),
            (
                "POST",
                (
                    f"{PREFIX}/"
                    f"{UUID}/approve"
                ),
            ),
            (
                "POST",
                (
                    f"{PREFIX}/"
                    f"{UUID}/dry-run"
                ),
            ),
            (
                "POST",
                (
                    f"{PREFIX}/"
                    f"{UUID}/"
                    "publish-confirmation"
                ),
            ),
            (
                "POST",
                (
                    f"{PREFIX}/"
                    f"{UUID}/publish"
                ),
            ),
            (
                "POST",
                (
                    f"{PREFIX}/"
                    f"{UUID}/reconcile"
                ),
            ),
            (
                "POST",
                (
                    f"{PREFIX}/"
                    f"{UUID}/"
                    "publish-activation"
                ),
            ),
        ]

        for method, path in probes:
            with self.subTest(
                method=method,
                path=path,
            ):
                status = (
                    await _asgi_status(
                        self.app,
                        method,
                        path,
                    )
                )

                self.assertEqual(
                    status,
                    401,
                    (
                        method,
                        path,
                        status,
                    ),
                )

    def test_publish_safety_wiring(self):
        (
            _path,
            _text,
            node,
        ) = _find_endpoint_function(
            "publish_publication_endpoint"
        )

        calls = _call_names(
            node
        )

        attrs = _attribute_names(
            node
        )

        exceptions = _exception_names(
            node
        )

        required_calls = {
            "require_workspace_publish",
            "require_allowed_publication_publish_target",
            "get_publication_publish_transport",
            "verify_and_consume_publication_activation_for_execution",
            "execute_confirmed_meta_publication_with_transport",
        }

        self.assertTrue(
            required_calls.issubset(
                calls
            ),
            required_calls - calls,
        )

        self.assertIn(
            "settings.real_publish_enabled",
            attrs,
        )

        required_exceptions = {
            "PublicationPublishTargetRejected",
            "PublicationPublishTransportUnavailable",
            "ControlledPublicationExecutionDisabled",
            "ControlledPublicationContentHashMismatch",
            "ControlledPublicationActivationRejected",
            "ControlledPublicationConfirmationRejected",
            "PublicationExecutionProviderRejected",
            "PublicationExecutionOutcomeUnknown",
            "PublicationExecutionError",
        }

        self.assertTrue(
            required_exceptions.issubset(
                exceptions
            ),
            (
                required_exceptions
                - exceptions
            ),
        )

    def test_confirmation_activation_safety_wiring(
        self
    ):
        (
            _path,
            confirmation_text,
            confirmation,
        ) = _find_endpoint_function(
            "issue_publish_confirmation_endpoint"
        )

        confirmation_calls = (
            _call_names(
                confirmation
            )
        )

        self.assertTrue(
            {
                "require_workspace_publish",
                "build_publication_meta_dry_run",
                "create_publication_confirmation",
            }.issubset(
                confirmation_calls
            )
        )

        confirmation_segment = (
            "\n".join(
                confirmation_text.splitlines()[
                    confirmation.lineno - 1:
                    getattr(
                        confirmation,
                        "end_lineno",
                        confirmation.lineno,
                    )
                ]
            )
        )

        self.assertIn(
            "Cache-Control",
            confirmation_segment,
        )

        self.assertIn(
            "Pragma",
            confirmation_segment,
        )

        self.assertIn(
            "no-cache",
            confirmation_segment,
        )

        (
            _path,
            activation_text,
            activation,
        ) = _find_endpoint_function(
            "create_publication_activation_endpoint"
        )

        activation_calls = (
            _call_names(
                activation
            )
        )

        activation_attrs = (
            _attribute_names(
                activation
            )
        )

        self.assertTrue(
            {
                "require_workspace_publish_activation",
                "require_workspace_publish",
                "require_allowed_publication_publish_target",
                "build_publication_meta_dry_run",
                "create_publication_activation",
            }.issubset(
                activation_calls
            )
        )

        self.assertIn(
            "settings.meta_publish_canary_mode_enabled",
            activation_attrs,
        )

        activation_segment = (
            "\n".join(
                activation_text.splitlines()[
                    activation.lineno - 1:
                    getattr(
                        activation,
                        "end_lineno",
                        activation.lineno,
                    )
                ]
            )
        )

        self.assertIn(
            "Cache-Control",
            activation_segment,
        )

        self.assertIn(
            "Pragma",
            activation_segment,
        )

        self.assertIn(
            "no-cache",
            activation_segment,
        )

    def test_reconciliation_boundary_contract(self):
        (
            _path,
            _text,
            node,
        ) = _find_endpoint_function(
            "reconcile_publication_endpoint"
        )

        calls = _call_names(
            node
        )

        self.assertTrue(
            {
                "require_workspace_publish",
                "reconcile_publication",
                "db.commit",
                "db.rollback",
                "db.refresh",
            }.issubset(
                calls
            )
        )

        self.assertNotIn(
            "begin_publication_attempt",
            calls,
        )

        self.assertNotIn(
            "execute_confirmed_meta_publication_with_transport",
            calls,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
