"""
Helper to allow hbn types to be dumped to json safely.
"""
import json
from typing import Any


class CustomEncoder(json.JSONEncoder):
    """
    Encode things json might not understand natively.
    """

    def default(self, o: Any) -> Any:
        """Default for type"""
        if isinstance(o, set):
            return list(o)
        if isinstance(o, bytes):
            return o.decode("utf-8")
        if isinstance(o, type(Ellipsis)):
            return "Ellipsis"
        return super().default(o)
