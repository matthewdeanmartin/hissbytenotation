"""Shared install hints for optional hissbytenotation features."""

from __future__ import annotations

PACKAGE_NAME = "hissbytenotation"
ALL_EXTRA = "all"


def pip_install_command(extra: str) -> str:
    """Return a pip install command for a named extra."""
    return f'pip install "{PACKAGE_NAME}[{extra}]"'


def uv_sync_command(extra: str) -> str:
    """Return a uv sync command for a named extra."""
    return f"uv sync --extra {extra}"


def all_or_specific_extra_install_hint(extra: str) -> str:
    """Return a concise install hint covering the all extra and a specific extra."""
    return (
        f"Install everything with `{pip_install_command(ALL_EXTRA)}` "
        f"or just this feature with `{pip_install_command(extra)}`."
    )


def rust_install_hint() -> str:
    """Return install guidance for the optional Rust parser."""
    return (
        f"Install everything with `{pip_install_command(ALL_EXTRA)}`. "
        "For Rust acceleration specifically, reinstall `hissbytenotation` from a platform wheel when available, "
        "or build the optional extension locally with: `cd rust && maturin develop --release`."
    )
