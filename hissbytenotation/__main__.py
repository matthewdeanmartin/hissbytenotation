"""Support `python -m hissbytenotation`."""

from __future__ import annotations

import sys

from hissbytenotation.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
