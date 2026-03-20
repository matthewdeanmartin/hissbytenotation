"""
Benchmark suite for hissbytenotation.

Run with:
    python -m benchmark
"""

import pickle
import json
import timeit

import hissbytenotation as hbn
import test.generate as generator

# Check optional dependencies
try:
    import hbn_rust

    HAS_RUST = True
except ImportError:
    HAS_RUST = False

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from asteval import Interpreter

    HAS_ASTEVAL = True
except ImportError:
    HAS_ASTEVAL = False


def run_benchmarks(count: int = 1000) -> None:
    data = generator.generate_test_data(no_bytes=True, no_sets=True, no_elipsis=True)
    serialized_hbn = hbn.dumps(data, validate=False)
    serialized_json = json.dumps(data)
    serialized_pickle = pickle.dumps(data)

    results: list[tuple[str, float, str]] = []

    # --- Baselines ---
    t = timeit.timeit(lambda: pickle.loads(serialized_pickle), number=count)
    results.append(("Pickle", t, ""))

    t = timeit.timeit(lambda: json.loads(serialized_json), number=count)
    results.append(("JSON", t, ""))

    # --- HBN methods ---
    if HAS_RUST:
        t = timeit.timeit(lambda: hbn.loads(serialized_hbn, by_rust=True), number=count)
        results.append(("HBN (Rust parser)", t, "safe"))

    t = timeit.timeit(lambda: hbn.loads(serialized_hbn), number=count)
    results.append(("HBN (ast.literal_eval)", t, "safe"))

    t = timeit.timeit(lambda: hbn.loads(serialized_hbn, by_eval=True), number=count)
    results.append(("HBN (eval)", t, "unsafe"))

    t = timeit.timeit(lambda: hbn.loads(serialized_hbn, by_exec=True), number=count)
    results.append(("HBN (exec)", t, "unsafe"))

    t = timeit.timeit(lambda: hbn.loads(serialized_hbn, by_import=True), number=count)
    results.append(("HBN (import)", t, "unsafe"))

    if HAS_ASTEVAL:
        aeval = Interpreter(minimal=True)
        t = timeit.timeit(lambda: aeval(serialized_hbn), number=count)
        results.append(("HBN (asteval)", t, "safe"))

    # --- Serialization-only ---
    t = timeit.timeit(lambda: repr(data), number=count)
    results.append(("repr() only", t, "serialize"))

    # --- Print ---
    print(f"\n## Deserialization benchmark — {count} iterations\n")
    print(f"{'Method':<30} {'Time':>10} {'Notes':>10}")
    print("-" * 55)

    ast_time = None
    for name, time_s, note in results:
        if name == "HBN (ast.literal_eval)":
            ast_time = time_s
        print(f"{name:<30} {time_s:>9.3f}s {note:>10}")

    if ast_time and HAS_RUST:
        rust_time = next(t for n, t, _ in results if n == "HBN (Rust parser)")
        print(f"\nRust parser is {ast_time / rust_time:.1f}x faster than ast.literal_eval")

    if not HAS_RUST:
        print("\n(Rust parser not installed — cd rust && maturin develop --release)")


if __name__ == "__main__":
    run_benchmarks()
