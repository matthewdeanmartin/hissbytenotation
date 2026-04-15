import io
import json
import builtins
import sys
from types import SimpleNamespace

from hissbytenotation.cli import main
from hissbytenotation.cli.errors import EXTERNAL_TOOL_MISSING


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


def test_diff_builtin_reports_difference(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["diff", "--tool", "builtin", "--to", "json", "--compact", "--left-arg", "{'a': 1}", "--right-arg", "{'a': 2}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == 1
    assert "--- left" in stdout
    assert "+++ right" in stdout
    assert '-{"a":1}' in stdout
    assert '+{"a":2}' in stdout
    assert stderr == ""


def test_diff_identical_inputs_returns_zero(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["diff", "--tool", "builtin", "--left-arg", "{'a': 1}", "--right-arg", "{'a': 1}"], capsys, monkeypatch
    )

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""


def test_diff_git_tool_requires_git_when_explicit(capsys, monkeypatch):
    from hissbytenotation.cli import diff_ops

    monkeypatch.setattr(diff_ops.shutil, "which", lambda _name: None)
    exit_code, stdout, stderr = run_cli(
        ["diff", "--tool", "git", "--left-arg", "{'a': 1}", "--right-arg", "{'a': 2}"], capsys, monkeypatch
    )

    assert exit_code == EXTERNAL_TOOL_MISSING
    assert stdout == ""
    assert "git" in stderr.lower()


def test_fmt_prefers_black_executable_when_available(capsys, monkeypatch, tmp_path):
    from hissbytenotation import cli

    monkeypatch.setattr(cli.shutil, "which", lambda name: str(tmp_path / "black.exe") if name == "black" else None)

    def fake_run(command, capture_output, text, check):
        target_path = command[-1]
        with open(target_path, "w", encoding="utf-8") as handle:
            handle.write("{'b': 2, 'a': 1}\n")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(cli, "black", None)

    exit_code, stdout, stderr = run_cli(["fmt", "--arg", "{'b':2,'a':1}"], capsys, monkeypatch)

    assert exit_code == 0
    assert stdout == "{'b': 2, 'a': 1}\n"
    assert stderr == ""


def test_validate_missing_dependency_returns_all_and_specific_hint(capsys, monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cerberus":
            raise ImportError("missing test module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    exit_code, stdout, stderr = run_cli(
        ["validate", "--arg", "{'a': 1}", "--schema", "{'a': {'type': 'integer'}}"], capsys, monkeypatch
    )

    assert exit_code == EXTERNAL_TOOL_MISSING
    assert stdout == ""
    assert "hissbytenotation[all]" in stderr
    assert "hissbytenotation[validate]" in stderr


def test_doctor_reports_diff_capability(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["doctor", "--to", "json", "--compact"], capsys, monkeypatch)

    report = json.loads(stdout)
    assert exit_code == 0
    assert report["optional_features"]["diff"]["available"] is True
    assert report["optional_features"]["diff"]["summary"]
    assert stderr == ""


def test_help_diff_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["help", "diff"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Diff helper" in stdout
    assert stderr == ""
