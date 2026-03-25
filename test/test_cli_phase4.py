import io
import json
import sys

from hissbytenotation import loads as hbn_loads
from hissbytenotation.cli import main


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


def test_show_alias_outputs_hbn(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["show", "--arg", "{'a': 1}"], capsys, monkeypatch)

    assert exit_code == 0
    assert hbn_loads(stdout) == {"a": 1}
    assert stderr == ""


def test_delete_alias_removes_nested_key(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["delete", "a.b", "--arg", "{'a': {'b': 1, 'c': 2}}"], capsys, monkeypatch)

    assert exit_code == 0
    assert hbn_loads(stdout) == {"a": {"c": 2}}
    assert stderr == ""


def test_count_alias_outputs_length(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["count", "--arg", "[1, 2, 3]"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "3\n"
    assert stderr == ""


def test_doctor_json_report(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["doctor", "--to", "json", "--compact"], capsys, monkeypatch)

    report = json.loads(stdout)
    assert exit_code == 0
    assert report["package"]["name"] == "hissbytenotation"
    assert "optional_features" in report
    assert "glom" in report["optional_features"]
    assert 'hissbytenotation[all]' in report["optional_features"]["glom"]["install_hint"]
    assert 'hissbytenotation[glom]' in report["optional_features"]["glom"]["install_hint"]
    assert "recommendations" in report
    assert stderr == ""


def test_help_aliases_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["help", "aliases"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Command aliases" in stdout
    assert "show" in stdout
    assert stderr == ""


def test_examples_repl_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["examples", "repl"], capsys, monkeypatch)

    assert exit_code == 0
    assert "REPL examples" in stdout
    assert "hbn repl" in stdout
    assert stderr == ""


def test_completion_powershell_mentions_new_commands(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["completion", "powershell"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Register-ArgumentCompleter" in stdout
    assert "doctor" in stdout
    assert "show" in stdout
    assert stderr == ""


def test_repl_script_updates_current_value_and_writes_file(capsys, monkeypatch, tmp_path):
    output_path = tmp_path / "session.json"
    script = "\n".join(
        [
            "load {'users': [{'email': 'a@example.com'}]}",
            "get users.0.email --raw",
            "set users.0.role --value \"'admin'\"",
            "merge --value \"{'users': [{'email': 'b@example.com'}]}\" --strategy append-lists",
            "show --to json --compact",
            f'write "{output_path}" --to json --compact',
            "quit",
        ]
    )

    exit_code, stdout, stderr = run_cli(["repl"], capsys, monkeypatch, stdin_text=script)

    lines = stdout.splitlines()
    assert exit_code == 0
    assert lines[0] == "Loaded dict."
    assert lines[1] == "a@example.com"
    assert lines[2] == "Updated dict."
    assert lines[3] == "Merged into dict."
    assert json.loads(lines[4]) == {"users": [{"email": "a@example.com", "role": "admin"}, {"email": "b@example.com"}]}
    assert lines[5] == f"Wrote {output_path}."
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "users": [{"email": "a@example.com", "role": "admin"}, {"email": "b@example.com"}]
    }
    assert stderr == ""
