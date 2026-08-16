#!/usr/bin/env python3

import json
import re
import unittest
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

BRANDS_DIR = (
    PROJECT_ROOT
    / "frontend/app/brands"
)

LIST_ROUTE = (
    PROJECT_ROOT
    / "frontend/app/api/workspaces/[workspaceId]/brands/route.ts"
)

ITEM_ROUTE = (
    PROJECT_ROOT
    / "frontend/app/api/workspaces/[workspaceId]/brands/[brandId]/route.ts"
)

BASELINE_PATH = Path(
    __file__
).with_name(
    "brands_page_contract_baseline.json"
)


def source_files(root):
    return sorted(
        path
        for path in root.rglob("*")
        if (
            path.is_file()
            and
            path.suffix in {
                ".ts",
                ".tsx",
            }
        )
    )


def aggregate():
    return "\n".join(
        path.read_text(
            errors="replace"
        )
        for path in source_files(
            BRANDS_DIR
        )
    )


def api_refs(text):
    return sorted(
        set(
            re.findall(
                r'/api/[A-Za-z0-9_'
                r'\-/${}\[\].?=&]+',
                text,
            )
        )
    )


def fields(prefix, text):
    return sorted(
        set(
            re.findall(
                r'\b'
                + re.escape(prefix)
                + r'\.'
                r'([A-Za-z_$][\w$]*)',
                text,
            )
        )
    )


def method_literals(text):
    return dict(
        sorted(
            Counter(
                re.findall(
                    r'["\']'
                    r'(GET|POST|PUT|PATCH|DELETE)'
                    r'["\']',
                    text,
                )
            ).items()
        )
    )


def router_methods(text):
    return dict(
        sorted(
            Counter(
                re.findall(
                    r'\brouter\.'
                    r'(push|replace|refresh|back)'
                    r'\s*\(',
                    text,
                )
            ).items()
        )
    )


def router_path_tokens(text):
    result = set()

    for match in re.finditer(
        r'\brouter\.'
        r'(?:push|replace|refresh|back)'
        r'\s*\(',
        text,
    ):

        window = text[
            match.start():
            min(
                len(text),
                match.start() + 600,
            )
        ]

        for value in re.findall(
            r'[`"\']'
            r'(/[^`"\']+)'
            r'[`"\']',
            window,
        ):
            result.add(value)

    return sorted(result)


def route_methods(path):
    text = path.read_text(
        errors="replace"
    )

    return sorted(
        set(
            re.findall(
                r'export\s+async\s+function\s+'
                r'(GET|POST|PUT|PATCH|DELETE)'
                r'\s*\(',
                text,
            )
        )
    )


class BrandsPageContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.baseline = json.loads(
            BASELINE_PATH.read_text()
        )

        cls.source = aggregate()


    def test_01_page_state_surface(self):

        for token in self.baseline[
            "required_state_surface_tokens"
        ]:
            self.assertRegex(
                self.source,
                r'\b'
                + re.escape(token)
                + r'\b',
                token,
            )


    def test_02_workspace_boot_contract(self):

        self.assertIn(
            "workspaceId",
            self.source,
        )

        workspace_refs = [
            ref
            for ref in self.baseline[
                "client_api_refs"
            ]
            if "workspace" in ref
        ]

        self.assertTrue(
            workspace_refs
        )

        current = api_refs(
            self.source
        )

        for ref in workspace_refs:
            self.assertIn(
                ref,
                current,
            )


    def test_03_brand_list_fetch_contract(self):

        self.assertEqual(
            api_refs(
                self.source
            ),
            self.baseline[
                "client_api_refs"
            ],
        )

        self.assertGreaterEqual(
            len(
                re.findall(
                    r'\bfetch\s*\(',
                    self.source,
                )
            ),
            1,
        )


    def test_04_brand_create_mutation_contract(self):

        methods = method_literals(
            self.source
        )

        self.assertIn(
            "POST",
            methods,
        )

        self.assertIn(
            "POST",
            route_methods(
                LIST_ROUTE
            ),
        )


    def test_05_brand_update_mutation_contract(self):

        methods = method_literals(
            self.source
        )

        self.assertIn(
            "PATCH",
            methods,
        )

        self.assertIn(
            "PATCH",
            route_methods(
                ITEM_ROUTE
            ),
        )


    def test_06_brand_delete_mutation_contract(self):

        methods = method_literals(
            self.source
        )

        self.assertIn(
            "DELETE",
            methods,
        )

        self.assertIn(
            "DELETE",
            route_methods(
                ITEM_ROUTE
            ),
        )


    def test_07_form_field_contract(self):

        self.assertEqual(
            fields(
                "form",
                self.source,
            ),
            self.baseline[
                "form_fields"
            ],
        )


    def test_08_routing_contract(self):

        self.assertEqual(
            router_methods(
                self.source
            ),
            self.baseline[
                "router_methods"
            ],
        )

        self.assertEqual(
            router_path_tokens(
                self.source
            ),
            self.baseline[
                "router_path_tokens"
            ],
        )


    def test_09_bff_list_route_contract(self):

        self.assertEqual(
            route_methods(
                LIST_ROUTE
            ),
            self.baseline[
                "list_bff_methods"
            ],
        )


    def test_10_bff_item_route_contract(self):

        self.assertEqual(
            route_methods(
                ITEM_ROUTE
            ),
            self.baseline[
                "item_bff_methods"
            ],
        )


    def test_11_brand_brain_and_behavior_contract(self):

        self.assertEqual(
            fields(
                "brand",
                self.source,
            ),
            self.baseline[
                "brand_fields"
            ],
        )

        for token in self.baseline[
            "required_behavior_tokens"
        ]:
            self.assertRegex(
                self.source,
                r'\b'
                + re.escape(token)
                + r'\b',
                token,
            )

        self.assertEqual(
            method_literals(
                self.source
            ),
            self.baseline[
                "http_method_literals"
            ],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
