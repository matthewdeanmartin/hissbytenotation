"""Interactive REPL support for the CLI."""

from __future__ import annotations

import argparse
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

from hissbytenotation.cli.codecs import infer_format_from_path, normalize_format_name, parse_value
from hissbytenotation.cli.doctor import collect_doctor_report
from hissbytenotation.cli.errors import CliError, FileIOCliError, InputParseError, MissingValueError, OperationTypeError
from hissbytenotation.cli.glom_integration import append_value, delete_value, insert_value, query_value, set_value
from hissbytenotation.cli.merge_ops import CONFLICT_POLICIES, MERGE_STRATEGIES, merge_values
from hissbytenotation.cli.presenters import apply_default, render_output

REPL_HELP = """REPL commands:
  load VALUE                          load a new current value from HBN / Python literal syntax
  read PATH [--from FMT]              load a value from a file
  show [render-options]               print the current value
  type | keys | values | items | len  inspect the current value
  get PATH [render-options]           read a nested value
  q PATH [render-options]             query with a simple path
  q --glom SPEC [render-options]      query with an explicit glom spec
  set PATH --value VALUE              update a nested value in memory
  del PATH                            delete a nested value in memory
  append PATH --value VALUE           append into a nested list in memory
  insert PATH --index N --value VALUE insert into a nested list in memory
  merge --value VALUE                 merge the current value with an HBN value
  merge --file PATH                   merge the current value with a file
  write PATH [--to FMT]               write the current value to a file
  doctor [render-options]             inspect optional capabilities
  examples                            show REPL examples
  reset                               clear the current value
  quit | exit                         leave the REPL

Render options:
  --to FMT --pretty --compact --sort-keys --indent N
  --raw --lines --nul --shell-quote --shell-assign NAME --shell-export NAME
  --bash-array NAME --bash-assoc NAME --default VALUE
"""

REPL_EXAMPLES = """REPL examples:
  load {'users': [{'email': 'a@example.com'}]}
  get users.0.email --raw
  set users.0.role --value "'admin'"
  merge --value "{'users': [{'email': 'b@example.com'}]}" --strategy append-lists
  write session.json --to json --pretty
"""


class ReplArgumentParser(argparse.ArgumentParser):
    """ArgumentParser variant that raises CLI-friendly errors."""

    def error(self, message: str) -> NoReturn:
        raise InputParseError(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if status:
            raise InputParseError(message.strip() if message else "Invalid REPL command.")
        raise _ReplEarlyExit()


class _ReplEarlyExit(Exception):
    """Internal sentinel used for REPL help output."""


@dataclass
class ReplSession:
    """Mutable REPL session state."""

    current_value: Any | None = None
    current_path: str | None = None


def run_repl(*, initial_value: Any | None = None, initial_path: str | None = None, prompt: str = "hbn> ") -> int:
    """Run the interactive REPL loop."""
    session = ReplSession(current_value=initial_value, current_path=initial_path)
    interactive = sys.stdin.isatty()
    if interactive:
        print("hbn repl. Use `help` for commands and `quit` to exit.")
        if session.current_value is not None:
            print(f"Loaded {type_name_for_value(session.current_value)} from startup input.")
    while True:
        try:
            line = _read_line(prompt, interactive=interactive)
        except EOFError:
            if interactive:
                print()
            return 0
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            should_exit = execute_line(session, stripped)
        except _ReplEarlyExit:
            continue
        except CliError as exc:
            print(str(exc), file=sys.stderr)
            continue
        if should_exit:
            return 0


def execute_line(session: ReplSession, line: str) -> bool:
    """Execute a single REPL command line."""
    command, _, remainder = line.strip().partition(" ")
    command = command.lower()
    if command == "load":
        parsed = _parse_load_line(remainder)
        session.current_value = parse_value(parsed.value_text, parsed.from_format, strict=False)
        session.current_path = None
        print(f"Loaded {type_name_for_value(session.current_value)}.")
        return False
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError as exc:
        raise InputParseError(f"Could not parse REPL command: {exc}") from exc
    if not tokens:
        return False
    command = tokens[0].lower()
    argv = tokens[1:]
    if command in {"quit", "exit"}:
        return True
    if command == "help":
        _handle_help(argv)
        return False
    if command == "examples":
        print(REPL_EXAMPLES, end="")
        return False
    if command == "reset":
        session.current_value = None
        session.current_path = None
        print("Cleared current value.")
        return False
    if command == "read":
        parsed = _parse_read_args(argv)
        session.current_value = _read_value_from_path(parsed.path, parsed.from_format)
        session.current_path = parsed.path
        print(f"Loaded {type_name_for_value(session.current_value)} from {parsed.path}.")
        return False
    if command in {"show", "dump"}:
        _emit_value(_require_current_value(session), _parse_output_args(argv))
        return False
    if command == "type":
        _emit_value(type_name_for_value(_require_current_value(session)), _parse_scalar_args(argv))
        return False
    if command == "keys":
        value = _require_current_value(session)
        if not isinstance(value, dict):
            raise OperationTypeError("keys requires a dict current value.")
        _emit_value(list(value.keys()), _parse_output_args(argv))
        return False
    if command == "values":
        value = _require_current_value(session)
        if not isinstance(value, dict):
            raise OperationTypeError("values requires a dict current value.")
        _emit_value(list(value.values()), _parse_output_args(argv))
        return False
    if command == "items":
        value = _require_current_value(session)
        if not isinstance(value, dict):
            raise OperationTypeError("items requires a dict current value.")
        _emit_value(list(value.items()), _parse_output_args(argv))
        return False
    if command in {"len", "count"}:
        value = _require_current_value(session)
        if not isinstance(value, (str, bytes, list, tuple, dict, set)):
            raise OperationTypeError("len requires a sized current value.")
        _emit_value(len(value), _parse_scalar_args(argv))
        return False
    if command == "get":
        parsed = _parse_query_args(argv, require_path=True)
        result = query_value(
            _require_current_value(session),
            path_text=parsed.query_path,
            default_on_missing=parsed.default is not None,
        )
        _emit_value(result, parsed)
        return False
    if command in {"q", "query"}:
        parsed = _parse_query_args(argv, require_path=False)
        result = query_value(
            _require_current_value(session),
            path_text=getattr(parsed, "query_path", None),
            spec_text=parsed.glom_spec,
            spec_file_path=parsed.spec_file_path,
            default_on_missing=parsed.default is not None,
        )
        _emit_value(result, parsed)
        return False
    if command == "set":
        parsed = _parse_value_mutation_args(argv, command_name="set", index_required=False)
        session.current_value = set_value(
            _require_current_value(session), parsed.query_path, parse_value(" ".join(parsed.value_text), "hbn")
        )
        print(f"Updated {type_name_for_value(session.current_value)}.")
        return False
    if command in {"del", "delete", "remove"}:
        parsed = _parse_delete_args(argv)
        session.current_value = delete_value(_require_current_value(session), parsed.query_path)
        print(f"Updated {type_name_for_value(session.current_value)}.")
        return False
    if command == "append":
        parsed = _parse_value_mutation_args(argv, command_name="append", index_required=False)
        session.current_value = append_value(
            _require_current_value(session), parsed.query_path, parse_value(" ".join(parsed.value_text), "hbn")
        )
        print(f"Updated {type_name_for_value(session.current_value)}.")
        return False
    if command == "insert":
        parsed = _parse_value_mutation_args(argv, command_name="insert", index_required=True)
        session.current_value = insert_value(
            _require_current_value(session),
            parsed.query_path,
            parsed.index,
            parse_value(" ".join(parsed.value_text), "hbn"),
        )
        print(f"Updated {type_name_for_value(session.current_value)}.")
        return False
    if command == "merge":
        parsed = _parse_merge_args(argv)
        other_value = (
            _read_value_from_path(parsed.file_path, parsed.from_format)
            if parsed.file_path
            else parse_value(" ".join(parsed.value_text), parsed.from_format, strict=parsed.strict)
        )
        session.current_value = merge_values(
            _require_current_value(session),
            other_value,
            strategy=parsed.strategy,
            conflict=parsed.conflict,
            strict=parsed.strict,
        )
        print(f"Merged into {type_name_for_value(session.current_value)}.")
        return False
    if command == "write":
        parsed = _parse_write_args(argv)
        output_format = parsed.to_format or infer_format_from_path(parsed.path, output=True)
        render_args = _output_namespace(
            to_format=normalize_format_name(output_format, output=True),
            pretty=parsed.pretty,
            compact=parsed.compact,
            sort_keys=parsed.sort_keys,
            indent=parsed.indent,
        )
        output_text = render_output(_require_current_value(session), render_args)
        if output_text and not output_text.endswith("\n"):
            output_text = f"{output_text}\n"
        try:
            Path(parsed.path).write_text(output_text, encoding="utf-8")
        except OSError as exc:
            raise FileIOCliError(f"Could not write {parsed.path}: {exc}") from exc
        session.current_path = parsed.path
        print(f"Wrote {parsed.path}.")
        return False
    if command == "doctor":
        _emit_value(collect_doctor_report(), _parse_output_args(argv, allow_to=True))
        return False
    raise InputParseError(f"Unknown REPL command: {command}")


def _handle_help(argv: list[str]) -> None:
    """Render REPL help."""
    if not argv or argv[0] in {"repl", "commands"}:
        print(REPL_HELP, end="")
        return
    if argv[0] == "examples":
        print(REPL_EXAMPLES, end="")
        return
    raise InputParseError(f"Unknown REPL help topic: {argv[0]}")


def _parse_load_line(remainder: str) -> argparse.Namespace:
    """Parse a load command while preserving literal quotes."""
    if not remainder.strip():
        raise InputParseError("load requires a value.")
    rest = remainder.strip()
    if rest.startswith("--from "):
        parts = rest.split(None, 2)
        if len(parts) < 3:
            raise InputParseError("load --from requires both a format and a value.")
        return argparse.Namespace(from_format=parts[1], value_text=parts[2])
    return argparse.Namespace(from_format="hbn", value_text=rest)


def _parse_read_args(argv: list[str]) -> argparse.Namespace:
    parser = ReplArgumentParser(prog="read", add_help=False)
    parser.add_argument("--from", dest="from_format")
    parser.add_argument("path")
    return parser.parse_args(argv)


def _parse_query_args(argv: list[str], *, require_path: bool) -> argparse.Namespace:
    parser = ReplArgumentParser(prog="query", add_help=False)
    spec_group = parser.add_mutually_exclusive_group()
    spec_group.add_argument("--glom", dest="glom_spec")
    spec_group.add_argument("--spec-file", dest="spec_file_path")
    parser.add_argument("query_path", nargs=None if require_path else "?")
    _add_output_arguments(parser, allow_to=True)
    parsed = parser.parse_args(argv)
    if require_path and not parsed.query_path:
        raise InputParseError("get requires a query path.")
    if not require_path and not any((parsed.query_path, parsed.glom_spec, parsed.spec_file_path)):
        raise InputParseError("Provide a simple path, --glom, or --spec-file.")
    return parsed


def _parse_value_mutation_args(argv: list[str], *, command_name: str, index_required: bool) -> argparse.Namespace:
    parser = ReplArgumentParser(prog=command_name, add_help=False)
    parser.add_argument("query_path")
    if index_required:
        parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--value", dest="value_text", nargs="+", required=True)
    return parser.parse_args(argv)


def _parse_delete_args(argv: list[str]) -> argparse.Namespace:
    parser = ReplArgumentParser(prog="del", add_help=False)
    parser.add_argument("query_path")
    return parser.parse_args(argv)


def _parse_merge_args(argv: list[str]) -> argparse.Namespace:
    parser = ReplArgumentParser(prog="merge", add_help=False)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--value", dest="value_text", nargs="+")
    source_group.add_argument("--file", dest="file_path")
    parser.add_argument("--from", dest="from_format")
    parser.add_argument("--strategy", choices=MERGE_STRATEGIES, default="deep")
    parser.add_argument("--conflict", choices=CONFLICT_POLICIES, default="error")
    parser.add_argument("--strict", action="store_true")
    parsed = parser.parse_args(argv)
    if parsed.value_text is not None and parsed.from_format is None:
        parsed.from_format = "hbn"
    return parsed


def _parse_write_args(argv: list[str]) -> argparse.Namespace:
    parser = ReplArgumentParser(prog="write", add_help=False)
    parser.add_argument("--to", dest="to_format")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--sort-keys", action="store_true")
    parser.add_argument("--indent", type=int)
    parser.add_argument("path")
    return parser.parse_args(argv)


def _parse_output_args(argv: list[str], *, allow_to: bool = True) -> argparse.Namespace:
    parser = ReplArgumentParser(prog="show", add_help=False)
    _add_output_arguments(parser, allow_to=allow_to)
    return parser.parse_args(argv)


def _parse_scalar_args(argv: list[str]) -> argparse.Namespace:
    parsed = _parse_output_args(argv, allow_to=False)
    parsed.raw = True
    return parsed


def _add_output_arguments(parser: argparse.ArgumentParser, *, allow_to: bool) -> None:
    if allow_to:
        parser.add_argument("--to", dest="to_format")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--sort-keys", action="store_true")
    parser.add_argument("--indent", type=int)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--lines", action="store_true")
    parser.add_argument("--nul", action="store_true")
    parser.add_argument("--shell-quote", action="store_true")
    parser.add_argument("--shell-assign")
    parser.add_argument("--shell-export")
    parser.add_argument("--bash-array")
    parser.add_argument("--bash-assoc")
    parser.add_argument("--default")


def _emit_value(value: Any, args: argparse.Namespace) -> None:
    value = apply_default(value, getattr(args, "default", None))
    output_text = render_output(value, args)
    if output_text and not getattr(args, "nul", False) and not output_text.endswith("\0"):
        output_text = f"{output_text}\n"
    sys.stdout.write(output_text)


def _read_value_from_path(path: str, format_name: str | None) -> Any:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise FileIOCliError(f"Could not read {path}: {exc}") from exc
    return parse_value(text, format_name or infer_format_from_path(path, output=False))


def _read_line(prompt: str, *, interactive: bool) -> str:
    if interactive:
        return input(prompt)
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return line.rstrip("\r\n")


def _require_current_value(session: ReplSession) -> Any:
    if session.current_value is None:
        raise MissingValueError("No value is loaded. Use `load` or `read` first.")
    return session.current_value


def _output_namespace(**overrides: Any) -> SimpleNamespace:
    values = {
        "to_format": None,
        "pretty": False,
        "compact": False,
        "sort_keys": False,
        "indent": None,
        "raw": False,
        "lines": False,
        "nul": False,
        "shell_quote": False,
        "shell_assign": None,
        "shell_export": None,
        "bash_array": None,
        "bash_assoc": None,
        "default": None,
        "strict": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def type_name_for_value(value: Any) -> str:
    """Return a friendly type name for REPL status output."""
    if value is None:
        return "none"
    if value is Ellipsis:
        return "ellipsis"
    return type(value).__name__
