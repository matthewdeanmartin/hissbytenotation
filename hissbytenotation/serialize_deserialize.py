"""
(De)serialize to and from python source
"""

import ast
import importlib
from types import ModuleType
from typing import Any, Dict

from hissbytenotation.deserialize_by_import import loads_via_import
from hissbytenotation.install_hints import rust_install_hint
from hissbytenotation.supported_types import RecursiveSerializable


class HissByteNotationException(Exception):
    """Exceptions from hissbytenotation library"""


def _load_rust_parser_module() -> ModuleType:
    """Import the optional Rust parser from the packaged wheel or local dev builds."""
    for module_name in ("hissbytenotation.hbn_rust", "hbn_rust"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    raise ImportError(f"Optional Rust acceleration is unavailable. {rust_install_hint()}")


def dumps(python_object: Any, validate: bool = True) -> str:
    """
    Get a string representation of a Python object.

    Args:
    python_object: The Python object.

    Returns:
    str: A string representation of the Python object.
    """
    representation = repr(python_object)
    if validate:
        try:
            if ast.literal_eval(representation) != python_object:
                raise HissByteNotationException("Can't round trip, ast.literal_eval can't read that.")
        except (ValueError, SyntaxError) as e:
            raise HissByteNotationException("Can't round trip, ast.literal_eval can't read that.") from e
    return representation


def loads(
    source_code: str,
    by_eval: bool = False,
    by_import: bool = False,
    by_exec: bool = False,
    by_rust: bool = False,
) -> RecursiveSerializable:
    """
    Parse a string containing a Python literal expression and return the original Python object.

    Args:
    source_code (str): A string containing a Python literal expression.
    by_rust (bool): Use the optional Rust-accelerated parser when it is available.

    Returns:
    The original Python object.
    """
    if by_rust:
        return _load_rust_parser_module().loads(source_code)
    if by_import:
        return loads_via_import(source_code)
    if by_exec:
        data_dict: Dict[str, Any] = {}
        # pylint: disable=exec-used
        exec(f"data = {source_code}", data_dict)
        return data_dict["data"]
    if by_eval:
        # pylint: disable=eval-used
        return eval(source_code)
    return ast.literal_eval(source_code)
