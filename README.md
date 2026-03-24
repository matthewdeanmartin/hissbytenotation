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

Phase 1 ships a Bash-first CLI with the `hbn` command:

```bash
uv run hbn dump --arg "{'mammal': 'cat', 'version': 1}"
uv run hbn convert --from json --to hbn --arg '{"mammal": "cat", "version": 1}'
uv run hbn keys --arg "{'mammal': 'cat', 'version': 1}" --lines
uv run hbn dump --arg "['cat', 'snake']" --bash-array animals
uv run hbn dump --arg "{'host': 'db', 'port': '5432'}" --bash-assoc cfg
```

Supported phase 1 formats:

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

For formatter support, install the optional extra and use `hbn fmt`:

```bash
uv sync --extra fmt
uv run hbn fmt --arg "{'b':2,'a':1}"
```

### Rust-accelerated parsing

Install the `hbn_rust` package for a ~14x speedup over `ast.literal_eval`:

```bash
pip install hbn-rust
# or build from source:
cd rust && maturin develop --release
```

```python
fast = hbn.loads(data_as_string, by_rust=True)
```

## How it works

Serialization is done by calling repr, checking if ast.literal_eval can read it. Repr can be called on more data
structures than ast.literal_eval can handle.

Because ast.literal_eval is so slow, there are other options for deserialization:

- **Rust parser** (`by_rust=True`): ~14x faster than ast.literal_eval. Safe — no code execution. Requires `hbn_rust`.
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
