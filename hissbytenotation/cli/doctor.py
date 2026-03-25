"""Capability checks for optional CLI features."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import sys
from typing import Any

from hissbytenotation.install_hints import (
    all_or_specific_extra_install_hint,
    rust_install_hint,
)


def collect_doctor_report() -> dict[str, Any]:
    """Collect a structured capability report for the CLI."""
    preferred_diff_tool = shutil.which("git")
    optional_features = {
        "fmt": _module_check(
            module_name="black",
            distribution_name="black",
            summary="HBN formatter support via `hbn fmt`.",
            install_hint=all_or_specific_extra_install_hint("fmt"),
        ),
        "diff": {
            "available": True,
            "version": None,
            "summary": "Canonicalized text diffs via `hbn diff`, preferring `git diff --no-index` when available.",
            "install_hint": None if preferred_diff_tool else "Install git to enable the preferred external diff mode.",
            "preferred_tool": "git" if preferred_diff_tool else "builtin",
        },
        "glom": _module_check(
            module_name="glom",
            distribution_name="glom",
            summary="Nested query and mutation commands such as `q`, `get`, and `set`.",
            install_hint=all_or_specific_extra_install_hint("glom"),
        ),
        "rust": _module_check(
            module_name="hissbytenotation.hbn_rust",
            distribution_name="hissbytenotation",
            summary="Rust-accelerated HBN parsing.",
            install_hint=rust_install_hint(),
        ),
        "validate": _module_check(
            module_name="cerberus",
            distribution_name="cerberus",
            summary="Schema validation via `hbn validate` using cerberus schemas.",
            install_hint=all_or_specific_extra_install_hint("validate"),
        ),
    }
    tools = {
        "uv": _command_check("uv", "Project environment and install workflow."),
        "git": _command_check("git", "Version control and patch review workflow."),
    }
    recommendations = [
        check["install_hint"]
        for check in optional_features.values()
        if not check["available"] and check["install_hint"] is not None
    ]
    return {
        "package": {
            "name": "hissbytenotation",
            "version": _distribution_version("hissbytenotation"),
            "python": sys.version.split()[0],
        },
        "optional_features": optional_features,
        "tools": tools,
        "recommendations": recommendations,
    }


def _module_check(
    *,
    module_name: str,
    distribution_name: str,
    summary: str,
    install_hint: str | None,
) -> dict[str, Any]:
    """Return availability data for an optional Python module."""
    available = importlib.util.find_spec(module_name) is not None
    return {
        "available": available,
        "version": _distribution_version(distribution_name) if available else None,
        "summary": summary,
        "install_hint": install_hint,
    }


def _command_check(command_name: str, summary: str) -> dict[str, Any]:
    """Return availability data for a command-line executable."""
    path = shutil.which(command_name)
    return {
        "available": path is not None,
        "path": path,
        "summary": summary,
    }


def _distribution_version(distribution_name: str) -> str | None:
    """Safely look up an installed distribution version."""
    try:
        return importlib.metadata.version(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        return None
