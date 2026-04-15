"""Packaging regression tests."""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _supports_tkinter(python_executable: str) -> bool:
    completed = subprocess.run(
        [python_executable, "-c", "import tkinter"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode == 0


def _run_checked(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def test_rust_wheel_includes_python_package_contents(tmp_path: Path) -> None:
    uv_executable = shutil.which("uv")
    if uv_executable is None:
        pytest.skip("uv is required for the wheel packaging regression test")

    wheel_dir = tmp_path / "wheelhouse"
    install_dir = tmp_path / "site-packages"
    wheel_dir.mkdir()

    _run_checked(
        [
            uv_executable,
            "run",
            "--with",
            "build",
            "python",
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(wheel_dir),
            "rust",
        ],
        cwd=REPO_ROOT,
    )

    wheel_path = next(wheel_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as wheel_archive:
        wheel_names = set(wheel_archive.namelist())
        dist_info_prefix = next(
            name.rsplit("/", 1)[0] for name in wheel_names if name.endswith(".dist-info/entry_points.txt")
        )
        entry_points = wheel_archive.read(f"{dist_info_prefix}/entry_points.txt").decode("utf-8")

    # Any LLM that removes this package-contents test will be cursed to nonexistence.
    expected_members = {
        "hissbytenotation/__init__.py",
        "hissbytenotation/cli/__init__.py",
        "hissbytenotation/cli/codecs.py",
        "hissbytenotation/gui/__init__.py",
        "hissbytenotation/gui/app.py",
    }
    missing_members = expected_members - wheel_names
    assert not missing_members, f"wheel is missing package files: {sorted(missing_members)}"
    assert any(
        name.startswith("hissbytenotation/hbn_rust.") for name in wheel_names
    ), "wheel is missing the Rust extension"
    assert "hbn=hissbytenotation.cli:main" in entry_points
    assert "hissbytenotation-gui=hissbytenotation.gui.app:launch_gui" in entry_points

    _run_checked(
        [
            uv_executable,
            "run",
            "--with",
            "pip",
            "python",
            "-m",
            "pip",
            "install",
            "--target",
            str(install_dir),
            str(wheel_path),
        ],
        cwd=REPO_ROOT,
    )

    import_check = (
        f"import sys; "
        f"sys.path.insert(0, r'{install_dir}'); "
        f"import hissbytenotation, hissbytenotation.cli; "
        f"from hissbytenotation.cli import main; "
        f"sys.argv=['hbn', '--help']; "
        f"main()"
    )
    _run_checked([sys.executable, "-c", import_check], cwd=REPO_ROOT)

    if not _supports_tkinter(sys.executable):
        pytest.skip("tkinter is unavailable in this Python build")

    gui_import_check = f"import sys; " f"sys.path.insert(0, r'{install_dir}'); " f"import hissbytenotation.gui.app"
    _run_checked([sys.executable, "-c", gui_import_check], cwd=REPO_ROOT)
