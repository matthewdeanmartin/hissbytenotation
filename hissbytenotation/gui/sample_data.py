"""Random data generators for the HBN GUI demo."""

from __future__ import annotations

import random
import string
from typing import Any


def _random_string(min_len: int = 3, max_len: int = 12) -> str:
    length = random.randint(min_len, max_len)
    return "".join(random.choices(string.ascii_lowercase, k=length))


def _random_email() -> str:
    return f"{_random_string(4, 8)}@{_random_string(4, 8)}.{random.choice(['com', 'org', 'net', 'io'])}"


def _random_scalar() -> Any:
    kind = random.choice(["int", "float", "str", "bool", "none", "bytes"])
    if kind == "int":
        return random.randint(-1000, 1000)
    if kind == "float":
        return round(random.uniform(-100.0, 100.0), 4)
    if kind == "str":
        return _random_string()
    if kind == "bool":
        return random.choice([True, False])
    if kind == "none":
        return None
    return _random_string(2, 6).encode("ascii")


def generate_flat_dict(n: int = 8) -> dict[str, Any]:
    """Generate a flat dictionary with random scalar values."""
    return {_random_string(): _random_scalar() for _ in range(n)}


def generate_nested_dict(depth: int = 3, breadth: int = 4) -> dict[str, Any]:
    """Generate a nested dictionary structure."""
    if depth <= 1:
        return generate_flat_dict(breadth)
    result: dict[str, Any] = {}
    for _ in range(breadth):
        key = _random_string()
        choice = random.random()
        if choice < 0.3:
            result[key] = generate_nested_dict(depth - 1, max(2, breadth - 1))
        elif choice < 0.5:
            result[key] = [_random_scalar() for _ in range(random.randint(2, 6))]
        else:
            result[key] = _random_scalar()
    return result


def generate_user_records(n: int = 5) -> dict[str, list[dict[str, Any]]]:
    """Generate a realistic users dataset."""
    roles = ["admin", "editor", "viewer", "moderator"]
    statuses = ["active", "inactive", "pending"]
    users = []
    for i in range(n):
        user: dict[str, Any] = {
            "id": i + 1,
            "name": f"{_random_string(4, 8).capitalize()} {_random_string(5, 10).capitalize()}",
            "email": _random_email(),
            "role": random.choice(roles),
            "status": random.choice(statuses),
            "score": round(random.uniform(0, 100), 2),
            "tags": [_random_string(3, 6) for _ in range(random.randint(1, 4))],
        }
        if random.random() > 0.5:
            user["metadata"] = generate_flat_dict(3)
        users.append(user)
    return {"users": users}


def generate_config_file() -> dict[str, Any]:
    """Generate a realistic configuration structure."""
    return {
        "app": {
            "name": _random_string(5, 10),
            "version": f"{random.randint(0, 5)}.{random.randint(0, 20)}.{random.randint(0, 99)}",
            "debug": random.choice([True, False]),
        },
        "database": {
            "host": f"{_random_string(3, 6)}.example.com",
            "port": random.choice([3306, 5432, 27017, 6379]),
            "name": _random_string(5, 10),
            "pool_size": random.randint(5, 50),
            "ssl": random.choice([True, False]),
        },
        "logging": {
            "level": random.choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
            "format": random.choice(["json", "text", "structured"]),
            "handlers": [random.choice(["console", "file", "syslog"]) for _ in range(random.randint(1, 3))],
        },
        "features": {key: random.choice([True, False]) for key in [_random_string(5, 10) for _ in range(4)]},
    }


def generate_mixed_types() -> dict[str, Any]:
    """Generate data showcasing all HBN-supported types."""
    return {
        "string_val": "hello world",
        "bytes_val": b"binary data",
        "int_val": 42,
        "negative_int": -17,
        "float_val": 3.14159,
        "bool_true": True,
        "bool_false": False,
        "none_val": None,
        "tuple_val": (1, "two", 3.0),
        "list_val": [10, 20, 30, 40],
        "set_val": {1, 2, 3, 4, 5},
        "nested_dict": {"a": {"b": {"c": "deep"}}},
        "nested_list": [[1, 2], [3, 4], [5, 6]],
        "mixed_list": [1, "two", 3.0, True, None, b"five"],
        "empty_dict": {},
        "empty_list": [],
        "empty_tuple": (),
        "empty_set": set(),
        "large_int": 10**18,
        "ellipsis": ...,
    }


def generate_list_of_dicts(n: int = 8) -> list[dict[str, Any]]:
    """Generate a list of flat records."""
    categories = ["A", "B", "C", "D"]
    return [
        {
            "id": i + 1,
            "label": _random_string(4, 10),
            "value": round(random.uniform(0, 1000), 2),
            "category": random.choice(categories),
            "active": random.choice([True, False]),
        }
        for i in range(n)
    ]


GENERATORS = {
    "Flat Dictionary": generate_flat_dict,
    "Nested Dictionary": generate_nested_dict,
    "User Records": generate_user_records,
    "Config File": generate_config_file,
    "All HBN Types": generate_mixed_types,
    "List of Records": generate_list_of_dicts,
}
