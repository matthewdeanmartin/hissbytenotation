# Hiss Byte Notation

Library to make it easy to use python literal syntax as a data format. No JavaScript and fast.

Have you seen people try to print a dict and then use the JSON library to parse the output? This library is some
helper function for that scenario. It has an API similar to other serialization libraries with dumps, loads and so on.

It is a small wrapper all the ways that python has to convert python literals to live python

- ast.literal_eval
- import
- etc.

However, I don't recommend using any of those except Pickle because performance is so bad. Instead use hsbn with the
rust speed ups which are now the default.

## Safety

`ast.literal_eval` is safer than `eval` but the python docs still imply that there are malicious payloads. I'm not
sure if they are the same problems that could affect json or other formats.

The Rust parser (`by_rust=True`) is safe — it only parses literal syntax and never executes arbitrary code.

## Usage

Learn how to use it with the GUI which demos all the features

```bash
hissbytenotation gui
```

Normal usage is as a library.

```python
import hissbytenotation as hbn

data = {
    "mammal": "cat",
    "reptile": ["snake", "lizard"],
    "version": 1
}
data_as_string = hbn.dumps(data)

rehydrated = hbn.loads(data_as_string)
print(rehydrated)
# {'mammal': 'cat', 'reptile': ['snake', 'lizard'], 'version': 1}
```

## CLI

It now has a Bash-first CLI with the `hbn` command:

```bash
uv run hbn dump --arg "{'mammal': 'cat', 'version': 1}"
uv run hbn convert --from json --to hbn --arg '{"mammal": "cat", "version": 1}'
uv run hbn keys --arg "{'mammal': 'cat', 'version': 1}" --lines
uv run hbn dump --arg "['cat', 'snake']" --bash-array animals
uv run hbn dump --arg "{'host': 'db', 'port': '5432'}" --bash-assoc cfg
uv run hbn get users.0.email users.hbn --raw
uv run hbn q --glom "{'emails': ('users', ['email'])}" users.hbn
uv run hbn set users.0.role --value "'admin'" users.hbn
uv run hbn merge left.hbn right.hbn
uv run hbn merge --strategy append-lists left.hbn right.hbn
uv run hbn diff left.hbn right.hbn
uv run hbn doctor --to json --pretty
uv run hbn repl users.hbn
```

Supported core formats:

- HBN input and output
- JSON input and output
- TOML input
- XML input and output via a simple `@attrs` / `#text` mapping
- Bash Map Notation (`bmn`) for flat dicts and scalar arrays

Useful shell-oriented output flags:

- `--raw`
- `--lines`
- `--nul`
- `--shell-quote`
- `--shell-assign NAME`
- `--shell-export NAME`
- `--bash-array NAME`
- `--bash-assoc NAME`
- `--default VALUE`

For nested traversal and mutation, install the optional glom extra:

```bash
uv sync --extra glom
uv run hbn q users.0.email users.hbn --raw
uv run hbn q --glom "{'emails': ('users', ['email'])}" users.hbn
uv run hbn append users --value "{'email': 'new@example.com'}" users.hbn
```

It now has glom commands, which is a query language for python dicts and types:

- `q` / `query`
- `get`
- `set`
- `del`
- `append`
- `insert`

Glom query mode supports:

- simple dot-path lookups such as `users.0.email`
- `--glom SPEC` for explicit glom specs written in HBN / Python literal syntax
- `--spec-file PATH` for reusable glom specs

It supports merge and mutation workflows:

- `merge`
- merge strategies: `replace`, `shallow`, `deep`, `append-lists`, `set-union-lists`
- conflict policies: `error`, `left-wins`, `right-wins`
- file mutation flags: `--in-place`, `--backup SUFFIX`, `--atomic`, `--check`

Examples:

```bash
uv run hbn merge --conflict right-wins --left-arg "{'a': 1}" --right-arg "{'a': 2}"
uv run hbn set config.port --value 6432 --in-place settings.hbn
uv run hbn append users --value "{'email': 'new@example.com'}" --backup .bak users.hbn
```

It supports some discoverability and interactive workflows:

- `repl`
- `doctor`
- friendly aliases such as `show`, `format`, `delete`, and `count`
- richer help and examples topics via `hbn help TOPIC` and `hbn examples TOPIC`
- shell completion scripts for Bash, Zsh, Fish, and PowerShell

Examples:

```bash
uv run hbn show --arg "{'a': 1}"
uv run hbn delete users.0.role users.hbn
uv run hbn count --arg "[1, 2, 3]"
uv run hbn doctor --compact
uv run hbn completion powershell
uv run hbn repl users.hbn
```

Inside the REPL:

```text
load {'users': [{'email': 'a@example.com'}]}
get users.0.email --raw
set users.0.role --value "'admin'"
merge --value "{'users': [{'email': 'b@example.com'}]}" --strategy append-lists
write session.json --to json --pretty
```

The `doctor` command reports optional capabilities and install hints for:

- formatter support via `black`
- diff helper support, preferring `git diff --no-index` when available
- optional `glom` integration
- optional `hbn_rust` acceleration
- `uv` and `git` availability on `PATH`

Install shell completions by evaluating or sourcing the generated script for your shell:

```bash
uv run hbn completion bash
uv run hbn completion zsh
uv run hbn completion fish
uv run hbn completion powershell
```

For formatter support, install the optional extra and use `hbn fmt`:

```bash
uv sync --extra fmt
uv run hbn fmt --arg "{'b':2,'a':1}"
```

`hbn fmt` prefers shelling out to the `black` executable when it is available and falls back to the Python package API when it is installed without the command on `PATH`.

It supports optional extras and helpers:

- `fmt` for formatter integration
- `diff` for canonicalized text diffs

Examples:

```bash
uv run hbn diff left.hbn right.hbn
uv run hbn diff --to json left.hbn right.hbn
uv run hbn diff --tool builtin --left-arg "{'a': 1}" --right-arg "{'a': 2}"
uv run hbn fmt --arg "{'b':2,'a':1}"
```

The `diff` command:

- canonicalizes both inputs as HBN or JSON
- prefers `git diff --no-index` when `git` is available
- falls back to a builtin unified diff renderer otherwise
- returns `0` for no diff and `1` when differences are found

### Rust-accelerated parsing

Install `hissbytenotation` normally. Platform wheels can include the optional Rust parser for a ~14x speedup over `ast.literal_eval`; source installs fall back to the pure-Python implementation:

```bash
pip install hissbytenotation
# or build the optional extension from source:
cd rust && maturin develop --release
```

```python
fast = hbn.loads(data_as_string, by_rust=True)
```

## How it works

Serialization is done by calling repr, checking if ast.literal_eval can read it. Repr can be called on more data
structures than ast.literal_eval can handle.

Because ast.literal_eval is so slow, there are other options for deserialization:

- **Rust parser** (`by_rust=True`): ~14x faster than ast.literal_eval. Safe — no code execution. Available when the optional Rust extension is present.
- **default**: ast.literal_eval with validation enabled. Very slow, very safe.
- **eval** (`by_eval=True`): Slow, only for trusted data.
- **exec** (`by_exec=True`): Slow, only for trusted data.
- **import** (`by_import=True`): Two times faster than exec, only for trusted data.

## Deserialization benchmark — 1,000 iterations

| Method                 |    Time | Notes     |
|------------------------|--------:|-----------|
| Pickle                 |  0.084s |           |
| JSON                   |  0.252s |           |
| **HBN (Rust parser)**  |  0.510s | safe      |
| HBN (eval)             |  4.968s | unsafe    |
| HBN (ast.literal_eval) |  6.984s | safe      |
| HBN (exec)             |  5.357s | unsafe    |
| HBN (import)           | 10.790s | unsafe    |
| repr() only            |  0.339s | serialize |

**Rust parser is ~14x faster than ast.literal_eval** and the fastest safe option.

Run the benchmark yourself:

```bash
python -m benchmark
python -m benchmark -n 5000  # more iterations
```

## Prior art

- [literal-python-to-pickle](https://github.com/albertz/literal-python-to-pickle) A faster replacement for
  ast.literal_eval and
  corresponding [question on stackoverflow](https://stackoverflow.com/questions/66480073/fastest-implementation-of-ast-literal-eval).

- You could just call `repr` and `ast.literal_eval` directly.

Possibly [astor](https://pypi.org/project/astor/) which serializes to a string representation of the AST, which looks
nothing like the source code, nor json.
