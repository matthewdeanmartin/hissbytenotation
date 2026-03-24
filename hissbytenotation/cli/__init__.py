"""Phase 1 CLI entrypoint for hissbytenotation."""

from __future__ import annotations

import argparse
import importlib.metadata
import sys
from pathlib import Path
from typing import Any

from hissbytenotation.cli.codecs import (
    infer_format_from_path,
    normalize_format_name,
    parse_value,
)
from hissbytenotation.cli.errors import (
    FALSEY_RESULT,
    INTERNAL_ERROR,
    CliError,
    ExternalToolError,
    FileIOCliError,
    InputParseError,
    OperationTypeError,
)
from hissbytenotation.cli.presenters import apply_default, render_output

black: Any = None
try:
    import black
except ImportError:  # pragma: no cover - exercised when the optional formatter is missing
    black = None

TOPIC_HELP = {
    "shell": """Shell output helpers:
  --raw                 emit scalar text without HBN/JSON quoting
  --lines               emit one sequence item per line
  --nul                 emit one sequence item per NUL byte
  --shell-quote         emit a single shell-escaped token
  --shell-assign NAME   emit NAME='...'
  --shell-export NAME   emit export NAME='...'
  --bash-array NAME     emit a Bash indexed array assignment
  --bash-assoc NAME     emit a Bash associative array assignment for flat dicts
  --default VALUE       substitute VALUE when the result is empty
""",
    "formats": """Supported formats:
  hbn   native Hiss Byte Notation / Python literal syntax
  json  stdlib JSON input and output
  toml  stdlib TOML input only
  xml   basic XML mapping using @attrs and #text
  bmn   Bash Map Notation for flat dicts and scalar arrays
""",
}

EXAMPLES = {
    "general": """Examples:
  hbn dump --arg "{'cat': 'snake'}"
  hbn convert --from json --to hbn --arg "{\\"cat\\": \\"snake\\"}"
  hbn type data.hbn
  hbn keys --lines data.hbn
  hbn fmt config.hbn
""",
    "bash": """Bash examples:
  hbn values --lines data.hbn
  hbn dump --arg "['a', 'b']" --bash-array items
  hbn dump --arg "{'host': 'db', 'port': '5432'}" --bash-assoc cfg
  hbn len --arg "[]" --default 0 --raw
  db_url=$(hbn dump --arg "'postgres://db'" --shell-quote)
""",
}

COMMAND_NAMES = {
    "dump",
    "fmt",
    "convert",
    "type",
    "keys",
    "values",
    "items",
    "len",
    "help",
    "examples",
    "completion",
    "version",
}


def main(argv: list[str] | None = None) -> int:
    """Run the phase 1 CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args, parser)
    except CliError as exc:
        if getattr(args, "debug", False):
            raise
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except BrokenPipeError:
        return FALSEY_RESULT
    except Exception as exc:  # pragma: no cover  # pylint: disable=broad-exception-caught
        if getattr(args, "debug", False):
            raise
        print(f"Internal error: {exc}", file=sys.stderr)
        return INTERNAL_ERROR


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(prog="hbn", description="Bash-first tools for Hiss Byte Notation.")
    subparsers = parser.add_subparsers(dest="command")

    data_parent = build_data_parent_parser()
    output_parent = build_output_parent_parser()

    dump_parser = subparsers.add_parser("dump", parents=[data_parent, output_parent], help="Render input as HBN.")
    dump_parser.set_defaults(handler=handle_dump, to_format="hbn")

    fmt_parser = subparsers.add_parser("fmt", parents=[data_parent], help="Format HBN input using black.")
    fmt_parser.add_argument("-o", "--output", dest="output_path", help="Write formatted output to a file.")
    fmt_parser.set_defaults(handler=handle_fmt)

    convert_parser = subparsers.add_parser(
        "convert",
        parents=[data_parent, output_parent],
        help="Convert between HBN, JSON, TOML input, XML, and BMN.",
    )
    convert_parser.add_argument("--to", dest="to_format", required=True, help="Target output format.")
    convert_parser.set_defaults(handler=handle_convert)

    for command_name, handler, help_text in (
        ("type", handle_type, "Show the root value type."),
        ("keys", handle_keys, "Show dict keys."),
        ("values", handle_values, "Show dict values."),
        ("items", handle_items, "Show dict items."),
        ("len", handle_len, "Show collection length."),
    ):
        command_parser = subparsers.add_parser(command_name, parents=[data_parent, output_parent], help=help_text)
        command_parser.set_defaults(handler=handler)

    help_parser = subparsers.add_parser("help", help="Show help for a topic.")
    help_parser.add_argument("topic", nargs="?", help="Topic such as shell or formats.")
    help_parser.set_defaults(handler=handle_help)

    examples_parser = subparsers.add_parser("examples", help="Show usage examples.")
    examples_parser.add_argument("topic", nargs="?", default="general", help="Example topic such as bash.")
    examples_parser.set_defaults(handler=handle_examples)

    completion_parser = subparsers.add_parser("completion", help="Emit shell completion scripts.")
    completion_parser.add_argument("shell", choices=["bash", "zsh", "fish"], help="Shell to target.")
    completion_parser.set_defaults(handler=handle_completion)

    version_parser = subparsers.add_parser("version", help="Show the installed version.")
    version_parser.set_defaults(handler=handle_version)

    return parser


def build_data_parent_parser() -> argparse.ArgumentParser:
    """Build common input arguments."""
    parser = argparse.ArgumentParser(add_help=False)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--file", dest="input_path", help="Read input from a file.")
    source_group.add_argument("--stdin", action="store_true", help="Read input from stdin.")
    source_group.add_argument("--arg", dest="input_text", help="Read input from a literal argument string.")
    parser.add_argument("path", nargs="?", help="Optional input file path.")
    parser.add_argument("--from", dest="from_format", help="Input format.")
    parser.add_argument("--strict", action="store_true", help="Refuse lossy conversions.")
    parser.add_argument("--default", help="Default value to use when the result is empty.")
    parser.add_argument("--exit-status", action="store_true", help="Return exit code 1 for falsey results.")
    parser.add_argument("--quiet", action="store_true", help="Suppress normal command output.")
    parser.add_argument("--verbose", action="store_true", help="Reserved for future verbose output.")
    parser.add_argument("--debug", action="store_true", help="Raise exceptions with tracebacks.")
    parser.add_argument("--color", action="store_true", help="Reserved for future colored output.")
    parser.add_argument("--no-color", action="store_true", help="Reserved for future plain output.")
    return parser


def build_output_parent_parser() -> argparse.ArgumentParser:
    """Build common output arguments."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-o", "--output", dest="output_path", help="Write output to a file.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print structured output.")
    parser.add_argument("--compact", action="store_true", help="Emit compact structured output.")
    parser.add_argument("--sort-keys", action="store_true", help="Sort mapping keys when supported.")
    parser.add_argument("--indent", type=int, help="Indentation width when pretty-printing.")
    parser.add_argument("--raw", action="store_true", help="Emit raw scalar text when possible.")
    parser.add_argument("--lines", action="store_true", help="Emit one sequence item per line.")
    parser.add_argument("--nul", action="store_true", help="Emit one sequence item per NUL byte.")
    parser.add_argument("--shell-quote", action="store_true", help="Emit a single shell-escaped token.")
    parser.add_argument("--shell-assign", metavar="NAME", help="Emit NAME='...'.")
    parser.add_argument("--shell-export", metavar="NAME", help="Emit export NAME='...'.")
    parser.add_argument("--bash-array", metavar="NAME", help="Emit a Bash indexed array assignment.")
    parser.add_argument("--bash-assoc", metavar="NAME", help="Emit a Bash associative array assignment.")
    return parser


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Dispatch to the selected command handler."""
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args, parser)


def handle_dump(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Render the input value as HBN."""
    value = load_input_value(args)
    return emit_result(value, args)


def handle_convert(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Convert the input value to another output format."""
    args.to_format = normalize_format_name(args.to_format, output=True)
    value = load_input_value(args)
    return emit_result(value, args)


def handle_type(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Show the root value type name."""
    value = load_input_value(args)
    if not any(
        (
            args.lines,
            args.nul,
            args.shell_quote,
            args.shell_assign,
            args.shell_export,
            args.bash_array,
            args.bash_assoc,
        )
    ):
        args.raw = True
    return emit_result(type_name_for_value(value), args)


def handle_keys(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Show dictionary keys."""
    value = load_input_value(args)
    if not isinstance(value, dict):
        raise OperationTypeError("keys requires a dict root value.")
    return emit_result(list(value.keys()), args)


def handle_values(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Show dictionary values."""
    value = load_input_value(args)
    if not isinstance(value, dict):
        raise OperationTypeError("values requires a dict root value.")
    return emit_result(list(value.values()), args)


def handle_items(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Show dictionary items."""
    value = load_input_value(args)
    if not isinstance(value, dict):
        raise OperationTypeError("items requires a dict root value.")
    return emit_result(list(value.items()), args)


def handle_len(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Show the length of the root value."""
    value = load_input_value(args)
    if not isinstance(value, (str, bytes, list, tuple, dict, set)):
        raise OperationTypeError("len requires a sized root value.")
    return emit_result(len(value), args)


def handle_fmt(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Format HBN input using black."""
    source_text, _ = load_input_text(args)
    formatted_text = format_hbn_text(source_text)
    return write_output(formatted_text, args)


def handle_help(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Show general or topical help."""
    if not args.topic:
        parser.print_help()
        return 0
    topic = args.topic.lower()
    if topic in TOPIC_HELP:
        print(TOPIC_HELP[topic], end="")
        return 0
    if topic in EXAMPLES:
        print(EXAMPLES[topic], end="")
        return 0
    if topic in COMMAND_NAMES:
        try:
            build_parser().parse_args([topic, "--help"])
        except SystemExit as exc:
            return int(exc.code or 0)
        return 0
    raise InputParseError(f"Unknown help topic: {args.topic}")


def handle_examples(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Show canned usage examples."""
    topic = args.topic.lower()
    if topic not in EXAMPLES:
        raise InputParseError(f"Unknown examples topic: {args.topic}")
    print(EXAMPLES[topic], end="")
    return 0


def handle_completion(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Emit a minimal shell completion script."""
    scripts = {
        "bash": """_hbn_complete() {
    local commands=\"dump fmt convert type keys values items len help examples completion version\"
    COMPREPLY=( $(compgen -W \"$commands\" -- \"${COMP_WORDS[COMP_CWORD]}\") )
}
complete -F _hbn_complete hbn hissbytenotation
""",
        "zsh": """#compdef hbn hissbytenotation
local -a commands
commands=(dump fmt convert type keys values items len help examples completion version)
_describe 'command' commands
""",
        "fish": """complete -c hbn -f -a "dump fmt convert type keys values items len help examples completion version"
complete -c hissbytenotation -f -a "dump fmt convert type keys values items len help examples completion version"
""",
    }
    print(scripts[args.shell], end="")
    return 0


def handle_version(_args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Show the installed package version."""
    print(importlib.metadata.version("hissbytenotation"))
    return 0


def load_input_value(args: argparse.Namespace) -> Any:
    """Load and parse the input value."""
    source_text, input_path = load_input_text(args)
    from_format = args.from_format or infer_format_from_path(input_path, output=False)
    return parse_value(source_text, from_format, strict=args.strict)


def load_input_text(args: argparse.Namespace) -> tuple[str, str | None]:
    """Load raw input text from one of the supported sources."""
    input_path = args.input_path or args.path
    if args.input_path and args.path and args.input_path != args.path:
        raise InputParseError("Use only one input file path source.")
    explicit_non_file_sources = int(args.stdin) + int(args.input_text is not None)
    if input_path and explicit_non_file_sources:
        raise InputParseError("Use either a file path, --stdin, or --arg for input, but not a combination.")
    if input_path:
        try:
            return Path(input_path).read_text(encoding="utf-8"), input_path
        except OSError as exc:
            raise FileIOCliError(f"Could not read {input_path}: {exc}") from exc
    if args.input_text is not None:
        return args.input_text, None
    if args.stdin or not sys.stdin.isatty():
        try:
            return sys.stdin.read(), None
        except OSError as exc:
            raise FileIOCliError(f"Could not read stdin: {exc}") from exc
    raise InputParseError("Provide input with a file path, --file, --stdin, or --arg.")


def emit_result(value: Any, args: argparse.Namespace) -> int:
    """Apply defaults, output rendering, and exit-status handling."""
    value = apply_default(value, args.default)
    if args.exit_status and not value:
        return FALSEY_RESULT
    if args.quiet:
        return 0
    output_text = render_output(value, args)
    if output_text and not args.nul and not output_text.endswith("\0"):
        output_text = f"{output_text}\n"
    return write_output(output_text, args)


def write_output(output_text: str, args: argparse.Namespace) -> int:
    """Write output to stdout or a file."""
    output_path = getattr(args, "output_path", None)
    if output_path:
        try:
            Path(output_path).write_text(output_text, encoding="utf-8")
        except OSError as exc:
            raise FileIOCliError(f"Could not write {output_path}: {exc}") from exc
    else:
        sys.stdout.write(output_text)
    return 0


def type_name_for_value(value: Any) -> str:
    """Return a friendly type name."""
    if value is None:
        return "none"
    if value is Ellipsis:
        return "ellipsis"
    return type(value).__name__


def format_hbn_text(source_text: str) -> str:
    """Format HBN text using black if available."""
    if black is None:
        raise ExternalToolError("Formatting requires black. Install the fmt extra or make sure black is available.")
    try:
        return black.format_str(source_text, mode=black.FileMode())
    except black.InvalidInput as exc:
        raise InputParseError(f"Could not format input as HBN: {exc}") from exc
