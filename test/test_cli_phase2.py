import io
import sys


from hissbytenotation import loads as hbn_loads
from hissbytenotation.cli import main
from hissbytenotation.cli.errors import (
    FILE_IO_ERROR,
    GLOM_FAILURE,
    MISSING_VALUE,
    PARSE_FAILURE,
    TYPE_MISMATCH,
)


class FakeStdin(io.StringIO):
    def isatty(self):
        return False


class FakeTTYStdin(io.StringIO):
    def isatty(self):
        return True


def run_cli(args, capsys, monkeypatch, stdin_text=None):
    if stdin_text is not None:
        monkeypatch.setattr(sys, "stdin", FakeStdin(stdin_text))
    else:
        monkeypatch.setattr(sys, "stdin", FakeTTYStdin())
    exit_code = main(args)
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def test_query_path_outputs_scalar_raw(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["q", "users.0.email", "--raw", "--arg", "{'users': [{'email': 'a@example.com'}]}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert stdout == "a@example.com\n"
    assert stderr == ""


def test_query_alias_with_glom_spec(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["query", "--glom", "{'emails': ('users', ['email'])}", "--arg", "{'users': [{'email': 'a@example.com'}]}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert hbn_loads(stdout) == {"emails": ["a@example.com"]}
    assert stderr == ""


def test_query_spec_file(capsys, monkeypatch, tmp_path):
    spec_path = tmp_path / "emails.glomspec"
    spec_path.write_text("{'emails': ('users', ['email'])}", encoding="utf-8")

    exit_code, stdout, stderr = run_cli(
        ["q", "--spec-file", str(spec_path), "--arg", "{'users': [{'email': 'a@example.com'}]}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert hbn_loads(stdout) == {"emails": ["a@example.com"]}
    assert stderr == ""


def test_get_missing_path_uses_default(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["get", "user.name", "--arg", "{}", "--default", "'unknown'", "--raw"],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert stdout == "unknown\n"
    assert stderr == ""


def test_query_missing_path_has_stable_exit_code(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["q", "missing.value", "--arg", "{}"], capsys, monkeypatch)

    assert exit_code == MISSING_VALUE
    assert stdout == ""
    assert "Missing query target" in stderr


def test_set_creates_nested_dicts(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["set", "a.b.c", "--value", "42", "--arg", "{}"], capsys, monkeypatch)

    assert exit_code == 0
    assert hbn_loads(stdout) == {"a": {"b": {"c": 42}}}
    assert stderr == ""


def test_del_removes_nested_key(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["del", "a.b", "--arg", "{'a': {'b': 1, 'c': 2}}"], capsys, monkeypatch)

    assert exit_code == 0
    assert hbn_loads(stdout) == {"a": {"c": 2}}
    assert stderr == ""


def test_append_adds_to_nested_list(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["append", "items", "--value", "{'name': 'new'}", "--arg", "{'items': [{'name': 'old'}]}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert hbn_loads(stdout) == {"items": [{"name": "old"}, {"name": "new"}]}
    assert stderr == ""


def test_insert_adds_at_requested_index(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["insert", "items", "--index", "1", "--value", "'x'", "--arg", "{'items': ['a', 'b']}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert hbn_loads(stdout) == {"items": ["a", "x", "b"]}
    assert stderr == ""


def test_append_requires_list_target(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["append", "items", "--value", "1", "--arg", "{'items': 'nope'}"], capsys, monkeypatch
    )

    assert exit_code == TYPE_MISMATCH
    assert stdout == ""
    assert "requires a list target" in stderr


def test_invalid_glom_spec_returns_parse_failure(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["q", "--glom", "{broken", "--arg", "{}"], capsys, monkeypatch)

    assert exit_code == PARSE_FAILURE
    assert stdout == ""
    assert "Could not parse glom spec" in stderr


def test_missing_spec_file_returns_file_error(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["q", "--spec-file", "missing.glomspec", "--arg", "{}"], capsys, monkeypatch)

    assert exit_code == FILE_IO_ERROR
    assert stdout == ""
    assert "Could not read spec file" in stderr


def test_missing_glom_dependency_returns_clear_error(capsys, monkeypatch):
    from hissbytenotation.cli import glom_integration

    monkeypatch.setattr(glom_integration, "glom", None)
    exit_code, stdout, stderr = run_cli(["q", "value", "--arg", "{'value': 1}"], capsys, monkeypatch)

    assert exit_code == GLOM_FAILURE
    assert stdout == ""
    assert "optional glom extra" in stderr
    assert "hissbytenotation[all]" in stderr
    assert "hissbytenotation[glom]" in stderr


def test_set_missing_value_flag_returns_parse_failure(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["set", "a.b", "--arg", "{}"], capsys, monkeypatch)

    assert exit_code == PARSE_FAILURE
    assert stdout == ""
    assert "required" in stderr.lower()


def test_help_glom_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["help", "glom"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Glom-powered queries" in stdout
    assert stderr == ""


def test_examples_glom_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["examples", "glom"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Glom examples" in stdout
    assert stderr == ""
