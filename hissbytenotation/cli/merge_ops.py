"""Merge helpers for phase 3 CLI commands."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .errors import MergeConflictError

MERGE_STRATEGIES = ("replace", "shallow", "deep", "append-lists", "set-union-lists")
CONFLICT_POLICIES = ("error", "left-wins", "right-wins")


def merge_values(
    left: Any,
    right: Any,
    *,
    strategy: str = "deep",
    conflict: str = "error",
    strict: bool = False,
    path: str = "$",
) -> Any:
    """Merge two values according to the selected strategy and conflict policy."""
    if strategy == "replace":
        return deepcopy(right)
    if isinstance(left, dict) and isinstance(right, dict):
        if strategy == "shallow":
            return _merge_dict_shallow(left, right, conflict=conflict, path=path)
        return _merge_dict_recursive(left, right, strategy=strategy, conflict=conflict, strict=strict, path=path)
    if type(left) is not type(right):
        return _type_conflict(left, right, conflict=conflict, strict=strict, path=path)
    if isinstance(left, list):
        if strategy == "append-lists":
            return deepcopy(left) + deepcopy(right)
        if strategy == "set-union-lists":
            return _merge_list_union(left, right)
    if left == right:
        return deepcopy(left)
    return _resolve_conflict(
        left, right, conflict=conflict, message=f"Merge conflict at {path}: {left!r} conflicts with {right!r}."
    )


def _merge_dict_shallow(left: dict[Any, Any], right: dict[Any, Any], *, conflict: str, path: str) -> dict[Any, Any]:
    result = deepcopy(left)
    for key, right_value in right.items():
        child_path = _child_path(path, key)
        if key not in left:
            result[key] = deepcopy(right_value)
            continue
        if left[key] == right_value:
            result[key] = deepcopy(left[key])
            continue
        result[key] = _resolve_conflict(
            left[key], right_value, conflict=conflict, message=f"Shallow merge conflict at {child_path}."
        )
    return result


def _merge_dict_recursive(
    left: dict[Any, Any],
    right: dict[Any, Any],
    *,
    strategy: str,
    conflict: str,
    strict: bool,
    path: str,
) -> dict[Any, Any]:
    result = deepcopy(left)
    for key, right_value in right.items():
        child_path = _child_path(path, key)
        if key not in left:
            result[key] = deepcopy(right_value)
            continue
        result[key] = merge_values(
            left[key],
            right_value,
            strategy=strategy,
            conflict=conflict,
            strict=strict,
            path=child_path,
        )
    return result


def _merge_list_union(left: list[Any], right: list[Any]) -> list[Any]:
    result: list[Any] = []
    for item in list(left) + list(right):
        if any(existing == item for existing in result):
            continue
        result.append(deepcopy(item))
    return result


def _type_conflict(left: Any, right: Any, *, conflict: str, strict: bool, path: str) -> Any:
    message = f"Type mismatch at {path}: {type(left).__name__} conflicts with {type(right).__name__}."
    if strict:
        raise MergeConflictError(message)
    return _resolve_conflict(left, right, conflict=conflict, message=message)


def _resolve_conflict(left: Any, right: Any, *, conflict: str, message: str) -> Any:
    if conflict == "left-wins":
        return deepcopy(left)
    if conflict == "right-wins":
        return deepcopy(right)
    raise MergeConflictError(message)


def _child_path(path: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}"
