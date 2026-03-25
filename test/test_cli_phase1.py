import io
import json
import sys

from hissbytenotation.cli import main
from hissbytenotation.cli.errors import EXTERNAL_TOOL_MISSING, FALSEY_RESULT, TYPE_MISMATCH, UNSUPPORTED_FORMAT


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


def test_dump_outputs_hbn(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["dump", "--arg", "{'a': 1}"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "{'a': 1}\n"
    assert stderr == ""


def test_convert_json_to_hbn(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["convert", "--from", "json", "--to", "hbn", "--arg", '{"a": 1}'], capsys, monkeypatch
    )

    assert exit_code == 0
    assert stdout == "{'a': 1}\n"
    assert stderr == ""


def test_convert_toml_to_json(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["convert", "--from", "toml", "--to", "json", "--arg", 'title = "hiss"\ncount = 2'],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert json.loads(stdout) == {"title": "hiss", "count": 2}
    assert stderr == ""


def test_convert_xml_to_json(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["convert", "--from", "xml", "--to", "json", "--arg", '<user id="1"><name>Matt</name></user>'],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert json.loads(stdout) == {"user": {"@attrs": {"id": "1"}, "name": "Matt"}}
    assert stderr == ""


def test_type_defaults_to_raw_text(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["type", "--arg", "{'a': 1}"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "dict\n"
    assert stderr == ""


def test_keys_lines_output(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["keys", "--arg", "{'a': 1, 'b': 2}", "--lines"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "a\nb\n"
    assert stderr == ""


def test_values_nul_output(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["values", "--arg", "{'a': 1, 'b': 2}", "--nul"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "1\0002"
    assert stderr == ""


def test_default_replaces_empty_result(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["keys", "--arg", "{}", "--default", "'missing'", "--raw"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "missing\n"
    assert stderr == ""


def test_exit_status_for_falsey_result(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["values", "--arg", "{}", "--exit-status"], capsys, monkeypatch)

    assert exit_code == FALSEY_RESULT
    assert stdout == ""
    assert stderr == ""


def test_shell_quote_output(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["dump", "--arg", "'hello world'", "--shell-quote"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "'hello world'\n"
    assert stderr == ""


def test_bash_array_output(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["dump", "--arg", "['a', 'b']", "--bash-array", "items"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "items=(a b)\n"
    assert stderr == ""


def test_bash_assoc_output(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["dump", "--arg", "{'host': 'db', 'port': '5432'}", "--bash-assoc", "cfg"],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert "declare -A cfg=(" in stdout
    assert "[host]=db" in stdout
    assert "[port]=5432" in stdout
    assert stderr == ""


def test_raw_requires_scalar(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["dump", "--arg", "['a', 'b']", "--raw"], capsys, monkeypatch)

    assert exit_code == TYPE_MISMATCH
    assert stdout == ""
    assert "--raw requires a scalar result." in stderr


def test_fmt_formats_hbn(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["fmt", "--arg", "{'b':2,'a':1}"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == '{"b": 2, "a": 1}\n'
    assert stderr == ""


def test_fmt_missing_dependency_returns_all_and_specific_hint(capsys, monkeypatch):
    from hissbytenotation import cli

    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)
    monkeypatch.setattr(cli, "black", None)

    exit_code, stdout, stderr = run_cli(["fmt", "--arg", "{'b':2,'a':1}"], capsys, monkeypatch)

    assert exit_code == EXTERNAL_TOOL_MISSING
    assert stdout == ""
    assert 'hissbytenotation[all]' in stderr
    assert 'hissbytenotation[fmt]' in stderr


def test_help_shell_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["help", "shell"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Shell output helpers" in stdout
    assert stderr == ""


def test_examples_bash_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["examples", "bash"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Bash examples" in stdout
    assert stderr == ""


def test_completion_bash(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["completion", "bash"], capsys, monkeypatch)

    assert exit_code == 0
    assert "_hbn_complete" in stdout
    assert stderr == ""


def test_unsupported_output_format_has_stable_exit_code(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["convert", "--from", "json", "--to", "toml", "--arg", '{"a": 1}'],
        capsys,
        monkeypatch,
    )

    assert exit_code == UNSUPPORTED_FORMAT
    assert stdout == ""
    assert "Unsupported output format" in stderr
