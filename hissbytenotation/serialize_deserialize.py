"""
(De)serialize to and from python source
"""
import ast
from typing import Any

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
    if validate and ast.literal_eval(representation) == python_object:
        return representation
    raise HissByteNotationException("Can't round trip, ast.literal_eval can't read that.")


def loads(source_code: str) -> RecursiveSerializable:
    """
    Parse a string containing a Python literal expression and return the original Python object.

    Args:
    source_code (str): A string containing a Python literal expression.

    Returns:
    The original Python object.
    """
    return ast.literal_eval(source_code)
