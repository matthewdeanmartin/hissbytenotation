"""Glom integration helpers for phase 2 CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hissbytenotation import loads as hbn_loads
from hissbytenotation.install_hints import all_or_specific_extra_install_hint

from .errors import (
    FileIOCliError,
    GlomCliError,
    InputParseError,
    MissingValueError,
    OperationTypeError,
)

glom: Any = None
try:
    import glom as _glom

    glom = _glom
except ImportError:  # pragma: no cover - exercised when the optional glom extra is missing
    glom = None

_MISSING_QUERY_DEFAULT = object()


def ensure_glom_available() -> None:
    """Raise a CLI-facing error when glom is unavailable."""
    if glom is None:
        raise GlomCliError(
            "Glom integration requires the optional glom extra. "
            f"{all_or_specific_extra_install_hint('glom')}"
        )


def parse_glom_spec(spec_text: str) -> Any:
    """Parse a glom spec written in HBN / Python literal notation."""
    try:
        return hbn_loads(spec_text)
    except (SyntaxError, ValueError) as exc:
        raise InputParseError(f"Could not parse glom spec: {exc}") from exc


def resolve_query_spec(path_text: str | None, spec_text: str | None, spec_file_path: str | None) -> Any:
    """Resolve the glom query spec from path, inline text, or a spec file."""
    ensure_glom_available()
    if spec_file_path:
        try:
            spec_text = Path(spec_file_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise FileIOCliError(f"Could not read spec file {spec_file_path}: {exc}") from exc
    if spec_text is not None:
        return parse_glom_spec(spec_text)
    if path_text:
        return path_text
    raise InputParseError("Provide a query path, `--glom`, or `--spec-file`.")


def query_value(
    value: Any,
    *,
    path_text: str | None = None,
    spec_text: str | None = None,
    spec_file_path: str | None = None,
    default_on_missing: bool = False,
) -> Any:
    """Run a glom query and map glom errors to stable CLI errors."""
    spec = resolve_query_spec(path_text, spec_text, spec_file_path)
    try:
        if default_on_missing:
            result = glom.glom(value, spec, default=_MISSING_QUERY_DEFAULT, skip_exc=glom.PathAccessError)
            if result is _MISSING_QUERY_DEFAULT:
                return None
            return result
        return glom.glom(value, spec)
    except glom.PathAccessError as exc:
        raise MissingValueError(
            f"Missing query target for {_describe_target(path_text, spec_file_path, spec_text)}: {exc}"
        ) from exc
    except glom.GlomError as exc:
        raise GlomCliError(
            f"Glom query failed for {_describe_target(path_text, spec_file_path, spec_text)}: {exc}"
        ) from exc


def set_value(value: Any, path_text: str, new_value: Any) -> Any:
    """Set a nested value using glom assign semantics."""
    ensure_glom_available()
    _ensure_path(path_text, "set")
    try:
        return glom.assign(value, path_text, new_value, missing=dict)
    except glom.PathAccessError as exc:
        raise MissingValueError(f"Missing target path for set {path_text!r}: {exc}") from exc
    except glom.PathAssignError as exc:
        raise OperationTypeError(f"Could not set {path_text!r}: {exc}") from exc
    except glom.GlomError as exc:
        raise GlomCliError(f"Glom set failed for {path_text!r}: {exc}") from exc


def delete_value(value: Any, path_text: str) -> Any:
    """Delete a nested value using glom delete semantics."""
    ensure_glom_available()
    _ensure_path(path_text, "del")
    try:
        return glom.delete(value, path_text)
    except glom.PathDeleteError as exc:
        raise MissingValueError(f"Missing target path for del {path_text!r}: {exc}") from exc
    except glom.GlomError as exc:
        raise GlomCliError(f"Glom delete failed for {path_text!r}: {exc}") from exc


def append_value(value: Any, path_text: str, new_value: Any) -> Any:
    """Append to a nested list in place."""
    target_list = _get_list_target(value, path_text, "append")
    target_list.append(new_value)
    return value


def insert_value(value: Any, path_text: str, index: int, new_value: Any) -> Any:
    """Insert into a nested list in place."""
    target_list = _get_list_target(value, path_text, "insert")
    target_list.insert(index, new_value)
    return value


def _get_list_target(value: Any, path_text: str, operation_name: str) -> list[Any]:
    _ensure_path(path_text, operation_name)
    target = query_value(value, path_text=path_text)
    if not isinstance(target, list):
        raise OperationTypeError(
            f"{operation_name} requires a list target at {path_text!r}, got {type(target).__name__}."
        )
    return target


def _ensure_path(path_text: str | None, operation_name: str) -> None:
    if not path_text:
        raise InputParseError(f"{operation_name} requires a simple path.")


def _describe_target(path_text: str | None, spec_file_path: str | None, spec_text: str | None) -> str:
    if spec_file_path:
        return f"spec file {spec_file_path!r}"
    if spec_text is not None:
        return "`--glom` spec"
    if path_text:
        return f"path {path_text!r}"
    return "query"
