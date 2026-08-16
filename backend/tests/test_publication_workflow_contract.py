import ast
import hashlib
import importlib
import importlib.util
import json
import unittest
from pathlib import Path


EXPECTED = json.loads(r"""{
    "coupled_tests": [
        "test_publication_begin_attempt_audit.py",
        "test_publication_confirmation_http.py",
        "test_publication_executor.py",
        "test_publication_publish_http_integration.py",
        "test_publication_publish_normal_mode_integration.py",
        "test_publication_reconciliation.py",
        "test_publication_reconciliation_postgres_integration.py"
    ],
    "functions": {
        "_get_publication_for_update": {
            "sha256": "ef267519afbebcd49e824443861642a7b2083767fa514ae66a66feebfe3eabff",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='db', annotation=Name(id='AsyncSession', ctx=Load())), arg(arg='workspace_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='publication_id', annotation=Name(id='UUID', ctx=Load()))], kwonlyargs=[], kw_defaults=[], defaults=[])",
                "async": true,
                "returns": "Name(id='Publication', ctx=Load())",
                "type_comment": null
            },
            "status_refs": []
        },
        "approve_publication": {
            "sha256": "51b8501a5cb26fb18e994bed6ee335898b6a9c32d2b8cd7dc1a6026ffe2dd7a2",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='db', annotation=Name(id='AsyncSession', ctx=Load())), arg(arg='workspace_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='publication_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='approved_by_user_id', annotation=Name(id='UUID', ctx=Load()))], kwonlyargs=[], kw_defaults=[], defaults=[])",
                "async": true,
                "returns": "Name(id='Publication', ctx=Load())",
                "type_comment": null
            },
            "status_refs": [
                "approved",
                "draft"
            ]
        },
        "begin_publication_attempt": {
            "sha256": "ca470b7d581e5cb9b93c5166cc0dc54896fce3f33712f9692860e94e057cdda6",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='db', annotation=Name(id='AsyncSession', ctx=Load())), arg(arg='workspace_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='publication_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='triggered_by_user_id', annotation=Name(id='UUID', ctx=Load()))], kwonlyargs=[], kw_defaults=[], defaults=[])",
                "async": true,
                "returns": "Name(id='Publication', ctx=Load())",
                "type_comment": null
            },
            "status_refs": [
                "approved",
                "publishing"
            ]
        },
        "content_sha256": {
            "sha256": "e16c43fc33b31cf143d79e0339b0e3ec83c5581c9ee678ed1d34a48ca0f13f14",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='content', annotation=Name(id='str', ctx=Load()))], kwonlyargs=[], kw_defaults=[], defaults=[])",
                "async": false,
                "returns": "Name(id='str', ctx=Load())",
                "type_comment": null
            },
            "status_refs": []
        },
        "create_publication_draft": {
            "sha256": "66395e1903299603d63c983ab81e22fca39b3e21f2d94ce117ab4d63866659c4",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='db', annotation=Name(id='AsyncSession', ctx=Load())), arg(arg='workspace_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='content_generation_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='social_account_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='created_by_user_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='idempotency_key', annotation=Name(id='str', ctx=Load()))], kwonlyargs=[], kw_defaults=[], defaults=[])",
                "async": true,
                "returns": "Name(id='Publication', ctx=Load())",
                "type_comment": null
            },
            "status_refs": [
                "draft"
            ]
        },
        "mark_publication_execution_unknown": {
            "sha256": "7b103eb4028fd1c29193e0edb16fbc7540ad22b9106a7c053629c9ddefcbc72f",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='db', annotation=Name(id='AsyncSession', ctx=Load())), arg(arg='workspace_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='publication_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='safe_error', annotation=Name(id='str', ctx=Load()))], kwonlyargs=[], kw_defaults=[], defaults=[Constant(value='Publishing outcome is unknown; manual reconciliation required')])",
                "async": true,
                "returns": "Name(id='Publication', ctx=Load())",
                "type_comment": null
            },
            "status_refs": [
                "publishing"
            ]
        },
        "mark_publication_failed": {
            "sha256": "566d1525475014b73d4313702d51a48ba4237a13e11b60b65e1a4102282dce49",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='db', annotation=Name(id='AsyncSession', ctx=Load())), arg(arg='workspace_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='publication_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='safe_error', annotation=Name(id='str', ctx=Load()))], kwonlyargs=[], kw_defaults=[], defaults=[])",
                "async": true,
                "returns": "Name(id='Publication', ctx=Load())",
                "type_comment": null
            },
            "status_refs": [
                "failed",
                "publishing"
            ]
        },
        "mark_publication_published": {
            "sha256": "ed2229110d14fe20246fd0e43fdd90c59beddd82d9be62af85733429d88491f7",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='db', annotation=Name(id='AsyncSession', ctx=Load())), arg(arg='workspace_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='publication_id', annotation=Name(id='UUID', ctx=Load())), arg(arg='provider_post_id', annotation=Name(id='str', ctx=Load())), arg(arg='provider_permalink', annotation=BinOp(left=Name(id='str', ctx=Load()), op=BitOr(), right=Constant(value=None)))], kwonlyargs=[], kw_defaults=[], defaults=[Constant(value=None)])",
                "async": true,
                "returns": "Name(id='Publication', ctx=Load())",
                "type_comment": null
            },
            "status_refs": [
                "published",
                "publishing"
            ]
        },
        "verify_snapshot_integrity": {
            "sha256": "e0d35442a0d0eb0697235c32e654f8b2eedcd9e7fd7cbd36a40251e91685f9e2",
            "signature": {
                "args": "arguments(posonlyargs=[], args=[arg(arg='publication', annotation=Name(id='Publication', ctx=Load()))], kwonlyargs=[], kw_defaults=[], defaults=[])",
                "async": false,
                "returns": "Constant(value=None)",
                "type_comment": null
            },
            "status_refs": []
        }
    },
    "importers": {
        "api/publications/common.py": [
            "PublicationIdempotencyConflict",
            "PublicationNotFound",
            "PublicationStateError",
            "PublicationValidationError",
            "approve_publication",
            "create_publication_draft"
        ],
        "services/publication_dry_run.py": [
            "PublicationNotFound",
            "PublicationStateError",
            "PublicationValidationError",
            "verify_snapshot_integrity"
        ],
        "services/publication_executor.py": [
            "PublicationNotFound",
            "PublicationStateError",
            "PublicationValidationError",
            "begin_publication_attempt",
            "mark_publication_execution_unknown",
            "mark_publication_failed",
            "mark_publication_published",
            "verify_snapshot_integrity"
        ],
        "services/publication_reconciliation.py": [
            "PublicationNotFound",
            "PublicationStateError",
            "PublicationValidationError",
            "verify_snapshot_integrity"
        ]
    },
    "semantic_contract": {
        "forbids_explicit_commit": true,
        "forbids_explicit_rollback": true,
        "forbids_settings_branching": true,
        "requires_idempotency_logic": true,
        "requires_row_lock": true
    },
    "target_sha": "ab9e7760a4f300e176c3c6a41bddc32548832f7aa1edca21b8bb6fb0bb9b92a4"
}""")


BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"
TESTS_ROOT = BACKEND_ROOT / "tests"

MODULE_NAME = "app.services.publication_workflow"

EXPECTED_FUNCTION_NAMES = set(
    EXPECTED["functions"]
)


def _implementation_paths():
    spec = importlib.util.find_spec(
        MODULE_NAME
    )

    if spec is None:
        raise AssertionError(
            "publication_workflow module not found"
        )

    if spec.submodule_search_locations:
        roots = list(
            spec.submodule_search_locations
        )

        if len(roots) != 1:
            raise AssertionError(
                "unexpected workflow package locations"
            )

        root = Path(
            roots[0]
        )

        return sorted(
            root.glob("*.py")
        )

    if not spec.origin:
        raise AssertionError(
            "workflow module origin missing"
        )

    return [
        Path(spec.origin)
    ]


def _collect_functions():
    found = {}

    for path in _implementation_paths():
        text = path.read_text()
        lines = text.splitlines()

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

            if (
                node.name
                not in EXPECTED_FUNCTION_NAMES
            ):
                continue

            if node.name in found:
                raise AssertionError(
                    "duplicate workflow function: "
                    + node.name
                )

            decorator_lines = [
                item.lineno
                for item
                in node.decorator_list
            ]

            start = min(
                [
                    node.lineno,
                    *decorator_lines,
                ]
            )

            end = getattr(
                node,
                "end_lineno",
                node.lineno,
            )

            source = (
                "\n".join(
                    lines[
                        start - 1:
                        end
                    ]
                )
                + "\n"
            )

            signature = {
                "args": ast.dump(
                    node.args,
                    include_attributes=False,
                ),
                "returns": (
                    ast.dump(
                        node.returns,
                        include_attributes=False,
                    )
                    if node.returns is not None
                    else None
                ),
                "type_comment": getattr(
                    node,
                    "type_comment",
                    None,
                ),
                "async": isinstance(
                    node,
                    ast.AsyncFunctionDef,
                ),
            }

            status_refs = sorted(
                {
                    child.attr
                    for child
                    in ast.walk(node)
                    if (
                        isinstance(
                            child,
                            ast.Attribute,
                        )
                        and isinstance(
                            child.value,
                            ast.Name,
                        )
                        and child.value.id
                        == "PublicationStatus"
                    )
                }
            )

            found[node.name] = {
                "sha256": hashlib.sha256(
                    source.encode()
                ).hexdigest(),
                "signature": signature,
                "status_refs": status_refs,
                "source": source,
                "path": path.name,
            }

    return found


def _source_importers():
    needle = MODULE_NAME
    result = {}

    for path in sorted(
        APP_ROOT.rglob("*.py")
    ):
        rel = path.relative_to(
            APP_ROOT
        ).as_posix()

        if (
            rel == "services/publication_workflow.py"
            or rel.startswith(
                "services/publication_workflow/"
            )
        ):
            continue

        source = path.read_text()

        if needle not in source:
            continue

        tree = ast.parse(
            source,
            filename=str(path),
        )

        symbols = []

        for node in ast.walk(tree):
            if isinstance(
                node,
                ast.ImportFrom,
            ):
                if node.module == needle:
                    symbols.extend(
                        alias.name
                        for alias in node.names
                    )

            elif isinstance(
                node,
                ast.Import,
            ):
                for alias in node.names:
                    if alias.name == needle:
                        symbols.append(
                            "*MODULE*"
                        )

        result[rel] = sorted(
            set(symbols)
        )

    return result


class PublicationWorkflowContractTests(
    unittest.TestCase
):

    def test_facade_public_symbols(self):
        module = importlib.import_module(
            MODULE_NAME
        )

        for name in sorted(
            EXPECTED_FUNCTION_NAMES
        ):
            self.assertTrue(
                hasattr(
                    module,
                    name,
                ),
                name,
            )

            self.assertTrue(
                callable(
                    getattr(
                        module,
                        name,
                    )
                ),
                name,
            )


    def test_exact_function_inventory_signatures_and_sources(
        self,
    ):
        actual = _collect_functions()

        self.assertEqual(
            set(actual),
            EXPECTED_FUNCTION_NAMES,
        )

        for name in sorted(
            EXPECTED_FUNCTION_NAMES
        ):
            frozen = EXPECTED[
                "functions"
            ][name]

            current = actual[name]

            self.assertEqual(
                current["signature"],
                frozen["signature"],
                name,
            )

            self.assertEqual(
                current["status_refs"],
                frozen["status_refs"],
                name,
            )

            self.assertEqual(
                current["sha256"],
                frozen["sha256"],
                (
                    name
                    + " moved with behavioral "
                    + "source changes"
                ),
            )


    def test_application_importer_contract(self):
        self.assertEqual(
            _source_importers(),
            EXPECTED["importers"],
        )

        module = importlib.import_module(
            MODULE_NAME
        )

        for symbols in EXPECTED[
            "importers"
        ].values():
            for symbol in symbols:
                if symbol == "*MODULE*":
                    continue

                self.assertTrue(
                    hasattr(
                        module,
                        symbol,
                    ),
                    symbol,
                )


    def test_preexisting_coupled_test_inventory(
        self,
    ):
        needle = MODULE_NAME

        actual = []

        for path in sorted(
            TESTS_ROOT.glob(
                "test_*.py"
            )
        ):
            if path.name == Path(
                __file__
            ).name:
                continue

            if needle in path.read_text():
                actual.append(
                    path.name
                )

        self.assertEqual(
            actual,
            EXPECTED[
                "coupled_tests"
            ],
        )


    def test_sensitive_behavior_markers(
        self,
    ):
        implementations = _collect_functions()

        source = "\n".join(
            implementations[name][
                "source"
            ]
            for name in sorted(
                implementations
            )
        )

        lowered = source.lower()

        semantic = EXPECTED[
            "semantic_contract"
        ]

        if semantic[
            "requires_row_lock"
        ]:
            self.assertTrue(
                (
                    "with_for_update"
                    in lowered
                )
                or (
                    "for update"
                    in lowered
                )
            )

        if semantic[
            "requires_idempotency_logic"
        ]:
            self.assertIn(
                "idempot",
                lowered,
            )

        if semantic[
            "forbids_explicit_commit"
        ]:
            self.assertNotIn(
                ".commit(",
                lowered,
            )

        if semantic[
            "forbids_explicit_rollback"
        ]:
            self.assertNotIn(
                ".rollback(",
                lowered,
            )

        if semantic[
            "forbids_settings_branching"
        ]:
            self.assertNotIn(
                "settings.",
                lowered,
            )
