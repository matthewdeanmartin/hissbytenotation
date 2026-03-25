"""CLI entrypoint for hissbytenotation."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from hissbytenotation.cli.codecs import (
    infer_format_from_path,
    normalize_format_name,
    parse_value,
)
from hissbytenotation.cli.diff_ops import CANONICAL_DIFF_FORMATS, DIFF_TOOLS, canonicalize_value, diff_texts
from hissbytenotation.cli.doctor import collect_doctor_report
from hissbytenotation.cli.errors import (
    FALSEY_RESULT,
    INTERNAL_ERROR,
    CliError,
    ExternalToolError,
    FileIOCliError,
    InputParseError,
    OperationTypeError,
)
from hissbytenotation.cli.glom_integration import (
    append_value,
    delete_value,
    insert_value,
    query_value,
    set_value,
)
from hissbytenotation.cli.merge_ops import (
    CONFLICT_POLICIES,
    MERGE_STRATEGIES,
    merge_values,
)
from hissbytenotation.cli.presenters import apply_default, render_output
from hissbytenotation.cli.repl import run_repl

black: Any = None
try:
    import black
except ImportError:  # pragma: no cover - exercised when the optional formatter is missing
    black = None

COMMAND_ALIASES = {
    "dump": ["show"],
    "fmt": ["format"],
    "q": ["query"],
    "del": ["delete", "remove"],
    "len": ["count"],
}

HELP_TOPICS = ("shell", "glom", "merge", "diff", "repl", "doctor", "aliases", "formats", "topics")
EXAMPLE_TOPICS = ("general", "bash", "glom", "merge", "diff", "repl", "doctor", "all")

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
    "glom": """Glom-powered queries:
  q PATH               query nested data using a simple path such as users.0.email
  q --glom SPEC        use an explicit glom spec written in HBN / Python literal syntax
  q --spec-file PATH   load a glom spec from a file
  get PATH             alias for simple path lookup
  set PATH --value V   deep-set a nested value
  del PATH             delete a nested value
  append PATH --value V
                       append to a nested list
  insert PATH --index N --value V
                       insert into a nested list
""",
    "merge": """Merge and file mutation helpers:
  merge LEFT RIGHT                     merge two inputs
  merge --strategy deep               recursively merge nested dicts
  merge --strategy append-lists       concatenate lists during recursive merge
  merge --strategy set-union-lists    union lists while preserving order
  merge --conflict error              fail on conflicting values
  merge --conflict left-wins          keep the left value on conflicts
  merge --conflict right-wins         keep the right value on conflicts
  --in-place                          write back to the input file
  --backup SUFFIX                     create a backup before writing
  --atomic                            write through a temp file then replace
  --check                             validate without printing or writing
""",
    "diff": """Diff helper:
  diff LEFT RIGHT                      canonicalize two inputs and diff them
  diff --to json                       diff canonical JSON instead of HBN
  diff --tool git                      require git diff --no-index
  diff --tool builtin                  force the builtin unified diff renderer
  diff --context 5                     adjust unified diff context lines
  Exit codes:
    0  inputs are equivalent after canonicalization
    1  diff found
""",
    "repl": """Interactive REPL:
  repl [file]
  repl --arg "{'users': []}"
  Inside the REPL:
    load VALUE
    read PATH [--from FMT]
    show | type | keys | values | items | len
    get PATH | q PATH | q --glom SPEC
    set PATH --value VALUE
    del PATH
    append PATH --value VALUE
    insert PATH --index N --value VALUE
    merge --value VALUE | merge --file PATH
    write PATH [--to FMT]
    doctor
    reset
    quit
""",
    "doctor": """Doctor checks:
  doctor                            show a structured capability report
  doctor --to json --pretty         render the report as JSON
  The report checks optional runtime features such as:
    - black / fmt support
    - diff helper support
    - glom integration
    - hbn_rust acceleration
    - uv and git on PATH
""",
    "aliases": """Command aliases:
  show      alias for dump
  format    alias for fmt
  query     alias for q
  delete    alias for del
  remove    alias for del
  count     alias for len
""",
    "formats": """Supported formats:
  hbn   native Hiss Byte Notation / Python literal syntax
  json  stdlib JSON input and output
  toml  stdlib TOML input only
  xml   basic XML mapping using @attrs and #text
  bmn   Bash Map Notation for flat dicts and scalar arrays
""",
    "topics": """Help topics:
  shell
  glom
  merge
  diff
  repl
  doctor
  aliases
  formats
  topics
""",
}

EXAMPLES = {
    "general": """Examples:
  hbn dump --arg "{'cat': 'snake'}"
  hbn convert --from json --to hbn --arg "{\\"cat\\": \\"snake\\"}"
  hbn type data.hbn
  hbn keys --lines data.hbn
  hbn fmt config.hbn
  hbn diff left.hbn right.hbn
  hbn get users.0.email data.hbn --raw
  hbn repl data.hbn
  hbn doctor --to json --pretty
""",
    "bash": """Bash examples:
  hbn values --lines data.hbn
  hbn dump --arg "['a', 'b']" --bash-array items
  hbn dump --arg "{'host': 'db', 'port': '5432'}" --bash-assoc cfg
  hbn len --arg "[]" --default 0 --raw
  db_url=$(hbn dump --arg "'postgres://db'" --shell-quote)
  first_email=$(hbn get users.0.email data.hbn --raw)
""",
    "glom": """Glom examples:
  hbn q users.0.email data.hbn --raw
  hbn q --glom "{'emails': ('users', ['email'])}" data.hbn
  hbn q --spec-file active_users.glomspec data.hbn
  hbn set users.0.role --value "'admin'" data.hbn
  hbn append users --value "{'email': 'new@example.com'}" data.hbn
""",
    "merge": """Merge examples:
  hbn merge left.hbn right.hbn
  hbn merge --strategy append-lists left.hbn right.hbn
  hbn merge --conflict right-wins --left-arg "{'a': 1}" --right-arg "{'a': 2}"
  hbn set config.port --value 5432 --in-place settings.hbn
  hbn append users --value "{'email': 'new@example.com'}" --backup .bak users.hbn
""",
    "diff": """Diff examples:
  hbn diff left.hbn right.hbn
  hbn diff --to json left.hbn right.hbn
  hbn diff --tool builtin --left-arg "{'a': 1}" --right-arg "{'a': 2}"
""",
    "repl": """REPL examples:
  hbn repl
  hbn repl session.hbn
  hbn repl --arg "{'users': [{'email': 'a@example.com'}]}"

  # inside the REPL
  load {'users': [{'email': 'a@example.com'}]}
  get users.0.email --raw
  set users.0.role --value "'admin'"
  merge --value "{'users': [{'email': 'b@example.com'}]}" --strategy append-lists
  write users.json --to json --pretty
""",
    "doctor": """Doctor examples:
  hbn doctor
  hbn doctor --to json --pretty
  hbn doctor --compact
""",
}

COMMAND_NAMES = {
    "dump",
    "show",
    "fmt",
    "format",
    "diff",
    "q",
    "query",
    "get",
    "set",
    "del",
    "delete",
    "remove",
    "append",
    "insert",
    "merge",
    "convert",
    "type",
    "keys",
    "values",
    "items",
    "len",
    "count",
    "repl",
    "doctor",
    "help",
    "examples",
    "completion",
    "version",
    "gui",
}


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
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
    glom_data_parent = build_data_parent_parser(include_positional_path=False)
    output_parent = build_output_parent_parser()
    glom_parent = build_glom_parent_parser()
    mutation_parent = build_mutation_parent_parser()
    merge_parent = build_merge_parent_parser()

    dump_parser = subparsers.add_parser(
        "dump", aliases=COMMAND_ALIASES["dump"], parents=[data_parent, output_parent], help="Render input as HBN."
    )
    dump_parser.set_defaults(handler=handle_dump, to_format="hbn")

    fmt_parser = subparsers.add_parser(
        "fmt", aliases=COMMAND_ALIASES["fmt"], parents=[data_parent], help="Format HBN input using black."
    )
    fmt_parser.add_argument("-o", "--output", dest="output_path", help="Write formatted output to a file.")
    fmt_parser.set_defaults(handler=handle_fmt)

    diff_parser = subparsers.add_parser(
        "diff",
        help="Canonicalize two inputs and show a unified diff.",
    )
    diff_parser.add_argument("left_source", nargs="?", help="Left input file path.")
    diff_parser.add_argument("right_source", nargs="?", help="Right input file path.")
    diff_parser.add_argument("--left-file", dest="left_file", help="Explicit left input file path.")
    diff_parser.add_argument("--right-file", dest="right_file", help="Explicit right input file path.")
    diff_parser.add_argument("--left-arg", dest="left_arg", help="Left input literal text.")
    diff_parser.add_argument("--right-arg", dest="right_arg", help="Right input literal text.")
    diff_parser.add_argument("--left-stdin", action="store_true", help="Read the left input from stdin.")
    diff_parser.add_argument("--left-from", dest="left_format", help="Format for the left input.")
    diff_parser.add_argument("--right-from", dest="right_format", help="Format for the right input.")
    diff_parser.add_argument("--to", dest="to_format", choices=CANONICAL_DIFF_FORMATS, default="hbn")
    diff_parser.add_argument("--tool", choices=DIFF_TOOLS, default="auto", help="Diff implementation to use.")
    diff_parser.add_argument("--context", type=int, default=3, help="Unified diff context lines.")
    diff_parser.add_argument("--compact", action="store_true", help="Emit compact canonical text before diffing.")
    diff_parser.add_argument("--pretty", action="store_true", help="Pretty-print canonical text before diffing.")
    diff_parser.add_argument("--indent", type=int, help="Indentation width for canonical rendering.")
    diff_parser.add_argument("--sort-keys", action="store_true", help="Sort mapping keys before diffing.")
    diff_parser.add_argument("--strict", action="store_true", help="Refuse lossy canonicalization conversions.")
    diff_parser.add_argument("--label-left", default="left", help="Label to use for the left side of the diff.")
    diff_parser.add_argument("--label-right", default="right", help="Label to use for the right side of the diff.")
    diff_parser.add_argument("--debug", action="store_true", help="Raise exceptions with tracebacks.")
    diff_parser.set_defaults(handler=handle_diff, pretty=True, sort_keys=True)

    convert_parser = subparsers.add_parser(
        "convert",
        parents=[data_parent, output_parent],
        help="Convert between HBN, JSON, TOML input, XML, and BMN.",
    )
    convert_parser.add_argument("--to", dest="to_format", required=True, help="Target output format.")
    convert_parser.set_defaults(handler=handle_convert)

    query_parser = subparsers.add_parser(
        "q",
        aliases=COMMAND_ALIASES["q"],
        parents=[glom_data_parent, output_parent, glom_parent],
        help="Query nested data with glom paths or specs.",
    )
    query_parser.add_argument("query_path", nargs="?", help="Simple query path such as users.0.email.")
    query_parser.add_argument("source_path", nargs="?", help="Optional input file path.")
    query_parser.set_defaults(handler=handle_query)

    get_parser = subparsers.add_parser(
        "get",
        parents=[glom_data_parent, output_parent],
        help="Read a nested value using a simple path.",
    )
    get_parser.add_argument("query_path", help="Simple query path such as users.0.email.")
    get_parser.add_argument("source_path", nargs="?", help="Optional input file path.")
    get_parser.set_defaults(handler=handle_get)

    set_parser = subparsers.add_parser(
        "set",
        parents=[glom_data_parent, output_parent, mutation_parent],
        help="Set a nested value using a simple path.",
    )
    set_parser.add_argument("query_path", help="Simple query path such as users.0.email.")
    set_parser.add_argument("--value", dest="value_text", required=True, help="Replacement value in HBN syntax.")
    set_parser.add_argument("source_path", nargs="?", help="Optional input file path.")
    set_parser.set_defaults(handler=handle_set)

    del_parser = subparsers.add_parser(
        "del",
        aliases=COMMAND_ALIASES["del"],
        parents=[glom_data_parent, output_parent, mutation_parent],
        help="Delete a nested value using a simple path.",
    )
    del_parser.add_argument("query_path", help="Simple query path such as users.0.email.")
    del_parser.add_argument("source_path", nargs="?", help="Optional input file path.")
    del_parser.set_defaults(handler=handle_del)

    append_parser = subparsers.add_parser(
        "append",
        parents=[glom_data_parent, output_parent, mutation_parent],
        help="Append a value to a nested list.",
    )
    append_parser.add_argument("query_path", help="Simple path to a list target.")
    append_parser.add_argument("--value", dest="value_text", required=True, help="Value to append in HBN syntax.")
    append_parser.add_argument("source_path", nargs="?", help="Optional input file path.")
    append_parser.set_defaults(handler=handle_append)

    insert_parser = subparsers.add_parser(
        "insert",
        parents=[glom_data_parent, output_parent, mutation_parent],
        help="Insert a value into a nested list.",
    )
    insert_parser.add_argument("query_path", help="Simple path to a list target.")
    insert_parser.add_argument("--index", type=int, required=True, help="Zero-based insert position.")
    insert_parser.add_argument("--value", dest="value_text", required=True, help="Value to insert in HBN syntax.")
    insert_parser.add_argument("source_path", nargs="?", help="Optional input file path.")
    insert_parser.set_defaults(handler=handle_insert)

    merge_parser = subparsers.add_parser(
        "merge",
        parents=[output_parent, mutation_parent, merge_parent],
        help="Merge two inputs using a selected strategy.",
    )
    merge_parser.add_argument("left_source", nargs="?", help="Left input file path.")
    merge_parser.add_argument("right_source", nargs="?", help="Right input file path.")
    merge_parser.add_argument("--left-file", dest="left_file", help="Explicit left input file path.")
    merge_parser.add_argument("--right-file", dest="right_file", help="Explicit right input file path.")
    merge_parser.add_argument("--left-arg", dest="left_arg", help="Left input literal text.")
    merge_parser.add_argument("--right-arg", dest="right_arg", help="Right input literal text.")
    merge_parser.add_argument("--left-stdin", action="store_true", help="Read the left input from stdin.")
    merge_parser.add_argument("--left-from", dest="left_format", help="Format for the left input.")
    merge_parser.add_argument("--right-from", dest="right_format", help="Format for the right input.")
    merge_parser.add_argument("--to", dest="to_format", help="Target output format.")
    merge_parser.set_defaults(handler=handle_merge)

    for command_name, handler, help_text in (
        ("type", handle_type, "Show the root value type."),
        ("keys", handle_keys, "Show dict keys."),
        ("values", handle_values, "Show dict values."),
        ("items", handle_items, "Show dict items."),
        ("len", handle_len, "Show collection length."),
    ):
        aliases = COMMAND_ALIASES.get(command_name, [])
        command_parser = subparsers.add_parser(
            command_name, aliases=aliases, parents=[data_parent, output_parent], help=help_text
        )
        command_parser.set_defaults(handler=handler)

    repl_parser = subparsers.add_parser("repl", help="Start an interactive REPL.")
    repl_source_group = repl_parser.add_mutually_exclusive_group()
    repl_source_group.add_argument("--file", dest="input_path", help="Load an initial value from a file.")
    repl_source_group.add_argument("--arg", dest="input_text", help="Load an initial value from a literal string.")
    repl_parser.add_argument("source_path", nargs="?", help="Optional initial input file path.")
    repl_parser.add_argument("--from", dest="from_format", help="Format for the initial input.")
    repl_parser.add_argument("--prompt", default="hbn> ", help="Prompt string to use in interactive mode.")
    repl_parser.add_argument("--debug", action="store_true", help="Raise exceptions with tracebacks.")
    repl_parser.set_defaults(handler=handle_repl)

    doctor_parser = subparsers.add_parser("doctor", parents=[output_parent], help="Inspect optional capabilities.")
    doctor_parser.add_argument("--to", dest="to_format", help="Target output format.")
    doctor_parser.set_defaults(handler=handle_doctor, pretty=True)

    help_parser = subparsers.add_parser("help", help="Show help for a topic.")
    help_parser.add_argument("topic", nargs="?", help="Topic such as shell or formats.")
    help_parser.set_defaults(handler=handle_help)

    examples_parser = subparsers.add_parser("examples", help="Show usage examples.")
    examples_parser.add_argument("topic", nargs="?", default="general", help="Example topic such as bash.")
    examples_parser.set_defaults(handler=handle_examples)

    completion_parser = subparsers.add_parser("completion", help="Emit shell completion scripts.")
    completion_parser.add_argument("shell", choices=["bash", "zsh", "fish", "powershell"], help="Shell to target.")
    completion_parser.set_defaults(handler=handle_completion)

    version_parser = subparsers.add_parser("version", help="Show the installed version.")
    version_parser.set_defaults(handler=handle_version)

    gui_parser = subparsers.add_parser("gui", help="Launch the graphical interface.")
    gui_parser.set_defaults(handler=handle_gui)

    parser.add_argument("--gui", action="store_true", help="Launch the graphical interface.")

    return parser


def build_data_parent_parser(*, include_positional_path: bool = True) -> argparse.ArgumentParser:
    """Build common input arguments."""
    parser = argparse.ArgumentParser(add_help=False)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--file", dest="input_path", help="Read input from a file.")
    source_group.add_argument("--stdin", action="store_true", help="Read input from stdin.")
    source_group.add_argument("--arg", dest="input_text", help="Read input from a literal argument string.")
    if include_positional_path:
        parser.add_argument("source_path", nargs="?", help="Optional input file path.")
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


def build_glom_parent_parser() -> argparse.ArgumentParser:
    """Build shared glom query arguments."""
    parser = argparse.ArgumentParser(add_help=False)
    spec_group = parser.add_mutually_exclusive_group()
    spec_group.add_argument("--glom", dest="glom_spec", help="Glom spec written in HBN / Python literal syntax.")
    spec_group.add_argument("--spec-file", dest="spec_file_path", help="Read the glom spec from a file.")
    return parser


def build_mutation_parent_parser() -> argparse.ArgumentParser:
    """Build shared mutation file arguments."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--in-place", action="store_true", help="Write the result back to the input file.")
    parser.add_argument("--backup", metavar="SUFFIX", help="Create a backup copy before writing in place.")
    parser.add_argument("--atomic", action="store_true", help="Write through a temporary file and replace the input.")
    parser.add_argument("--check", action="store_true", help="Validate the command without printing or writing.")
    return parser


def build_merge_parent_parser() -> argparse.ArgumentParser:
    """Build shared merge arguments."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--strategy", choices=MERGE_STRATEGIES, default="deep", help="Merge strategy to apply.")
    parser.add_argument(
        "--conflict",
        choices=CONFLICT_POLICIES,
        default="error",
        help="Conflict policy for non-mergeable values.",
    )
    parser.add_argument("--strict", action="store_true", help="Refuse mismatched types unless using replace.")
    parser.add_argument("--default", help="Default value to use when the result is empty.")
    parser.add_argument("--exit-status", action="store_true", help="Return exit code 1 for falsey results.")
    parser.add_argument("--quiet", action="store_true", help="Suppress normal command output.")
    parser.add_argument("--verbose", action="store_true", help="Reserved for future verbose output.")
    parser.add_argument("--debug", action="store_true", help="Raise exceptions with tracebacks.")
    parser.add_argument("--color", action="store_true", help="Reserved for future colored output.")
    parser.add_argument("--no-color", action="store_true", help="Reserved for future plain output.")
    return parser


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Dispatch to the selected command handler."""
    if getattr(args, "gui", False) or args.command == "gui":
        from hissbytenotation.gui.app import launch_gui

        launch_gui()
        return 0
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


def handle_diff(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Canonicalize two inputs and diff them."""
    left_value, left_path = load_merge_input(args, side="left")
    right_value, right_path = load_merge_input(args, side="right")
    output_format = normalize_format_name(args.to_format, output=True)
    left_text = canonicalize_value(
        left_value,
        output_format=output_format,
        pretty=args.pretty,
        compact=args.compact,
        sort_keys=args.sort_keys,
        indent=args.indent,
        strict=args.strict,
    )
    right_text = canonicalize_value(
        right_value,
        output_format=output_format,
        pretty=args.pretty,
        compact=args.compact,
        sort_keys=args.sort_keys,
        indent=args.indent,
        strict=args.strict,
    )
    left_label = left_path or args.label_left
    right_label = right_path or args.label_right
    exit_code, diff_output = diff_texts(
        left_text,
        right_text,
        left_label=left_label,
        right_label=right_label,
        tool=args.tool,
        context=args.context,
        output_format=output_format,
    )
    if diff_output:
        sys.stdout.write(diff_output if diff_output.endswith("\n") else f"{diff_output}\n")
    return exit_code


def handle_query(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Run a glom-backed query."""
    value = load_input_value(args)
    result = query_value(
        value,
        path_text=args.query_path,
        spec_text=args.glom_spec,
        spec_file_path=args.spec_file_path,
        default_on_missing=args.default is not None,
    )
    return emit_result(result, args)


def handle_get(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Run a simple path query."""
    value = load_input_value(args)
    result = query_value(value, path_text=args.query_path, default_on_missing=args.default is not None)
    return emit_result(result, args)


def handle_set(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Set a nested value."""
    value = load_input_value(args)
    new_value = parse_cli_value(args.value_text)
    return finish_mutation(set_value(value, args.query_path, new_value), args)


def handle_del(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Delete a nested value."""
    value = load_input_value(args)
    return finish_mutation(delete_value(value, args.query_path), args)


def handle_append(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Append to a nested list."""
    value = load_input_value(args)
    new_value = parse_cli_value(args.value_text)
    return finish_mutation(append_value(value, args.query_path, new_value), args)


def handle_insert(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Insert into a nested list."""
    value = load_input_value(args)
    new_value = parse_cli_value(args.value_text)
    return finish_mutation(insert_value(value, args.query_path, args.index, new_value), args)


def handle_merge(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Merge two inputs using the selected strategy."""
    left_value, left_path = load_merge_input(args, side="left")
    right_value, _right_path = load_merge_input(args, side="right")
    result = merge_values(
        left_value,
        right_value,
        strategy=args.strategy,
        conflict=args.conflict,
        strict=args.strict,
    )
    return finish_mutation(result, args, input_path=left_path)


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


def handle_repl(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Start the interactive REPL."""
    initial_value, initial_path = load_repl_initial_value(args)
    return run_repl(initial_value=initial_value, initial_path=initial_path, prompt=args.prompt)


def handle_doctor(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Show a structured capability report."""
    if getattr(args, "to_format", None):
        args.to_format = normalize_format_name(args.to_format, output=True)
    return emit_result(collect_doctor_report(), args)


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
    if topic == "all":
        for example_topic in EXAMPLE_TOPICS:
            if example_topic == "all":
                continue
            print(EXAMPLES[example_topic], end="" if example_topic == "doctor" else "\n")
        return 0
    if topic not in EXAMPLES:
        raise InputParseError(f"Unknown examples topic: {args.topic}")
    print(EXAMPLES[topic], end="")
    return 0


def handle_completion(args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Emit a minimal shell completion script."""
    commands = sorted(COMMAND_NAMES)
    help_topics = list(HELP_TOPICS)
    example_topics = list(EXAMPLE_TOPICS)
    shells = ["bash", "zsh", "fish", "powershell"]
    scripts = {
        "bash": build_bash_completion(commands, help_topics, example_topics, shells),
        "zsh": build_zsh_completion(commands, help_topics, example_topics, shells),
        "fish": build_fish_completion(commands, help_topics, example_topics, shells),
        "powershell": build_powershell_completion(commands, help_topics, example_topics, shells),
    }
    print(scripts[args.shell], end="")
    return 0


def build_bash_completion(
    commands: list[str], help_topics: list[str], example_topics: list[str], shells: list[str]
) -> str:
    """Build a Bash completion script."""
    commands_text = " ".join(commands)
    help_topics_text = " ".join(help_topics)
    example_topics_text = " ".join(example_topics)
    shells_text = " ".join(shells)
    return f"""_hbn_complete() {{
    local current commands help_topics example_topics shells
    current="${{COMP_WORDS[COMP_CWORD]}}"
    commands="{commands_text}"
    help_topics="{help_topics_text}"
    example_topics="{example_topics_text}"
    shells="{shells_text}"
    if [[ ${{COMP_CWORD}} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$current") )
        return 0
    fi
    case "${{COMP_WORDS[1]}}" in
        help)
            COMPREPLY=( $(compgen -W "$help_topics $commands" -- "$current") )
            ;;
        examples)
            COMPREPLY=( $(compgen -W "$example_topics" -- "$current") )
            ;;
        completion)
            COMPREPLY=( $(compgen -W "$shells" -- "$current") )
            ;;
        *)
            COMPREPLY=( $(compgen -W "$commands" -- "$current") )
            ;;
    esac
}}
complete -F _hbn_complete hbn hissbytenotation
"""


def build_zsh_completion(
    commands: list[str], help_topics: list[str], example_topics: list[str], shells: list[str]
) -> str:
    """Build a Zsh completion script."""
    command_items = " ".join(f'"{command}"' for command in commands)
    help_topic_items = " ".join(f'"{topic}"' for topic in help_topics)
    example_topic_items = " ".join(f'"{topic}"' for topic in example_topics)
    shell_items = " ".join(f'"{shell}"' for shell in shells)
    return f"""#compdef hbn hissbytenotation
local -a commands
commands=({command_items})
local -a help_topics
help_topics=({help_topic_items})
local -a example_topics
example_topics=({example_topic_items})
local -a shells
shells=({shell_items})

if (( CURRENT == 2 )); then
  _describe 'command' commands
  return
fi

case "${{words[2]}}" in
  help)
    _describe 'help topic' help_topics
    ;;
  examples)
    _describe 'example topic' example_topics
    ;;
  completion)
    _describe 'shell' shells
    ;;
  *)
    _describe 'command' commands
    ;;
esac
"""


def build_fish_completion(
    commands: list[str], help_topics: list[str], example_topics: list[str], shells: list[str]
) -> str:
    """Build a Fish completion script."""
    commands_text = " ".join(commands)
    help_topics_text = " ".join(help_topics)
    example_topics_text = " ".join(example_topics)
    shells_text = " ".join(shells)
    return f"""set -l hbn_commands {commands_text}
set -l hbn_help_topics {help_topics_text}
set -l hbn_example_topics {example_topics_text}
set -l hbn_shells {shells_text}

complete -c hbn -n '__fish_use_subcommand' -f -a "$hbn_commands"
complete -c hissbytenotation -n '__fish_use_subcommand' -f -a "$hbn_commands"
complete -c hbn -n '__fish_seen_subcommand_from help' -f -a "$hbn_help_topics $hbn_commands"
complete -c hissbytenotation -n '__fish_seen_subcommand_from help' -f -a "$hbn_help_topics $hbn_commands"
complete -c hbn -n '__fish_seen_subcommand_from examples' -f -a "$hbn_example_topics"
complete -c hissbytenotation -n '__fish_seen_subcommand_from examples' -f -a "$hbn_example_topics"
complete -c hbn -n '__fish_seen_subcommand_from completion' -f -a "$hbn_shells"
complete -c hissbytenotation -n '__fish_seen_subcommand_from completion' -f -a "$hbn_shells"
"""


def build_powershell_completion(
    commands: list[str], help_topics: list[str], example_topics: list[str], shells: list[str]
) -> str:
    """Build a PowerShell completion script."""
    command_items = ", ".join(f"'{command}'" for command in commands)
    help_topic_items = ", ".join(f"'{topic}'" for topic in help_topics)
    example_topic_items = ", ".join(f"'{topic}'" for topic in example_topics)
    shell_items = ", ".join(f"'{shell}'" for shell in shells)
    return f"""Register-ArgumentCompleter -CommandName hbn, hissbytenotation -ScriptBlock {{
    param($wordToComplete, $commandAst, $cursorPosition)

    $commands = @({command_items})
    $helpTopics = @({help_topic_items})
    $exampleTopics = @({example_topic_items})
    $shells = @({shell_items})
    $elements = $commandAst.CommandElements | ForEach-Object {{ $_.Extent.Text }}

    if ($elements.Count -le 2) {{
        $commands | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }}
        return
    }}

    $subcommand = $elements[1]
    $choices = switch ($subcommand) {{
        'help' {{ $helpTopics + $commands }}
        'examples' {{ $exampleTopics }}
        'completion' {{ $shells }}
        default {{ $commands }}
    }}

    $choices | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }}
}}
"""


def handle_gui(_args: argparse.Namespace, _parser: argparse.ArgumentParser) -> int:
    """Launch the graphical interface."""
    from hissbytenotation.gui.app import launch_gui

    launch_gui()
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


def parse_cli_value(value_text: str) -> Any:
    """Parse a CLI value argument as HBN."""
    return parse_value(value_text, "hbn")


def load_merge_input(args: argparse.Namespace, *, side: str) -> tuple[Any, str | None]:
    """Load one side of a merge operation."""
    positional_name = f"{side}_source"
    file_name = f"{side}_file"
    arg_name = f"{side}_arg"
    format_name = f"{side}_format"
    stdin_name = f"{side}_stdin"

    positional_path = getattr(args, positional_name, None)
    explicit_path = getattr(args, file_name, None)
    literal_text = getattr(args, arg_name, None)
    from_format = getattr(args, format_name, None)
    use_stdin = bool(getattr(args, stdin_name, False))

    provided_count = (
        int(positional_path is not None)
        + int(explicit_path is not None)
        + int(literal_text is not None)
        + int(use_stdin)
    )
    if provided_count != 1:
        allowed_sources = [f"--{side}-file", f"--{side}-arg", "a positional file"]
        if side == "left":
            allowed_sources.append("--left-stdin")
        raise InputParseError(f"Provide exactly one {side} input using {', '.join(allowed_sources)}.")
    if positional_path and explicit_path and positional_path != explicit_path:
        raise InputParseError(f"Use only one {side} file path source.")
    input_path = explicit_path or positional_path
    if input_path:
        try:
            text = Path(input_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise FileIOCliError(f"Could not read {input_path}: {exc}") from exc
        format_hint = from_format or infer_format_from_path(input_path, output=False)
        return parse_value(text, format_hint, strict=args.strict), input_path
    if literal_text is not None:
        format_hint = from_format or "hbn"
        return parse_value(literal_text, format_hint, strict=args.strict), None
    try:
        text = sys.stdin.read()
    except OSError as exc:
        raise FileIOCliError(f"Could not read stdin: {exc}") from exc
    format_hint = from_format or "hbn"
    return parse_value(text, format_hint, strict=args.strict), None


def load_repl_initial_value(args: argparse.Namespace) -> tuple[Any | None, str | None]:
    """Load an optional initial REPL value without consuming command stdin implicitly."""
    source_path = getattr(args, "source_path", None)
    input_path = getattr(args, "input_path", None) or source_path
    input_text = getattr(args, "input_text", None)
    if getattr(args, "input_path", None) and source_path and args.input_path != source_path:
        raise InputParseError("Use only one initial REPL file path source.")
    if input_path and input_text is not None:
        raise InputParseError("Use either a file path or --arg for REPL startup input, but not both.")
    if input_path is None and input_text is None:
        return None, None
    from_format = getattr(args, "from_format", None)
    if input_path is not None:
        try:
            text = Path(input_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise FileIOCliError(f"Could not read {input_path}: {exc}") from exc
        return parse_value(text, from_format or infer_format_from_path(input_path, output=False)), input_path
    assert input_text is not None
    return parse_value(input_text, from_format or "hbn"), None


def load_input_text(args: argparse.Namespace) -> tuple[str, str | None]:
    """Load raw input text from one of the supported sources."""
    source_path = getattr(args, "source_path", None)
    input_path = args.input_path or source_path
    if args.input_path and source_path and args.input_path != source_path:
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


def finish_mutation(value: Any, args: argparse.Namespace, *, input_path: str | None = None) -> int:
    """Handle check/in-place behavior for mutation-style commands."""
    validate_mutation_options(args, input_path=input_path)
    if getattr(args, "check", False):
        return 0
    if mutation_requested(args):
        return write_in_place_result(value, args, input_path=input_path)
    return emit_result(value, args)


def mutation_requested(args: argparse.Namespace) -> bool:
    """Return True when mutation file options are active."""
    return bool(getattr(args, "in_place", False) or getattr(args, "backup", None) or getattr(args, "atomic", False))


def validate_mutation_options(args: argparse.Namespace, *, input_path: str | None = None) -> None:
    """Validate shared mutation file options."""
    if getattr(args, "check", False) and getattr(args, "output_path", None):
        raise InputParseError("--check cannot be combined with --output.")
    if mutation_requested(args) and any(
        (
            getattr(args, "raw", False),
            getattr(args, "lines", False),
            getattr(args, "nul", False),
            getattr(args, "shell_quote", False),
            getattr(args, "shell_assign", None),
            getattr(args, "shell_export", None),
            getattr(args, "bash_array", None),
            getattr(args, "bash_assoc", None),
        )
    ):
        raise InputParseError("In-place mutations require structured output and cannot use shell presentation flags.")
    if not mutation_requested(args):
        return
    if getattr(args, "output_path", None):
        raise InputParseError("--in-place, --backup, and --atomic cannot be combined with --output.")
    if input_path is None:
        input_path = resolve_mutation_input_path(args)
    if input_path is None:
        raise InputParseError(
            "--in-place, --backup, and --atomic require a file-backed input. Use a file path instead of --arg or --stdin."
        )


def resolve_mutation_input_path(args: argparse.Namespace) -> str | None:
    """Resolve the file path that an in-place mutation should write back to."""
    return getattr(args, "input_path", None) or getattr(args, "source_path", None)


def write_in_place_result(value: Any, args: argparse.Namespace, *, input_path: str | None = None) -> int:
    """Write a mutation result back to its source file."""
    target_path = input_path or resolve_mutation_input_path(args)
    if target_path is None:
        raise InputParseError("No input file path is available for in-place writing.")
    target_format = getattr(args, "to_format", None)
    if target_format is None:
        target_format = infer_format_from_path(target_path, output=True)
    else:
        target_format = normalize_format_name(target_format, output=True)
    args.to_format = target_format
    output_text = render_output(value, args)
    if output_text and not args.nul and not output_text.endswith("\0"):
        output_text = f"{output_text}\n"
    target = Path(target_path)
    if getattr(args, "backup", None):
        backup_path = Path(f"{target_path}{args.backup}")
        try:
            shutil.copy2(target, backup_path)
        except OSError as exc:
            raise FileIOCliError(f"Could not create backup {backup_path}: {exc}") from exc
    if getattr(args, "atomic", False):
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(target.parent),
                prefix=f"{target.stem}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_file.write(output_text)
                temporary_path = temporary_file.name
            os.replace(temporary_path, target)
        except OSError as exc:
            if temporary_path is not None and Path(temporary_path).exists():
                Path(temporary_path).unlink(missing_ok=True)
            raise FileIOCliError(f"Atomic write failed for {target_path}: {exc}") from exc
        return 0
    try:
        target.write_text(output_text, encoding="utf-8")
    except OSError as exc:
        raise FileIOCliError(f"Could not write {target_path}: {exc}") from exc
    return 0


def emit_result(value: Any, args: argparse.Namespace) -> int:
    """Apply defaults, output rendering, and exit-status handling."""
    value = apply_default(value, getattr(args, "default", None))
    if getattr(args, "exit_status", False) and not value:
        return FALSEY_RESULT
    if getattr(args, "quiet", False):
        return 0
    output_text = render_output(value, args)
    if output_text and not getattr(args, "nul", False) and not output_text.endswith("\0"):
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
    black_path = shutil.which("black")
    if black_path:
        return format_hbn_text_with_black_command(source_text, black_path)
    if black is None:
        raise ExternalToolError("Formatting requires black. Install the fmt extra or make sure black is available.")
    try:
        return black.format_str(source_text, mode=black.FileMode())
    except black.InvalidInput as exc:
        raise InputParseError(f"Could not format input as HBN: {exc}") from exc


def format_hbn_text_with_black_command(source_text: str, black_path: str) -> str:
    """Format HBN text by shelling out to the black executable."""
    with tempfile.TemporaryDirectory(prefix="hbn-fmt-") as temporary_dir_name:
        temporary_path = Path(temporary_dir_name) / "input.py"
        temporary_path.write_text(source_text, encoding="utf-8")
        completed = subprocess.run(
            [black_path, "--quiet", str(temporary_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr_text = completed.stderr.strip() or completed.stdout.strip() or "black failed."
            raise InputParseError(f"Could not format input as HBN: {stderr_text}")
        return temporary_path.read_text(encoding="utf-8")
