#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HBN=(uv run hbn)
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

cat >"$work_dir/data.hbn" <<'EOF'
{
    'users': [
        {'email': 'a@example.com'},
        {'email': 'b@example.com'}
    ],
    'host': 'db',
    'port': '5432'
}
EOF

first_email="$("${HBN[@]}" get users.0.email --file "$work_dir/data.hbn" --raw | tr -d '\r')"
[[ "$first_email" == "a@example.com" ]]

email_lines="$("${HBN[@]}" q --glom "('users', ['email'])" --file "$work_dir/data.hbn" --lines | tr -d '\r')"
[[ "$email_lines" == $'a@example.com\nb@example.com' ]]

array_assignment="$("${HBN[@]}" dump --arg "['alpha', 'beta']" --bash-array items | tr -d '\r')"
[[ "$array_assignment" == "items=(alpha beta)" ]]

assoc_assignment="$("${HBN[@]}" dump --arg "{'host': 'db', 'port': '5432'}" --bash-assoc cfg | tr -d '\r')"
[[ "$assoc_assignment" == *"declare -A cfg="* ]]
[[ "$assoc_assignment" == *"[host]=db"* ]]
[[ "$assoc_assignment" == *"[port]=5432"* ]]

quoted_text="$("${HBN[@]}" dump --arg "'hello world'" --shell-quote | tr -d '\r')"
[[ "$quoted_text" == "'hello world'" ]]

echo "shell output and query examples passed"
