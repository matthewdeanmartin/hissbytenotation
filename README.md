# Hiss Byte Notation

Library to make it easy to use python literal syntax as a data format

Have you seen people try to print a dict and then use the JSON library to parse the output? This library is some
helper function for that scenario. It is a small wrapper around ast.literal_eval and will have a API similar to other
serializer/deserializers such as json, pickle, pyyaml, etc.

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
