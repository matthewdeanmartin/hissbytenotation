from hissbytenotation.cli import (
    build_parser,
    dispatch,
    handle_completion,
    handle_examples,
    handle_help,
    handle_query,
    handle_set,
    main,
)
from hissbytenotation.cli.errors import PARSE_FAILURE


def test_examples_defaults_to_general_topic():
    args = build_parser().parse_args(["examples"])

    assert args.topic == "general"
    assert args.handler is handle_examples


def test_help_command_topic_uses_help_handler():
    args = build_parser().parse_args(["help", "dump"])

    assert args.topic == "dump"
    assert args.handler is handle_help


def test_query_alias_wires_glom_namespace():
    args = build_parser().parse_args(["query", "--glom", "('users', ['email'])", "users.0.email", "data.hbn"])

    assert args.command == "query"
    assert args.handler is handle_query
    assert args.glom_spec == "('users', ['email'])"
    assert args.query_path == "users.0.email"
    assert args.source_path == "data.hbn"


def test_set_parser_collects_mutation_arguments():
    args = build_parser().parse_args(
        ["set", "config.port", "--value", "6432", "--in-place", "--backup", ".bak", "settings.hbn"]
    )

    assert args.command == "set"
    assert args.handler is handle_set
    assert args.query_path == "config.port"
    assert args.value_text == "6432"
    assert args.in_place is True
    assert args.backup == ".bak"
    assert args.source_path == "settings.hbn"


def test_completion_parser_sets_shell_choice():
    args = build_parser().parse_args(["completion", "fish"])

    assert args.shell == "fish"
    assert args.handler is handle_completion


def test_dispatch_without_command_prints_top_level_help(capsys):
    parser = build_parser()
    args = parser.parse_args([])

    exit_code = dispatch(args, parser)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Bash-first tools for Hiss Byte Notation." in captured.out
    assert "completion" in captured.out
    assert captured.err == ""


def test_main_help_for_command_delegates_to_subparser(capsys):
    exit_code = main(["help", "dump"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "usage: hbn dump" in captured.out
    assert "--arg INPUT_TEXT" in captured.out
    assert captured.err == ""


def test_main_returns_parse_failure_for_invalid_completion_shell(capsys):
    exit_code = main(["completion", "cmd"])
    captured = capsys.readouterr()

    assert exit_code == PARSE_FAILURE
    assert captured.out == ""
    assert "invalid choice" in captured.err


def test_main_returns_parse_failure_when_validate_schema_source_is_missing(capsys):
    exit_code = main(["validate", "--arg", "{}"])
    captured = capsys.readouterr()

    assert exit_code == PARSE_FAILURE
    assert captured.out == ""
    assert "one of the arguments --schema --schema-file is required" in captured.err
