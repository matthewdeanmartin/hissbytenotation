"""
(De)serialize to and from python source
"""
import ast
from typing import Any, Dict

from hissbytenotation.deserialize_by_import import loads_via_import
from hissbytenotation.supported_types import RecursiveSerializable


class HissByteNotationException(Exception):
    """Exceptions from hissbytenotation library"""


def dumps(python_object: Any, validate: bool = True) -> str:
    """
    Get a string representation of a Python object.

    Args:
    python_object: The Python object.

    Returns:
    str: A string representation of the Python object.
    """
    representation = repr(python_object)
    if validate and not ast.literal_eval(representation) == python_object:
        raise HissByteNotationException("Can't round trip, ast.literal_eval can't read that.")
    return representation


def loads(
    source_code: str, by_eval: bool = False, by_import: bool = False, by_exec: bool = False
) -> RecursiveSerializable:
    """
    Parse a string containing a Python literal expression and return the original Python object.

    Args:
    source_code (str): A string containing a Python literal expression.

    Returns:
    The original Python object.
    """
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
