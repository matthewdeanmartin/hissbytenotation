"""Helpers for phase 5 diff support."""

from __future__ import annotations

import difflib
import shutil
import subprocess
import tempfile
from pathlib import Path

from hissbytenotation.cli.codecs import render_value
from hissbytenotation.cli.errors import ExternalToolError

DIFF_EXIT_DIFFERENT = 1
DIFF_EXIT_ERROR = 2
DIFF_TOOLS = ("auto", "git", "builtin")
CANONICAL_DIFF_FORMATS = ("hbn", "json")


def canonicalize_value(
    value: object,
    *,
    output_format: str,
    pretty: bool,
    compact: bool,
    sort_keys: bool,
    indent: int | None,
    strict: bool,
) -> str:
    """Render a value into stable text for diffing."""
    rendered = render_value(
        value,
        output_format,
        pretty=pretty,
        compact=compact,
        sort_keys=sort_keys,
        indent=indent,
        strict=strict,
    )
    return rendered if rendered.endswith("\n") else f"{rendered}\n"


def diff_texts(
    left_text: str,
    right_text: str,
    *,
    left_label: str,
    right_label: str,
    tool: str,
    context: int,
    output_format: str,
) -> tuple[int, str]:
    """Diff two canonical texts using the selected tool."""
    if tool not in DIFF_TOOLS:
        raise ExternalToolError(f"Unknown diff tool: {tool}")
    if tool in {"auto", "git"}:
        git_path = shutil.which("git")
        if git_path:
            return _run_git_diff(
                git_path,
                left_text,
                right_text,
                left_label=left_label,
                right_label=right_label,
                context=context,
                output_format=output_format,
            )
        if tool == "git":
            raise ExternalToolError("Diff requires git on PATH. Install the diff extra or make sure git is available.")
    return _run_builtin_diff(
        left_text,
        right_text,
        left_label=left_label,
        right_label=right_label,
        context=context,
    )


def _run_git_diff(
    git_path: str,
    left_text: str,
    right_text: str,
    *,
    left_label: str,
    right_label: str,
    context: int,
    output_format: str,
) -> tuple[int, str]:
    """Run `git diff --no-index` against temp files."""
    suffix = ".json" if output_format == "json" else ".hbn"
    with tempfile.TemporaryDirectory(prefix="hbn-diff-") as temporary_dir_name:
        temporary_dir = Path(temporary_dir_name)
        left_path = temporary_dir / f"{_safe_label(left_label)}{suffix}"
        right_path = temporary_dir / f"{_safe_label(right_label)}{suffix}"
        left_path.write_text(left_text, encoding="utf-8")
        right_path.write_text(right_text, encoding="utf-8")
        completed = subprocess.run(
            [
                git_path,
                "--no-pager",
                "diff",
                "--no-index",
                "--no-color",
                f"--unified={context}",
                "--",
                str(left_path),
                str(right_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    if completed.returncode in {0, DIFF_EXIT_DIFFERENT}:
        return completed.returncode, completed.stdout
    stderr_text = completed.stderr.strip() or completed.stdout.strip() or "git diff failed."
    raise ExternalToolError(stderr_text)


def _run_builtin_diff(
    left_text: str,
    right_text: str,
    *,
    left_label: str,
    right_label: str,
    context: int,
) -> tuple[int, str]:
    """Render a unified diff without shelling out."""
    diff_lines = list(
        difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile=left_label,
            tofile=right_label,
            n=context,
            lineterm="",
        )
    )
    if not diff_lines:
        return 0, ""
    return DIFF_EXIT_DIFFERENT, "\n".join(diff_lines) + "\n"


def _safe_label(label: str) -> str:
    """Normalize a user-facing label into a temp-file-safe filename."""
    cleaned = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in label)
    return cleaned or "value"
