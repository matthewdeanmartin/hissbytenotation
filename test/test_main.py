import hissbytenotation as hbn
from test.generate import generate_test_data


def test_go():
    data = generate_test_data()
    repr(data)


def test_roundtrip():
    # Python object
    python_object = {
        "key1": "value1",
        "key2": ["item1", "item2"],
        "key3": {"subkey1": "subvalue1"},
    }

    # Convert Python object to source code
    source_code = hbn.dumps(python_object)
    print("Source Code:")
    print(source_code)
    print("\n")

    # Convert source code back to Python object
    restored_python_object = hbn.loads(source_code)
    print("Restored Python Object:")
    print(restored_python_object)
