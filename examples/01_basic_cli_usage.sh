#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HBN=(uv run hbn)

dumped="$("${HBN[@]}" dump --arg "{'cat': 'snake'}" | tr -d '\r')"
[[ "$dumped" == "{'cat': 'snake'}" ]]

converted="$("${HBN[@]}" convert --from json --to hbn --arg '{"cat":"snake","count":2}' | tr -d '\r')"
[[ "$converted" == *"'cat': 'snake'"* ]]
[[ "$converted" == *"'count': 2"* ]]

root_type="$("${HBN[@]}" type --arg "{'cat': 'snake'}" | tr -d '\r')"
[[ "$root_type" == "dict" ]]

shell_help="$("${HBN[@]}" help shell | tr -d '\r')"
[[ "$shell_help" == *"Shell output helpers"* ]]

bash_examples="$("${HBN[@]}" examples bash | tr -d '\r')"
[[ "$bash_examples" == *"Bash examples"* ]]

bash_completion="$("${HBN[@]}" completion bash | tr -d '\r')"
[[ "$bash_completion" == *"_hbn_complete"* ]]

echo "basic CLI usage examples passed"
