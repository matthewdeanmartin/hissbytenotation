"""Run benchmarks: python -m benchmark"""

import argparse

from benchmark.main import run_benchmarks

parser = argparse.ArgumentParser(description="Benchmark hissbytenotation")
parser.add_argument("-n", "--count", type=int, default=1000, help="Number of iterations (default: 1000)")
args = parser.parse_args()
run_benchmarks(args.count)
