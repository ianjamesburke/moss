# Moss examples

Every example is a real, runnable Moss program.

## How to run any example

From the repo root (`~/Documents/GitHub/moss`):

```sh
./moss run examples/01_hello.moss
```

Replace the filename with whichever example you want to run. The first run compiles `serde_json` which takes ~10 seconds. Every run after that is near-instant because the Rust workspace stays warm.

## Other commands

```sh
./moss show-rust examples/01_hello.moss
```
Prints the Rust code Moss generates, without running it. Great for seeing how Moss maps to Rust.

```sh
./moss build examples/01_hello.moss
```
Compiles to a standalone binary in the current directory. You can share that binary with anyone — they don't need Moss installed.

## Index

| File | What it teaches |
|------|-----------------|
| `01_hello.moss` | Your first Moss program. A `main` function and an `emit`. |
| `02_emit_record.moss` | Building a record (key/value data) and emitting it as JSON. |
| `03_nested.moss` | Records inside records. |
| `04_variables.moss` | Top-level variables, reused inside `main`. |
| `05_interpolation.moss` | Dropping values into strings with `{name}`. |
| `06_lists.moss` | Lists of text and numbers. |
| `07_plexi_poc.moss` | A Plexi app proof of concept — emits a PGAP-shaped message. |
| `TEACHING.moss` | Every rule of Moss in one heavily commented file. Read this top-to-bottom and you know the language. |

## What's not working yet

This repo ships the **v0 runnable subset**. These features are in the spec but not yet in the compiler:

- Functions with parameters
- `return`
- `if` / `else if` / `else`
- `for` loops
- `stop` / `skip`
- Arithmetic and comparison operators
- List indexing (`tags[1]`) and `length()`

They're next in the queue.
