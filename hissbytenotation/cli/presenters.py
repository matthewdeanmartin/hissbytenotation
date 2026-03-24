"""Output presentation helpers for shell-facing commands."""

from __future__ import annotations

import shlex
from typing import Any

from hissbytenotation import loads as hbn_loads

from .codecs import dump_bmn, render_value, scalar_to_text
from .errors import OperationTypeError


def apply_default(value: Any, default_text: str | None) -> Any:
    """Replace empty values with a parsed default when requested."""
    if default_text is None:
        return value
    if value is None:
        return _parse_default(default_text)
    if isinstance(value, (str, bytes, list, tuple, dict, set)) and len(value) == 0:
        return _parse_default(default_text)
    return value


def _parse_default(default_text: str) -> Any:
    try:
        return hbn_loads(default_text)
    except (SyntaxError, ValueError):
        return default_text


def render_output(value: Any, args: Any) -> str:
    """Render a command result according to presentation flags."""
    if getattr(args, "bash_array", None):
        return render_bash_array(value, args.bash_array)
    if getattr(args, "bash_assoc", None):
        return render_bash_assoc(value, args.bash_assoc)
    if getattr(args, "shell_assign", None):
        return render_shell_assignment(value, args.shell_assign, export=False)
    if getattr(args, "shell_export", None):
        return render_shell_assignment(value, args.shell_export, export=True)
    if getattr(args, "shell_quote", False):
        return shlex.quote(scalar_to_text(value))
    if getattr(args, "nul", False):
        return render_sequence(value, separator="\0", args=args)
    if getattr(args, "lines", False):
        return render_sequence(value, separator="\n", args=args)
    if getattr(args, "raw", False):
        if isinstance(value, (list, tuple, dict, set)):
            raise OperationTypeError("--raw requires a scalar result.")
        return scalar_to_text(value)
    output_format = getattr(args, "to_format", None) or getattr(args, "output_format", None) or "hbn"
    return render_value(
        value,
        output_format,
        pretty=getattr(args, "pretty", False),
        compact=getattr(args, "compact", False),
        sort_keys=getattr(args, "sort_keys", False),
        indent=getattr(args, "indent", None),
        strict=getattr(args, "strict", False),
    )


def render_sequence(value: Any, *, separator: str, args: Any) -> str:
    """Render a sequence as line- or NUL-delimited output."""
    if not isinstance(value, (list, tuple, set)):
        raise OperationTypeError("--lines and --nul require a list, tuple, or set result.")
    rendered_items = [render_sequence_item(item, args) for item in value]
    return separator.join(rendered_items)


def render_sequence_item(value: Any, args: Any) -> str:
    """Render an item inside a delimited sequence."""
    if isinstance(value, (str, bytes, int, float, bool)) or value is None:
        return scalar_to_text(value)
    output_format = getattr(args, "to_format", None) or "hbn"
    return render_value(
        value,
        output_format,
        pretty=False,
        compact=True,
        sort_keys=getattr(args, "sort_keys", False),
        indent=getattr(args, "indent", None),
        strict=getattr(args, "strict", False),
    )


def render_shell_assignment(value: Any, variable_name: str, *, export: bool) -> str:
    """Render a shell-safe assignment."""
    prefix = "export " if export else ""
    return f"{prefix}{variable_name}={shlex.quote(scalar_to_text(value))}"


def render_bash_array(value: Any, variable_name: str) -> str:
    """Render a Bash indexed array assignment."""
    if not isinstance(value, (list, tuple)):
        raise OperationTypeError("--bash-array requires a list or tuple result.")
    return dump_bmn(value, name=variable_name)


def render_bash_assoc(value: Any, variable_name: str) -> str:
    """Render a Bash associative array assignment."""
    if not isinstance(value, dict):
        raise OperationTypeError("--bash-assoc requires a dict result.")
    return dump_bmn(value, name=variable_name)
