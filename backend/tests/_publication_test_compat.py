"""
Test-only publication module compatibility.

This helper deliberately lives under tests/.

It allows existing regression tests to target the same
publication endpoint globals under either:

    app/api/publications.py

or:

    app/api/publications/*.py

No production runtime code imports this module.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Iterable


_FACADE = importlib.import_module(
    "app.api.publications"
)


def _implementation_modules() -> list[ModuleType]:
    modules: list[ModuleType] = [
        _FACADE,
    ]

    names = (
        "common",
        "queries",
        "lifecycle",
        "publishing",
        "reconciliation",
    )

    for name in names:
        try:
            module = importlib.import_module(
                f"app.api.publications.{name}"
            )
        except (
            ImportError,
            ModuleNotFoundError,
        ):
            continue

        if module not in modules:
            modules.append(
                module
            )

    return modules


class _PublicationProxy:
    __slots__ = ()

    def __getattr__(
        self,
        name: str,
    ):
        return getattr(
            _FACADE,
            name,
        )

    def __setattr__(
        self,
        name: str,
        value,
    ) -> None:
        matched = False

        for module in _implementation_modules():
            if (
                module is _FACADE
                or hasattr(
                    module,
                    name,
                )
            ):
                setattr(
                    module,
                    name,
                    value,
                )

                matched = True

        if not matched:
            setattr(
                _FACADE,
                name,
                value,
            )

    def __delattr__(
        self,
        name: str,
    ) -> None:
        deleted = False

        for module in _implementation_modules():
            if hasattr(
                module,
                name,
            ):
                delattr(
                    module,
                    name,
                )

                deleted = True

        if not deleted:
            raise AttributeError(
                name
            )

    def __dir__(self):
        names = set()

        for module in _implementation_modules():
            names.update(
                dir(module)
            )

        return sorted(
            names
        )


publications = _PublicationProxy()


def publication_source_paths() -> tuple[Path, ...]:
    facade_path = Path(
        _FACADE.__file__
    ).resolve()

    #
    # Current monolithic layout.
    #
    if (
        facade_path.name
        == "publications.py"
    ):
        return (
            facade_path,
        )

    #
    # Package layout.
    #
    if facade_path.name == "__init__.py":
        package = facade_path.parent

        preferred = (
            "common.py",
            "queries.py",
            "lifecycle.py",
            "publishing.py",
            "reconciliation.py",
            "__init__.py",
        )

        result = tuple(
            package / name
            for name in preferred
            if (
                package
                / name
            ).is_file()
        )

        if result:
            return result

    raise RuntimeError(
        "Unsupported publication source layout: "
        + str(
            facade_path
        )
    )


def publication_publishing_source_path() -> Path:
    facade_path = Path(
        _FACADE.__file__
    ).resolve()

    if (
        facade_path.name
        == "publications.py"
    ):
        return facade_path

    candidate = (
        facade_path.parent
        / "publishing.py"
    )

    if candidate.is_file():
        return candidate

    raise RuntimeError(
        "Publication publishing source "
        "could not be located"
    )


def publication_source_text() -> str:
    return "\n\n".join(
        path.read_text()
        for path in publication_source_paths()
    )
