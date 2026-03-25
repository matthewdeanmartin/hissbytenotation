# Installation

Install the base package with:

```bash
pip install hissbytenotation
```

Install all optional Python extras with:

```bash
pip install "hissbytenotation[all]"
```

If you use `uv`, the matching command is:

```bash
uv sync --extra all
```

Install a single optional feature with one of these extras:

- `fmt`: `pip install "hissbytenotation[fmt]"` or `uv sync --extra fmt`
- `glom`: `pip install "hissbytenotation[glom]"` or `uv sync --extra glom`
- `validate`: `pip install "hissbytenotation[validate]"` or `uv sync --extra validate`

Rust acceleration is optional and comes from the `hissbytenotation` wheel for supported platforms. If no wheel is
available for your machine, the package still installs and uses the pure-Python implementation. To build the optional
Rust extension locally, run:

```bash
cd rust && maturin develop --release
```
