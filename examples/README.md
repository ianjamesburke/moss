# Moss examples

Every example is a real, runnable Moss program.

## Running

From the repo root:

```sh
./moss run examples/01_hello.moss
```

First run compiles `serde_json` (~10 seconds). Every run after that is instant — Moss caches compiled binaries by source hash in `~/.moss/bin/`.

Replace the filename with whichever example you want to run.

## Other commands

```sh
./moss show-rust examples/01_hello.moss
```
Print the Rust code Moss generates for an example.

```sh
./moss build examples/01_hello.moss
```
Produce a standalone binary in the current directory. Shareable — no Moss install needed to run it.

## Index

| File | What it teaches |
|------|-----------------|
| `01_hello.moss` | First program. `fn main` and `output`. |
| `02_output_record.moss` | Records as indented key/value blocks. |
| `03_nested.moss` | Records inside records. |
| `04_variables.moss` | Top-level variables, used inside `main`. |
| `05_interpolation.moss` | Dropping values into strings with `{name}`. |
| `06_lists.moss` | Lists of text and numbers. |
| `07_plexi_poc.moss` | A Plexi app proof of concept — PGAP-shaped message. |
| `08_module_input.moss` | Reading JSON from stdin with `input.name` dot access. |
| `09_pipeline_source.moss` | Source stage of a Unix pipeline. |
| `09_pipeline_sink.moss` | Sink stage that transforms input from the source. |
| `TEACHING.moss` | Every rule of Moss in one file. |

## Pipelines

Moss programs compose via Unix pipes. Each program reads JSON from stdin as `input`, and emits JSON via `output`:

```sh
./moss run examples/09_pipeline_source.moss | ./moss run examples/09_pipeline_sink.moss
```

You can also pipe in data directly:

```sh
echo '{"name":"ada","count":3}' | ./moss run examples/08_module_input.moss
```

## What's not implemented yet

These are in the spec but not in the compiler:

- Functions with parameters and `return`
- `if` / `else if` / `else`
- `for` loops, `stop`, `skip`
- Arithmetic and comparison operators
- List indexing and `length()`
- `takes` / `gives` declarations with defaults and test values
