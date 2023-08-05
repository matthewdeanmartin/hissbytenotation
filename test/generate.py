import random
import string


def generate_random_string(length):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def generate_test_data(nesting_level=2):
    if nesting_level == 0:
        return {
            "string": generate_random_string(5),
            "bytes": b"sample bytes",
            "number": random.randint(1, 100),
            "tuple": ("element1", "element2"),
            "list": ["item1", "item2", "item3"],
            "dict": {"key1": "value1", "key2": "value2"},
            "set": {1, 2, 3, 4, 5},
            "boolean": random.choice([True, False]),
            "none": None,
            "ellipsis": Ellipsis,
        }
    else:
        return {
            "string": generate_random_string(5),
            "bytes": b"sample bytes",
            "number": random.randint(1, 100),
            "tuple": ("element1", "element2"),
            "list": [generate_test_data(nesting_level - 1) for _ in range(3)],
            "dict": {f"key{i}": generate_test_data(nesting_level - 1) for i in range(2)},
            "set": {1, 2, 3, 4, 5},
            "boolean": random.choice([True, False]),
            "none": None,
            "ellipsis": Ellipsis,
        }
