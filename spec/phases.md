# Specification: `hbn` CLI Phase Plan for Bash-First Hiss Byte Notation

## 1. Context

`hissbytenotation` already exists as a Python package. Its repository describes it as “a small wrapper around `ast.literal_eval`” with an API similar to serializer/deserializer libraries, and PyPI describes it as serializing and deserializing Python source notation (`hbn`). The package was last released on August 12, 2023. ([GitHub][1])

`glom` already exists as a library and CLI for nested data access and restructuring. Its docs describe path-based access, declarative transformation, readable errors, and built-in debugging, and its CLI is explicitly documented as “library first.” ([glom.readthedocs.io][2])

This spec assumes:

* `hissbytenotation` remains primarily a `loads()` / `dumps()` library.
* a new CLI layer is added as a separate feature surface
* Bash support is a first-class goal
* `glom` is used for query/traversal/transformation rather than inventing a brand-new language
* file-format interop is limited to formats supported by the Python standard library: JSON, TOML read-only via `tomllib`, and XML via `xml.etree.ElementTree` ([Python documentation][3])

## 2. Product goals

The CLI exists for people who use shell pipelines and want structured data operations without immediately dropping into ad hoc Python. The intended value is:

* HBN as a Python-literal-native data format
* a Bash-friendly CLI around HBN
* optional glom-powered querying and mutation
* careful shell-safe output modes
* only minimal dependency drag in the default install

This deliberately does **not** try to become a 15-backend serializer umbrella.

## 3. Design principles

### 3.1 Core principles

* HBN-first, Bash-first
* glom for nested data operations instead of inventing a whole new query language
* standard-library format interop only in the core
* extras for optional features
* stable exit codes
* discoverable CLI with good help and examples
* safe defaults for shell output and file mutation

### 3.2 Dependency policy

Core install should depend only on:

* Python stdlib
* `hissbytenotation`
* optionally `glom` only when query/mutation phases land

No YAML, MessagePack, XML convenience wrappers, schema systems, or formatting stacks in core. `black` and diff helpers should be optional extras or shell-outs. This matters because `tomllib` is stdlib but read-only, while `json` and `xml.etree.ElementTree` support built-in parsing and emitting paths in stdlib. ([Python documentation][3])

## 4. Packaging plan

Recommended package layout:

* `hissbytenotation` — existing serialization library
* `hissbytenotation.cli` — CLI entrypoint package/module
* extras:

  * `hissbytenotation[glom]`
  * `hissbytenotation[fmt]`
  * `hissbytenotation[diff]`
  * `hissbytenotation[dev]`

Recommended executable names:

* canonical: `hbn`
* optional long alias: `hissbytenotation`

## 5. Scope boundaries

### 5.1 In scope for this spec

* load/dump HBN
* Bash-friendly output helpers
* JSON/TOML/XML interop, within stdlib limits
* glom-backed query and transform commands
* merge semantics
* mutator subcommands
* REPL
* discoverability/help/completions
* exit status model

### 5.2 Explicitly out of scope for early phases

* parse/validate/schema as standalone feature pillars
* YAML/CSV/INI support in core
* custom HBN query language
* embedded Python execution as the main query interface
* a guaranteed lossless XML object model
* custom formatter implementation

### 5.3 Deferred

* schema inference and validation
* patch mini-language
* plugin system
* advanced XML mappings
* diff engine in core

## 6. Interop policy

### 6.1 HBN

Native format. Full read/write.

### 6.2 JSON

Required. Python stdlib `json` supports encoding/decoding and a command-line interface already exists in stdlib. JSON interop is therefore core and unavoidable. ([Python documentation][3])

### 6.3 TOML

Read-only in core. Python’s `tomllib` parses TOML but explicitly does not support writing TOML. So HBN CLI may support `--from toml`, but not `--to toml` in core. ([Python documentation][4])

### 6.4 XML

Read and write support may be offered using `xml.etree.ElementTree`, which stdlib documents as a simple and efficient API for parsing and creating XML data. However, XML mapping must be treated as a structured conversion with clear loss/ambiguity warnings, not as a perfect round-trip of arbitrary XML semantics. ([Python documentation][5])

### 6.5 Bash Map Notation

Supported as an HBN-adjacent output/input convenience syntax, not as a standards-track serialization format. This is a shell interop feature, not a general interchange format.

## 7. High-level architecture

Recommended internal layers:

1. **Codec layer**

   * HBN loads/dumps
   * JSON loads/dumps
   * TOML load only
   * XML parse/emit via defined mapping

2. **Value model layer**

   * dict
   * list
   * scalar primitives
   * maybe tuples only if HBN core already preserves them

3. **Operation layer**

   * query
   * merge
   * mutate
   * convert
   * inspect

4. **Presentation layer**

   * pretty
   * compact
   * raw scalar
   * line output
   * shell-safe output
   * bash-map-notation output

5. **CLI layer**

   * argument parsing
   * help
   * exit code mapping
   * shell completions
   * REPL

## 8. glom strategy

`glom` should be used as the query engine rather than designing a fresh syntax from scratch. Glom already covers nested access, restructuring, meaningful errors, debugging, and CLI use cases. ([glom.readthedocs.io][2])

The project should support two glom-facing modes:

### 8.1 Path mode

Simple string paths for common shell use:

```bash
hbn q 'users.0.email' file.hbn
```

or

```bash
hbn get users.0.email file.hbn
```

This is for the 80 percent case.

### 8.2 Glom spec mode

A spec string or spec file is evaluated by glom:

```bash
hbn q --glom '("users", ["email"])' file.hbn
```

or

```bash
hbn q --spec-file active_users.glomspec file.hbn
```

This is for real transformations.

### 8.3 Recommendation on “glom query language”

Call it **glom spec support**, not a new HBN query language. That keeps expectations honest and avoids language-design creep.

## 9. CLI command set

Canonical top-level commands:

* `dump`
* `load`
* `fmt`
* `q` / `query`
* `get`
* `set`
* `del`
* `append`
* `insert`
* `merge`
* `convert`
* `type`
* `keys`
* `values`
* `items`
* `len`
* `repl`
* `help`
* `version`

Deferred:

* `diff`
* `schema`
* `validate`
* `patch`

You said parse/validate/schema are out of scope for now, so they stay phase n+1.

## 10. Global options

Core global options:

* `-f`, `--file PATH`
* `--stdin`
* `--arg TEXT`
* `--from {hbn,json,toml,xml,bmn}`
* `--to {hbn,json,xml,bmn}`
* `-o`, `--output PATH`
* `--pretty`
* `--compact`
* `--sort-keys`
* `--indent N`
* `--raw`
* `--lines`
* `--nul`
* `--quiet`
* `--verbose`
* `--debug`
* `--strict`
* `--no-color`
* `--color`
* `--exit-status`

Notably absent in core:

* `--to toml`
* non-stdlib serialization backends

## 11. Bash support features

This is the centerpiece.

### 11.1 Shell-safe output helpers

* `--raw`
  emit raw scalar text when possible

* `--quoted`
  emit quoted scalar text suitable for re-input

* `--shell-quote`
  emit a single shell-escaped token

* `--shell-assign NAME`
  emit `NAME='...'`

* `--shell-export NAME`
  emit `export NAME='...'`

* `--lines`
  emit one item per line

* `--nul`
  emit one item per NUL

* `--join SEP`
  join list of scalars with separator

* `--bash-array NAME`
  emit Bash indexed-array assignment

* `--bash-assoc NAME`
  emit Bash associative-array assignment for flat dicts

* `--env-prefix PREFIX`
  flatten a dict to shell env assignments

### 11.2 Bash Map Notation

Support an input/output mode tentatively named `bmn`:

Example output:

```bash
declare -A cfg=(
  [host]='db.example'
  [port]='5432'
)
```

and/or

```bash
items=('a' 'b' 'c')
```

Rules:

* only flat dicts for `declare -A`
* only list-of-scalars for indexed arrays
* nested values require flattening or error
* shell-escaping must be deterministic
* not intended for arbitrary round-tripping of deep structures

### 11.3 Script ergonomics

* `--default VALUE`
* `--fail-on-missing`
* `--first`
* `--count`
* `--truthy`
* `--false-if-empty`

These reduce glue code in shell scripts.

## 12. Discoverability requirements

These should be built in from early on.

* `hbn help`
* `hbn help query`
* `hbn help shell`
* `hbn help glom`
* `hbn examples`
* `hbn examples bash`
* `hbn examples merge`
* `hbn examples glom`
* `hbn completion bash`
* `hbn completion zsh`
* `hbn completion fish`

This is worth doing because the CLI is meant for shell users, not just Python programmers.

## 13. Merge semantics

Merge is a must-have.

Supported strategies:

* `replace`
* `shallow`
* `deep`
* `append-lists`
* `set-union-lists`

Conflict policies:

* `error`
* `left-wins`
* `right-wins`

Recommended CLI:

```bash
hbn merge --strategy deep a.hbn b.hbn
hbn merge --strategy append-lists left.hbn right.hbn
```

Strict-mode rules:

* mismatched types error unless `replace`
* TOML-origin metadata is not preserved
* XML-origin data may lose document-order or mixed-content fidelity depending on mapping

## 14. Exit code model

A rich exit code set is a good fit for Bash.

Recommended stable exit codes:

* `0` success
* `1` false/empty result when `--exit-status` is active
* `2` input syntax/parse failure
* `3` unsupported format or conversion mode
* `4` missing key/path/query target
* `5` type mismatch during operation
* `6` invalid glom spec or glom execution failure
* `7` merge conflict
* `8` file IO error
* `9` unsafe or lossy conversion refused in strict mode
* `10` external formatter/diff tool missing
* `11` internal error

## 15. REPL

The REPL is a nice-to-have that becomes quite good once glom is present.

Minimum features:

* load file or stdin
* inspect current root as `_`
* run simple glom paths/specs
* pretty-print current result
* switch output mode
* show type
* help on commands

Commands:

* `:load path`
* `:from json|hbn|toml|xml`
* `:to hbn|json|xml|bmn`
* `:pretty`
* `:compact`
* `:raw`
* `:type`
* `:help`
* `:quit`

## 16. Formatting

Formatting should be optional and externalized.

### 16.1 HBN formatting

`hbn fmt` should:

* prefer shelling out to `black` if present
* operate on text that is valid Python-literal-style source
* fail with a clear message if `black` is not installed and no internal fallback exists

Because `black` is external, formatting belongs in an extra such as `hissbytenotation[fmt]`, or simply works when `black` is on `PATH`.

### 16.2 JSON formatting

Core can pretty-print JSON internally via stdlib.

### 16.3 XML formatting

Core may emit XML, but pretty-print stability should be documented as best-effort unless an external formatter is installed.

### 16.4 TOML formatting

Out of scope in core because stdlib has no writer. ([Python documentation][4])

## 17. Diff

Diff belongs in extras, as you suggested.

### 17.1 Core stance

No custom structural diff in phase 1.

### 17.2 Extra

`hbn diff` may be provided by an optional dependency or by shelling out to a system diff after canonicalized conversion to HBN or JSON.

Suggested behavior:

* convert both inputs to canonical HBN or JSON
* run external diff if present
* preserve useful exit statuses

## 18. XML mapping policy

This needs explicit rules because XML is not just dict/list/scalars.

Recommended mapping for core:

* element tag -> dict key or object field
* attributes -> `@attrs`
* text -> `#text`
* child elements -> nested structures
* repeated sibling tags -> list
* mixed content -> either unsupported or represented verbosely

Example:

```xml
<user id="1"><name>Matt</name></user>
```

maps to something like:

```python
{
    "user": {
        "@attrs": {"id": "1"},
        "name": "Matt",
    }
}
```

This mapping is not perfect, and the CLI should say so. Python’s stdlib XML docs already warn users to consider XML security for untrusted data, so the tool should echo that caution for XML input. ([Python documentation][6])

## 19. Phase plan

## Phase 0: polish the library surface

Goal: make the existing `loads`/`dumps` package feel solid before adding a big CLI.

Includes:

* document HBN syntax clearly
* document guarantees and non-guarantees vs `ast.literal_eval`
* document performance claims carefully, including the Rust speedup if present in the project
* add basic examples for shell users
* keep API tiny

Deliverables:

* refreshed README
* explicit compatibility notes
* stable API docs for `load`, `loads`, `dump`, `dumps`

## Phase 1: Bash-first core CLI

Goal: make HBN actually useful from the shell even before glom support.

Commands:

* `dump`
* `fmt`
* `convert`
* `type`
* `keys`
* `values`
* `items`
* `len`

Supported formats:

* HBN
* JSON
* TOML input only
* XML basic mapping
* Bash Map Notation output/input where feasible

Features:

* `--raw`
* `--lines`
* `--nul`
* `--shell-quote`
* `--shell-assign`
* `--shell-export`
* `--bash-array`
* `--bash-assoc`
* `--default`
* rich exit codes
* help/examples/completions

Not included yet:

* glom
* schema
* parse/validate commands
* diff
* REPL

## Phase 2: glom integration

Goal: add nested traversal and reshaping without inventing a new DSL.

Commands:

* `q`
* `get`
* `set`
* `del`
* `append`
* `insert`

Features:

* path mode for common lookups
* `--glom` or default glom-spec mode
* `--spec-file`
* glom exception mapping to stable CLI errors
* simple examples that translate shell tasks into glom specs

Discoverability additions:

* `hbn help glom`
* `hbn examples glom`
* `hbn examples shell`

This phase depends on glom, whose docs emphasize nested data access, restructuring, debugging, and CLI use. ([glom.readthedocs.io][2])

## Phase 3: merge and higher-value mutations

Goal: support real config/data workflows.

Commands:

* `merge`
* improved `set`
* improved `append`
* improved `insert`

Features:

* merge strategies
* conflict policies
* `--in-place`
* `--backup`
* `--atomic`
* `--check`

This is probably where HBN becomes genuinely handy in CI and shell automation.

## Phase 4: REPL and discoverability polish

Goal: make the tool learnable and pleasant.

Includes:

* REPL
* command aliases
* shell completions
* richer examples
* `hbn doctor` maybe, for checking optional extras and external tools

## Phase 5: optional extras

Goal: keep core lean, but allow nice toys.

Extras:

* `[fmt]` for formatter integration
* `[diff]` for diff helper
* maybe `[xmlplus]` later if you ever want richer XML handling, but not now

## Phase N+1: schema / validate / parse

Goal: advanced correctness tooling.

Explicitly deferred per your guidance:

* `parse`
* `validate`
* `schema`

This phase may eventually include:

* schema inference for HBN/JSON-ish structures
* shape summaries
* structural assertions
* not-yet-implemented rules engine

## 20. Recommended command synopsis

A plausible command family:

```bash
hbn dump [options] [file]
hbn fmt [options] [file ...]
hbn convert --from FMT --to FMT [file]
hbn q [options] <spec-or-path> [file]
hbn get <path> [file]
hbn set <path> --value VALUE [file]
hbn del <path> [file]
hbn append <path> --value VALUE [file]
hbn insert <path> --index N --value VALUE [file]
hbn merge [options] left right
hbn type [path] [file]
hbn keys [path] [file]
hbn values [path] [file]
hbn items [path] [file]
hbn len [path] [file]
hbn repl
hbn help [topic]
hbn version
```

Aliases:

* `q` for query
* `fmt`
* `del`
* maybe `c` for `convert`, though I would avoid too many one-letter commands

## 21. Practical product positioning

The best positioning is not “glom but different.” It is:

* HBN is the Python-literal-native format
* `hbn` is the Bash-first CLI
* glom is the optional nested-data engine

That gives each piece a job:

* `hissbytenotation`: serialization
* `hbn`: shell ergonomics
* `glom`: structured querying and transformation

That is a coherent story and avoids accidental framework bloat.

## 22. Recommendation summary

Build this in this order:

1. phase 1 Bash-first core CLI
2. phase 2 glom integration
3. phase 3 merge/mutation
4. phase 4 REPL/discoverability
5. phase 5 optional diff/format extras
6. phase N+1 schema/validate/parse

The strongest constraint to keep repeating is this:

**core should stay small, stdlib-heavy, and shell-practical.**

That keeps the project from turning into “every serializer on PyPI plus three query languages plus a schema engine.”

If you want, I can turn this into a release-by-release implementation checklist with concrete argparse/typer command signatures and Python module layout.

[1]: https://github.com/matthewdeanmartin/hissbytenotation?utm_source=chatgpt.com "Library to make it easy to use python literal syntax as a ..."
[2]: https://glom.readthedocs.io/?utm_source=chatgpt.com "glom — glom 25.12.0 documentation"
[3]: https://docs.python.org/3/library/json.html?utm_source=chatgpt.com "JSON encoder and decoder — Python 3.14.3 documentation"
[4]: https://docs.python.org/3/library/tomllib.html?utm_source=chatgpt.com "tomllib — Parse TOML files"
[5]: https://docs.python.org/3/library/xml.etree.elementtree.html?utm_source=chatgpt.com "xml.etree.ElementTree — The ElementTree XML API"
[6]: https://docs.python.org/3/library/xml.html?utm_source=chatgpt.com "XML Processing Modules"
