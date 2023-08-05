"""
Type declarations
"""
from typing import Union

# strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and None

Scalar = Union[str, bytes, int, bool, None]
Serializable = Union[tuple[Scalar, ...], list[Scalar], set[Scalar], dict[Scalar, Scalar]]
RecursiveSerializable = Union[
    Serializable,
    tuple[Serializable, ...],
    list[Serializable],
    set[Serializable],
    dict[Serializable, Serializable],
]
