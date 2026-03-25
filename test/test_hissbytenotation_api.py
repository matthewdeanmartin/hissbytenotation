import ast
import importlib
import sys
import types

import pytest

import hissbytenotation as hbn
from hissbytenotation.serialize_deserialize import HissByteNotationException


@pytest.fixture(autouse=True)
def cleanup_temp_import_module():
    yield
    sys.modules.pop("temp_dict_module", None)


@pytest.mark.parametrize(
    "source_code",
    [
        "42",
        "-7",
        "3.14",
        "'hello'",
        "b'bytes'",
        "True",
        "False",
        "None",
        "(1, 2, 3)",
        "[1, 'two', 3.0]",
        "{'a': 1, 'b': [2, 3]}",
        "{'nested': {'deep': (1, 2)}}",
        "[]",
        "{}",
        "()",
        "(42,)",
    ],
)
def test_loads_matches_ast_literal_eval_for_supported_literals(source_code):
    assert hbn.loads(source_code) == ast.literal_eval(source_code)


def test_dumps_roundtrips_nested_literal_data():
    data = {
        "name": "serpent",
        "numbers": [1, 2, 3],
        "nested": {"tuple": ("a", "b"), "flag": True},
        "payload": b"hiss",
        "nothing": None,
    }

    assert hbn.loads(hbn.dumps(data)) == data


def test_dumps_rejects_non_literal_roundtrip_when_validation_enabled():
    with pytest.raises(HissByteNotationException, match="Can't round trip"):
        hbn.dumps(frozenset({1, 2}))


def test_dumps_allows_non_literal_roundtrip_when_validation_disabled():
    dumped = hbn.dumps(frozenset({1, 2}), validate=False)

    assert dumped.startswith("frozenset(")


def test_safe_loads_does_not_execute_code():
    with pytest.raises((ValueError, SyntaxError)):
        hbn.loads("__import__('os').system('echo unsafe')")


def test_unsafe_loader_modes_can_parse_non_literals():
    source_code = "frozenset({1, 2})"

    assert hbn.loads(source_code, by_eval=True) == frozenset({1, 2})
    assert hbn.loads(source_code, by_exec=True) == frozenset({1, 2})


def test_loads_by_import_roundtrips_data_and_writes_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = {"value": [1, 2, 3], "flag": True}

    assert hbn.loads(hbn.dumps(data), by_import=True) == data
    assert (tmp_path / "temp_dict_module.py").read_text(encoding="utf-8").startswith("data = ")


def test_loads_by_import_reloads_updated_contents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert hbn.loads("{'value': 1}", by_import=True) == {"value": 1}
    assert hbn.loads("{'value': 2}", by_import=True) == {"value": 2}


def test_loads_by_rust_uses_extension_module_when_available(monkeypatch):
    rust_module = types.ModuleType("hbn_rust")
    rust_module.loads = lambda source_code: {"parsed": source_code}
    monkeypatch.setitem(sys.modules, "hissbytenotation.hbn_rust", rust_module)
    monkeypatch.setitem(sys.modules, "hbn_rust", rust_module)

    assert hbn.loads("{'value': 1}", by_rust=True) == {"parsed": "{'value': 1}"}


def test_loads_by_rust_raises_helpful_error_when_extension_missing(monkeypatch):
    real_import_module = importlib.import_module

    def fake_import_module(name, *args, **kwargs):
        if name in {"hbn_rust", "hissbytenotation.hbn_rust"}:
            raise ImportError("missing test module")
        return real_import_module(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "hissbytenotation.hbn_rust", raising=False)
    monkeypatch.delitem(sys.modules, "hbn_rust", raising=False)
    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(ImportError, match="Optional Rust acceleration is unavailable"):
        hbn.loads("[]", by_rust=True)
