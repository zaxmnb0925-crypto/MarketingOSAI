#!/usr/bin/env python3

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent

DEFAULT_FEATURE_ROOT = (
    HERE.parent
    / "app"
    / "history"
)

FEATURE_ROOT = Path(
    os.environ.get(
        "HISTORY_FEATURE_ROOT",
        str(DEFAULT_FEATURE_ROOT),
    )
)

BASELINE_PATH = Path(
    os.environ.get(
        "HISTORY_BASELINE",
        str(
            HERE
            / "history_contract_baseline.json"
        ),
    )
)


def fail(message):
    print(
        "CONTRACT_FAIL="
        + message
    )

    raise SystemExit(1)


def pass_gate(name):
    print(
        name
        + "=PASS"
    )


if not BASELINE_PATH.is_file():
    fail(
        "baseline_missing"
    )


baseline = json.loads(
    BASELINE_PATH.read_text()
)


if not FEATURE_ROOT.is_dir():
    fail(
        "feature_root_missing"
    )


page = (
    FEATURE_ROOT
    / "page.tsx"
)


if not page.is_file():
    fail(
        "page_tsx_missing"
    )


source_files = sorted(
    [
        *FEATURE_ROOT.rglob(
            "*.ts"
        ),
        *FEATURE_ROOT.rglob(
            "*.tsx"
        ),
    ],
    key=lambda path: path.as_posix(),
)


if not source_files:
    fail(
        "no_history_source_files"
    )


sources = {
    path: path.read_text()
    for path in source_files
}


aggregate = "\n".join(
    sources.values()
)


print(
    "history_feature_source_files="
    + str(
        len(source_files)
    )
)


for path in source_files:
    print(
        "FEATURE_FILE="
        + str(path)
    )


#
# 1. Route entrypoint remains a client page.
#

page_text = page.read_text()


if baseline.get(
    "client_component"
):
    if not re.search(
        r'''
        ^\s*
        ["']
        use\ client
        ["']
        \s*;?
        ''',
        page_text,
        re.VERBOSE,
    ):
        fail(
            "client_directive_missing"
        )


if not re.search(
    r'''
    export
    \s+
    default
    \s+
    function
    \s+
    HistoryPage
    \s*\(
    ''',
    page_text,
    re.VERBOSE,
):
    fail(
        "default_HistoryPage_export_missing"
    )


pass_gate(
    "route_entrypoint_contract"
)


#
# 2. BFF request surface.
#

fetch_pattern = re.compile(
    r'''
    fetch
    \s*\(
    \s*
    (?:
        `([^`]+)`
        |
        "([^"]+)"
        |
        '([^']+)'
    )
    ''',
    re.VERBOSE,
)


fetch_values = []


for text in sources.values():

    for match in fetch_pattern.finditer(
        text
    ):
        value = next(
            (
                item
                for item
                in match.groups()
                if item is not None
            ),
            None,
        )

        if value is not None:
            fetch_values.append(
                value
            )


actual_fetches = sorted(
    fetch_values
)

expected_fetches = sorted(
    baseline[
        "fetch_literals"
    ]
)


for item in actual_fetches:
    print(
        "CONTRACT_FETCH="
        + item
    )


if actual_fetches != expected_fetches:
    fail(
        "fetch_surface_changed"
    )


if len(actual_fetches) != baseline[
    "fetch_count"
]:
    fail(
        "fetch_count_changed"
    )


if any(
    not item.startswith(
        "/api/"
    )
    for item in actual_fetches
):
    fail(
        "non_BFF_fetch_detected"
    )


pass_gate(
    "bff_fetch_contract"
)


#
# 3. Auth/session model remains cookie/BFF based.
#

for token in baseline[
    "forbidden_auth_storage_tokens"
]:
    if token in aggregate:
        fail(
            "forbidden_auth_storage_token:"
            + token
        )


pass_gate(
    "auth_cookie_model_contract"
)


#
# 4. Existing domain types must survive extraction.
#

actual_types = set(
    re.findall(
        r'''
        ^\s*
        type\s+
        ([A-Za-z_$][\w$]*)
        \s*=
        ''',
        aggregate,
        re.MULTILINE | re.VERBOSE,
    )
)


required_types = set(
    baseline[
        "required_type_aliases"
    ]
)


if not required_types.issubset(
    actual_types
):
    missing = sorted(
        required_types
        - actual_types
    )

    fail(
        "missing_types:"
        + ",".join(
            missing
        )
    )


pass_gate(
    "domain_type_contract"
)


#
# 5. Existing state ownership names must survive the
# mechanical extraction. Additional component-local state
# is allowed.
#

state_names = set(
    name
    for name, _setter
    in re.findall(
        r'''
        const\s*
        \[
            \s*([A-Za-z_$][\w$]*)
            \s*,
            \s*([A-Za-z_$][\w$]*)
        \]
        \s*=
        \s*useState
        ''',
        aggregate,
        re.VERBOSE,
    )
)


required_state = set(
    baseline[
        "required_state_variables"
    ]
)


if not required_state.issubset(
    state_names
):
    missing = sorted(
        required_state
        - state_names
    )

    fail(
        "missing_state:"
        + ",".join(
            missing
        )
    )


pass_gate(
    "state_surface_contract"
)


#
# 6. Existing orchestration/presentation function names
# remain available somewhere inside the feature tree.
#

function_names = set()


function_patterns = [
    r'''
    (?:export\s+default\s+)?
    (?:async\s+)?
    function\s+
    ([A-Za-z_$][\w$]*)
    \s*\(
    ''',

    r'''
    const\s+
    ([A-Za-z_$][\w$]*)
    \s*=
    \s*(?:async\s*)?
    \([^)]*\)
    \s*=>
    ''',

    r'''
    const\s+
    ([A-Za-z_$][\w$]*)
    \s*=
    \s*(?:async\s*)?
    [A-Za-z_$][\w$]*
    \s*=>
    ''',
]


for pattern in function_patterns:
    function_names.update(
        re.findall(
            pattern,
            aggregate,
            re.VERBOSE,
        )
    )


required_functions = set(
    baseline[
        "required_functions"
    ]
)


if not required_functions.issubset(
    function_names
):
    missing = sorted(
        required_functions
        - function_names
    )

    fail(
        "missing_functions:"
        + ",".join(
            missing
        )
    )


pass_gate(
    "function_surface_contract"
)


#
# 7. Navigation targets remain unchanged.
#

router_push_pattern = re.compile(
    r'''
    router
    \.
    push
    \s*\(
    \s*
    (?:
        "([^"]+)"
        |
        '([^']+)'
        |
        `([^`]+)`
    )
    ''',
    re.VERBOSE,
)


router_pushes = []


for text in sources.values():

    for match in router_push_pattern.finditer(
        text
    ):
        value = next(
            (
                item
                for item
                in match.groups()
                if item
            ),
            None,
        )

        if value:
            router_pushes.append(
                value
            )


if sorted(
    router_pushes
) != sorted(
    baseline[
        "router_push_literals"
    ]
):
    fail(
        "navigation_surface_changed"
    )


pass_gate(
    "navigation_contract"
)


#
# 8. Preserve the current native JSX structure counts.
# New React component tags are allowed.
#

for tag, expected in baseline[
    "jsx_counts"
].items():

    actual = len(
        re.findall(
            rf'<{tag}\b',
            aggregate,
            re.IGNORECASE,
        )
    )

    print(
        "JSX_CONTRACT="
        + tag
        + " EXPECTED="
        + str(expected)
        + " ACTUAL="
        + str(actual)
    )

    if actual != expected:
        fail(
            "jsx_count_changed:"
            + tag
        )


pass_gate(
    "jsx_structure_contract"
)


#
# 9. Preserve current className assignments. This gives
# the mechanical extraction a visual/CSS parity gate.
#

actual_class_count = len(
    re.findall(
        r'\bclassName\s*=',
        aggregate,
    )
)


if actual_class_count != baseline[
    "class_name_count"
]:
    fail(
        "className_count_changed"
    )


class_pattern = re.compile(
    r'''
    className
    \s*=
    \s*
    (?:
        "([^"]*)"
        |
        '([^']*)'
        |
        `([^`]*)`
    )
    ''',
    re.VERBOSE,
)


actual_class_literals = []


for text in sources.values():

    for match in class_pattern.finditer(
        text
    ):
        value = next(
            (
                item
                for item
                in match.groups()
                if item is not None
            ),
            None,
        )

        if value is not None:
            actual_class_literals.append(
                value
            )


if Counter(
    actual_class_literals
) != Counter(
    baseline[
        "class_literals"
    ]
):
    fail(
        "className_literals_changed"
    )


pass_gate(
    "visual_class_contract"
)


#
# 10. Preserve main page heading.
#

for expected_text in baseline[
    "h1_text"
]:
    if expected_text not in aggregate:
        fail(
            "h1_text_missing:"
            + expected_text
        )


pass_gate(
    "visible_heading_contract"
)


print(
    "history_contract=10_OF_10_PASS"
)

print(
    "OVERALL=FRONTEND_HISTORY_CONTRACT_FULL_PASS"
)
