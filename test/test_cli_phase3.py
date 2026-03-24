import io
import json
import sys

from hissbytenotation import loads as hbn_loads
from hissbytenotation.cli import main
from hissbytenotation.cli.errors import (
    MERGE_CONFLICT,
    PARSE_FAILURE,
    UNSUPPORTED_FORMAT,
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


def test_merge_deep_right_wins(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        [
            "merge",
            "--conflict",
            "right-wins",
            "--left-arg",
            "{'config': {'host': 'db', 'port': 5432}}",
            "--right-arg",
            "{'config': {'port': 6432, 'timeout': 30}}",
        ],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert hbn_loads(stdout) == {"config": {"host": "db", "port": 6432, "timeout": 30}}
    assert stderr == ""


def test_merge_shallow_replaces_nested_value(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        [
            "merge",
            "--strategy",
            "shallow",
            "--conflict",
            "right-wins",
            "--left-arg",
            "{'config': {'host': 'db', 'port': 5432}, 'name': 'left'}",
            "--right-arg",
            "{'config': {'timeout': 30}}",
        ],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert hbn_loads(stdout) == {"config": {"timeout": 30}, "name": "left"}
    assert stderr == ""


def test_merge_append_lists_recursively(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        [
            "merge",
            "--strategy",
            "append-lists",
            "--left-arg",
            "{'items': [1, 2]}",
            "--right-arg",
            "{'items': [3, 4]}",
        ],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert hbn_loads(stdout) == {"items": [1, 2, 3, 4]}
    assert stderr == ""


def test_merge_set_union_lists_preserves_order(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        [
            "merge",
            "--strategy",
            "set-union-lists",
            "--left-arg",
            "{'tags': ['a', 'b', 'c']}",
            "--right-arg",
            "{'tags': ['b', 'd']}",
        ],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert hbn_loads(stdout) == {"tags": ["a", "b", "c", "d"]}
    assert stderr == ""


def test_merge_conflict_error_has_stable_exit_code(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["merge", "--left-arg", "{'a': 1}", "--right-arg", "{'a': 2}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == MERGE_CONFLICT
    assert stdout == ""
    assert "Merge conflict" in stderr


def test_merge_strict_type_mismatch_errors_even_with_right_wins(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        [
            "merge",
            "--strict",
            "--conflict",
            "right-wins",
            "--left-arg",
            "{'a': {'nested': 1}}",
            "--right-arg",
            "{'a': [1, 2]}",
        ],
        capsys,
        monkeypatch,
    )

    assert exit_code == MERGE_CONFLICT
    assert stdout == ""
    assert "Type mismatch" in stderr


def test_merge_to_json(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        [
            "merge",
            "--conflict",
            "right-wins",
            "--to",
            "json",
            "--left-arg",
            "{'a': 1}",
            "--right-arg",
            "{'b': 2}",
        ],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert json.loads(stdout) == {"a": 1, "b": 2}
    assert stderr == ""


def test_merge_check_validates_without_output(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        [
            "merge",
            "--check",
            "--conflict",
            "right-wins",
            "--left-arg",
            "{'a': 1}",
            "--right-arg",
            "{'a': 2}",
        ],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""


def test_merge_in_place_writes_left_file(capsys, monkeypatch, tmp_path):
    left_path = tmp_path / "left.hbn"
    left_path.write_text("{'a': 1, 'b': 2}", encoding="utf-8")

    exit_code, stdout, stderr = run_cli(
        [
            "merge",
            "--in-place",
            "--conflict",
            "right-wins",
            str(left_path),
            "--right-arg",
            "{'b': 20, 'c': 3}",
        ],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""
    assert hbn_loads(left_path.read_text(encoding="utf-8")) == {"a": 1, "b": 20, "c": 3}


def test_set_in_place_updates_hbn_file(capsys, monkeypatch, tmp_path):
    data_path = tmp_path / "data.hbn"
    data_path.write_text("{'a': {'port': 5432}}", encoding="utf-8")

    exit_code, stdout, stderr = run_cli(
        ["set", "a.port", "--value", "6432", "--in-place", str(data_path)],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""
    assert hbn_loads(data_path.read_text(encoding="utf-8")) == {"a": {"port": 6432}}


def test_append_in_place_creates_backup(capsys, monkeypatch, tmp_path):
    data_path = tmp_path / "data.hbn"
    data_path.write_text("{'items': [1, 2]}", encoding="utf-8")

    exit_code, stdout, stderr = run_cli(
        ["append", "items", "--value", "3", "--backup", ".bak", str(data_path)],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""
    assert hbn_loads(data_path.read_text(encoding="utf-8")) == {"items": [1, 2, 3]}
    assert hbn_loads((tmp_path / "data.hbn.bak").read_text(encoding="utf-8")) == {"items": [1, 2]}


def test_insert_in_place_atomic_on_json_file_preserves_json(capsys, monkeypatch, tmp_path):
    data_path = tmp_path / "data.json"
    data_path.write_text('{"items": ["a", "b"]}', encoding="utf-8")

    exit_code, stdout, stderr = run_cli(
        ["insert", "items", "--index", "1", "--value", "'x'", "--atomic", str(data_path)],
        capsys,
        monkeypatch,
    )

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""
    assert json.loads(data_path.read_text(encoding="utf-8")) == {"items": ["a", "x", "b"]}
    assert list(tmp_path.glob("*.tmp")) == []


def test_in_place_requires_file_backed_input(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["set", "a", "--value", "42", "--in-place", "--arg", "{'a': 1}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == PARSE_FAILURE
    assert stdout == ""
    assert "file-backed input" in stderr


def test_check_cannot_be_combined_with_output(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(
        ["append", "items", "--value", "3", "--check", "-o", "ignored.hbn", "--arg", "{'items': [1, 2]}"],
        capsys,
        monkeypatch,
    )

    assert exit_code == PARSE_FAILURE
    assert stdout == ""
    assert "--check cannot be combined with --output" in stderr


def test_in_place_toml_refuses_output_format(capsys, monkeypatch, tmp_path):
    data_path = tmp_path / "config.toml"
    data_path.write_text('title = "demo"\n', encoding="utf-8")

    exit_code, stdout, stderr = run_cli(
        ["set", "title", "--value", "'changed'", "--in-place", str(data_path)], capsys, monkeypatch
    )

    assert exit_code == UNSUPPORTED_FORMAT
    assert stdout == ""
    assert "format" in stderr.lower()


def test_help_merge_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["help", "merge"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Merge and file mutation helpers" in stdout
    assert stderr == ""


def test_examples_merge_topic(capsys, monkeypatch):
    exit_code, stdout, stderr = run_cli(["examples", "merge"], capsys, monkeypatch)

    assert exit_code == 0
    assert "Merge examples" in stdout
    assert stderr == ""
