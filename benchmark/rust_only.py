"""Benchmark only the Rust parser path."""

import argparse
import timeit

import hissbytenotation as hbn
import test.generate as generator


def run_rust_only(count: int = 5000) -> None:
    data = generator.generate_test_data(no_bytes=True, no_sets=True, no_elipsis=True)
    serialized = hbn.dumps(data, validate=False)
    elapsed = timeit.timeit(lambda: hbn.loads(serialized, by_rust=True), number=count)
    print(f"Rust parser only: {elapsed:.3f}s for {count} iterations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark only the Rust parser path")
    parser.add_argument("-n", "--count", type=int, default=5000, help="Number of iterations (default: 5000)")
    args = parser.parse_args()
    run_rust_only(args.count)
