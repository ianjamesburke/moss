# Moss

A small language that reads like English and compiles to Rust.

Moss programs receive input, build values, and emit structured JSON to stdout. The source syntax hides JSON entirely — no braces, no quoted keys. You write what you mean; Moss handles the encoding.

```moss
fn main
    emit
        type: ready
        payload:
            service: "demo"
            ok: true
```

stdout:
```json
{"type":"ready","payload":{"service":"demo","ok":true}}
```

---

## Design rules

**One page.** The entire language fits on this page. If it doesn't fit, it's too big.

**One day.** You should be able to read this spec and write real programs by end of day.

**One way.** There is exactly one way to write each construct. No alternate syntax, no optional punctuation, no sugar. If two forms exist, one gets removed.

**Fail first.** The compiler finds the first error, prints it clearly, and stops. No warnings. No continuing past broken code. Fix it and try again.

**Read like English.** Keywords over symbols. Indentation over braces. Named values over inline noise.

---

## Syntax

### Comments

```moss
# this is a comment
```

### Variables

Top-level constants use `let`:
```moss
let name = "ian"
let retries = 3
let debug = false
```

Inside functions, first assignment creates a local. Reassignment is allowed:
```moss
fn main
    count = 0
    count = count + 1
```

No `let` inside functions. No shadowing — assigning an existing name updates it.

### Strings

```moss
let greeting = "hello, world"
let message = "status: " + code
```

Use `{name}` for interpolation:
```moss
let reply = "hello, {name}"
```

### Numbers

```moss
let port = 8080
let ratio = 0.75
```

### Booleans

```moss
let active = true
let done = false
```

### Null

```moss
let error = null
```

### Arrays

Inline for short lists:
```moss
let tags = ["fast", "simple", "clear"]
```

Multi-line for longer:
```moss
let steps =
    - "connect"
    - "authenticate"
    - "listen"
```

### Objects

Always written as indented key-value blocks. No braces. No quoted keys.

```moss
let config =
    host: "localhost"
    port: 8080
    debug: true
```

Nested:
```moss
let response =
    type: ready
    payload:
        service: "demo"
        version: "1.0"
```

If you need to pass an object to a function, assign it first:
```moss
fn main
    data =
        service: "demo"
    emit message("ready", data)
```

This is intentional — naming things makes code readable.

### Functions

```moss
fn greet(name)
    return "hello, {name}"
```

No params:
```moss
fn timestamp
    return 0
```

Functions return `null` if no `return` is reached.

### Return

```moss
fn answer
    return 42
```

Early return is allowed:
```moss
fn check(value)
    if value == null
        return false
    return true
```

### If / else

```moss
fn label(code)
    if code == 200
        return "ok"
    else if code == 404
        return "missing"
    else
        return "unknown"
```

### Operators

Arithmetic:
```
+  -  *  /
```

Comparison:
```
==  !=  >  >=  <  <=
```

Logic (words, not symbols):
```
and  or  not
```

`+` works on numbers and strings. No implicit coercion — adding a number to a string is a compile error.

---

## Builtins

### `emit`

Encodes a value as JSON and writes one line to stdout.

```moss
fn main
    emit
        type: ready
        payload:
            service: "demo"
```

stdout:
```json
{"type":"ready","payload":{"service":"demo"}}
```

Rules:
- Always compact JSON
- Always appends a newline
- If the value cannot be encoded, the program exits with code 1

### `fail`

Prints an error message to stderr and exits with code 1.

```moss
fail "something went wrong"
```

stderr:
```
error: something went wrong
```

### `print`

Prints a plain string to stdout. For debugging only — not protocol-safe.

```moss
print "starting up"
print "count is {count}"
```

---

## Compiler behavior

```sh
moss run app.moss          # compile and run
moss build app.moss        # compile to binary
moss build app.moss --rust # emit Rust source
moss check app.moss        # typecheck only, no output
```

**Fail first.** On any error, the compiler prints one message and exits immediately. It does not collect multiple errors. Fix the error and run again.

Error format:
```
error: unknown function 'greet'
 --> app.moss:6:5
  |
6 |     emit greet("ian")
  |          ^^^^^
```

---

## Compile-time errors

| Error | Cause |
|-------|-------|
| `unknown function` | Calling a function that doesn't exist |
| `wrong number of arguments` | Calling a function with the wrong arity |
| `duplicate function` | Two functions with the same name |
| `missing main` | No `main` function defined |
| `type mismatch` | Adding a string to a number, etc. |
| `invalid indentation` | Mixed tabs/spaces or broken block structure |
| `undefined variable` | Using a name before assigning it |

---

## Example programs

### Hello world

```moss
fn main
    print "hello, world"
```

### Emit a message

```moss
fn main
    emit
        type: ready
        ok: true
```

### Using a variable

```moss
let service = "demo"

fn main
    emit
        type: ready
        payload:
            service: service
```

### Helper function

```moss
fn message(kind, data)
    return
        type: kind
        payload: data

fn main
    data =
        service: "demo"
    emit message("ready", data)
```

### Conditional response

```moss
fn respond(code)
    if code == 200
        emit
            type: success
    else if code == 404
        emit
            type: not_found
    else
        fail "unexpected status: {code}"

fn main
    respond(200)
```

### Validation

```moss
fn is_valid(name)
    return not name == null and not name == ""

fn greet(name)
    if not is_valid(name)
        fail "name is required"
    return "hello, {name}"

fn main
    print greet("ian")
```

### Building a response from parts

```moss
let version = "1.0"

fn make_error(msg)
    return
        type: error
        error:
            message: msg
            version: version

fn make_success(data)
    return
        type: success
        payload: data
        error: null

fn main
    result =
        service: "demo"
        ready: true
    emit make_success(result)
```

### Array usage

```moss
fn main
    tags = ["fast", "simple", "clear"]
    emit
        type: info
        payload:
            tags: tags
            count: 3
```

---

## What Moss compiles to

Moss generates readable Rust. This Moss:

```moss
fn main
    emit
        type: ready
        ok: true
```

Generates this Rust:

```rust
use serde_json::json;

fn main() {
    let value = json!({
        "type": "ready",
        "ok": true
    });
    println!("{}", value);
}
```

All values map to `serde_json::Value`. No borrow complexity is exposed in the source language. Objects compile to `json!` macros. Strings compile to owned `String`.

---

## What Moss is not

- Not a systems language — use Rust directly for that
- Not a general-purpose language — for v0, one file, one main, stdout output
- Not a config format — use TOML/YAML for that
- Not async — everything is synchronous
- Not object-oriented — no classes, no methods, no inheritance

---

## Implementation order

**Phase 1 — core**
- Tokenizer
- Indentation-aware parser (indent/dedent tokens)
- AST: literals, objects, arrays, functions, emit
- `fn main` + `emit` + `print`
- Rust code generator

**Phase 2 — language**
- Function calls and return
- Variables and reassignment
- `if / else if / else`
- `fail`
- String interpolation

**Phase 3 — compiler**
- `moss check` (errors only, no output)
- `--rust` flag
- Source-location error messages
- Duplicate/missing function detection

**Phase 4 — grow**
- Loops (`for item in list`)
- Multi-file programs
- Standard library (string, math, list helpers)
- LSP / editor support

---

## Grammar

```
program      := (let_decl | fn_decl)*
let_decl     := "let" IDENT "=" expr NEWLINE
fn_decl      := "fn" IDENT params? NEWLINE block
params       := "(" (IDENT ("," IDENT)*)? ")"
block        := INDENT stmt+ DEDENT
stmt         := return_stmt
             | emit_stmt
             | fail_stmt
             | print_stmt
             | if_stmt
             | assignment
             | expr_stmt
return_stmt  := "return" expr? NEWLINE
emit_stmt    := "emit" (expr | NEWLINE object_block) NEWLINE
fail_stmt    := "fail" expr NEWLINE
print_stmt   := "print" expr NEWLINE
if_stmt      := "if" expr NEWLINE block ("else if" expr NEWLINE block)* ("else" NEWLINE block)?
assignment   := IDENT "=" (expr | NEWLINE object_block) NEWLINE
object_block := INDENT (IDENT ":" (expr | NEWLINE object_block) NEWLINE)+ DEDENT
array_block  := INDENT ("-" expr NEWLINE)+ DEDENT
expr         := literal | IDENT | call | binary | unary | interp_string
call         := IDENT "(" (expr ("," expr)*)? ")"
binary       := expr op expr
unary        := "not" expr
op           := "+" | "-" | "*" | "/" | "==" | "!=" | ">" | ">=" | "<" | "<=" | "and" | "or"
literal      := STRING | NUMBER | BOOL | "null"
             | "[" (expr ("," expr)*)? "]"
             | "[" NEWLINE array_block "]"
```

---

## Crate

The compiler is published as `moss-lang` on crates.io. The CLI is `moss`.

```sh
cargo install moss-lang
moss run hello.moss
```
