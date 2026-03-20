"""Tests for the Rust-accelerated parser."""

import pytest

try:
    import hbn_rust

    HAS_RUST = True
except ImportError:
    HAS_RUST = False

import hissbytenotation as hbn
from test.generate import generate_test_data


@pytest.mark.skipif(not HAS_RUST, reason="hbn_rust not installed")
class TestRustParser:
    def test_roundtrip_simple_dict(self):
        python_object = {
            "key1": "value1",
            "key2": ["item1", "item2"],
            "key3": {"subkey1": "subvalue1"},
        }
        source_code = hbn.dumps(python_object)
        restored = hbn.loads(source_code, by_rust=True)
        assert restored == python_object

    def test_roundtrip_with_types(self):
        python_object = {
            "string": "hello",
            "number": 42,
            "boolean": True,
            "none": None,
            "list": [1, 2, 3],
            "tuple": (1, 2, 3),
            "nested": {"a": {"b": "c"}},
        }
        source_code = hbn.dumps(python_object)
        restored = hbn.loads(source_code, by_rust=True)
        assert restored == python_object

    def test_roundtrip_bytes(self):
        python_object = {"data": b"hello bytes"}
        source_code = hbn.dumps(python_object)
        restored = hbn.loads(source_code, by_rust=True)
        assert restored == python_object

    def test_roundtrip_set(self):
        python_object = {1, 2, 3, 4, 5}
        source_code = hbn.dumps(python_object)
        restored = hbn.loads(source_code, by_rust=True)
        assert restored == python_object

    def test_roundtrip_ellipsis(self):
        python_object = {"ellipsis": Ellipsis}
        source_code = hbn.dumps(python_object, validate=False)
        restored = hbn.loads(source_code, by_rust=True)
        assert restored == python_object

    def test_roundtrip_generated_no_bytes_no_sets_no_ellipsis(self):
        """Test with generated data that's JSON-compatible."""
        data = generate_test_data(no_bytes=True, no_sets=True, no_elipsis=True)
        source_code = hbn.dumps(data, validate=False)
        restored = hbn.loads(source_code, by_rust=True)
        assert restored == data

    def test_roundtrip_generated_full(self):
        """Test with generated data including all types."""
        data = generate_test_data()
        source_code = hbn.dumps(data, validate=False)
        restored = hbn.loads(source_code, by_rust=True)
        assert restored == data

    def test_negative_numbers(self):
        assert hbn_rust.loads("-42") == -42
        assert hbn_rust.loads("-3.14") == -3.14

    def test_empty_collections(self):
        assert hbn_rust.loads("{}") == {}
        assert hbn_rust.loads("[]") == []
        assert hbn_rust.loads("()") == ()

    def test_single_element_tuple(self):
        assert hbn_rust.loads("(1,)") == (1,)

    def test_nested_quotes(self):
        assert hbn_rust.loads("'hello \\'world\\''") == "hello 'world'"

    def test_string_escapes(self):
        assert hbn_rust.loads(r"'hello\nworld'") == "hello\nworld"
        assert hbn_rust.loads(r"'tab\there'") == "tab\there"

    def test_trailing_commas(self):
        assert hbn_rust.loads("[1, 2, 3,]") == [1, 2, 3]
        assert hbn_rust.loads("{'a': 1, 'b': 2,}") == {"a": 1, "b": 2}

    def test_matches_ast_literal_eval(self):
        """Verify Rust parser produces identical results to ast.literal_eval."""
        import ast

        test_cases = [
            "42",
            "-7",
            "3.14",
            "'hello'",
            "b'bytes'",
            "True",
            "False",
            "None",
            "...",
            "(1, 2, 3)",
            "[1, 'two', 3.0]",
            "{'a': 1, 'b': [2, 3]}",
            "{'nested': {'deep': (1, 2)}}",
            "[]",
            "{}",
            "()",
            "(42,)",
        ]
        for case in test_cases:
            rust_result = hbn_rust.loads(case)
            py_result = ast.literal_eval(case)
            assert rust_result == py_result, f"Mismatch for {case!r}: rust={rust_result!r} vs py={py_result!r}"
