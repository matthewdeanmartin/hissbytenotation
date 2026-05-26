# Test if the data is json serializable
import json
from test.generate import generate_test_data

from hissbytenotation.dump_to_json import CustomEncoder


def test_interop():
    test_data = generate_test_data()
    result = json.dumps(test_data, cls=CustomEncoder)
    assert result
