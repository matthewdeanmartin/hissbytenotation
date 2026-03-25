#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HBN=(uv run hbn)
PYTHON=(uv run python)
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

cat >"$work_dir/left.hbn" <<'EOF'
{'config': {'host': 'db', 'port': 5432}}
EOF

cat >"$work_dir/right.hbn" <<'EOF'
{'config': {'port': 6432, 'timeout': 30}}
EOF

cp "$work_dir/left.hbn" "$work_dir/original-left.hbn"

"${HBN[@]}" merge --conflict right-wins --in-place "$work_dir/left.hbn" "$work_dir/right.hbn"

"${PYTHON[@]}" - <<'PY' "$work_dir/left.hbn"
from pathlib import Path
import sys

from hissbytenotation import loads

value = loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert value == {"config": {"host": "db", "port": 6432, "timeout": 30}}
PY

set +e
diff_output="$("${HBN[@]}" diff --tool builtin --to json --compact "$work_dir/original-left.hbn" "$work_dir/left.hbn" | tr -d '\r')"
diff_status=$?
set -e
[[ "$diff_status" -eq 1 ]]
[[ "$diff_output" == *"--- "*original-left.hbn* ]]
[[ "$diff_output" == *"+++ "*left.hbn* ]]
[[ "$diff_output" == *'"timeout":30'* ]]

echo "file mutation and diff examples passed"
