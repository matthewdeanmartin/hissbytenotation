ifeq ($(origin VIRTUAL_ENV),undefined)
    VENV := uv run
else
    VENV :=
endif

uv.lock: pyproject.toml
	@echo "Installing dependencies"
	@uv lock


# tests can't be expected to pass if dependencies aren't installed.
# tests are often slow and linting is fast, so run tests on linted code.
test: pylint bandit uv.lock
	@echo "Running unit tests"
	# $(VENV) pytest hissbytenotation --doctest-modules
	# $(VENV) python -m unittest discover
	$(VENV) py.test test --cov=hissbytenotation --cov-report=html --cov-fail-under 65

isort:  
	@echo "Formatting imports"
	$(VENV) isort hissbytenotation


black:  isort 
	@echo "Formatting code"
	$(VENV) black .


pre-commit:  isort black
	@echo "Pre-commit checks"
	$(VENV) pre-commit run --all-files


bandit:  
	@echo "Security checks"
	$(VENV)  bandit hissbytenotation

.PHONY: pylint
pylint:  isort black 
	@echo "Linting with pylint"
	$(VENV) pylint hissbytenotation --fail-under 9.9

mypy:
	@echo "Security checks"
	$(VENV)  mypy hissbytenotation

.PHONY: format benchmark perf-wheel perf-python-tests perf-rust-tests perf-rust-only perf-benchmark perf-check perf
format: isort black

benchmark:
	@echo "Running benchmarks"
	$(VENV) python -m benchmark

perf-wheel:
	@echo "Building release Rust wheel"
	uv run --with maturin maturin build --release --manifest-path rust\Cargo.toml --out rust\dist

perf-python-tests: perf-wheel
	@echo "Running Python tests with the release Rust wheel"
	@powershell -NoProfile -Command '$$wheel = Get-ChildItem "rust\dist\hbn_rust-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $$wheel) { throw "No wheel built in rust\dist" }; uv run --with $$wheel.FullName python -m pytest -q'

perf-rust-tests:
	@echo "Running Rust unit tests"
	cargo test --manifest-path rust\Cargo.toml

perf-rust-only: perf-wheel
	@echo "Benchmarking the Rust parser only"
	@powershell -NoProfile -Command '$$wheel = Get-ChildItem "rust\dist\hbn_rust-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $$wheel) { throw "No wheel built in rust\dist" }; uv run --with $$wheel.FullName python -m benchmark.rust_only -n 5000'

perf-benchmark: perf-wheel
	@echo "Running the full benchmark suite with the release Rust wheel"
	@powershell -NoProfile -Command '$$wheel = Get-ChildItem "rust\dist\hbn_rust-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $$wheel) { throw "No wheel built in rust\dist" }; uv run --with $$wheel.FullName python -m benchmark -n 5000'

perf-check: perf-python-tests perf-rust-tests

perf: perf-check perf-rust-only perf-benchmark

check: test pylint bandit pre-commit mypy

.PHONY: publish
publish: check
	rm -rf dist && $(VENV) hatch build
