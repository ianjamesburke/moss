# Moss

A tiny language for writing Plexi apps.

Moss programs emit structured JSON messages to stdout using the [PGAP protocol](https://github.com/ianjamesburke/plexi). The entire job of a Moss program is to receive input, build a value, and emit it as a PGAP-compliant message.

```moss
fn main
    emit {
        "type": "ready",
        "payload": {
            "service": "demo"
        }
    }
```

stdout:
```json
{"protocol":"pgap/1","type":"ready","id":null,"payload":{"service":"demo"},"error":null}
```

---

## Why

Plexi apps are just processes that speak PGAP over stdout. Moss makes writing those processes as simple as possible — no boilerplate, no imports, no runtime to configure. You describe what to emit, Moss handles the envelope.

---

## File extension

`.moss`

---

## v0 Scope

**Supported:**
- One-file programs
- Top-level constants (`let`)
- One `main` function
- Strings, numbers, booleans, null
- Arrays and objects
- Local variables and simple reassignment
- Function declarations and calls
- `emit` — writes a PGAP envelope to stdout
- `print` — plain debug output
- `if / else if / else`
- `return`

**Not in v0:**
- Classes
- Async
- Imports
- Custom types
- Loops (v1)
- Pattern matching (v1)

---

## Language

### Comments

```moss
# this is a comment
```

### Variables

Top-level:
```moss
let version = "pgap/1"
let retries = 3
```

Inside functions — first assignment creates a local, reassignment is allowed:
```moss
fn main
    count = 1
    count = count + 1
```

### Functions

```moss
fn main
    emit {"type": "ready"}
```

With params:
```moss
fn make_message(kind, payload)
    return {
        "type": kind,
        "payload": payload
    }
```

### Literals

```moss
"hello"
123
12.5
true
false
null
```

### Arrays

```moss
[1, 2, 3]
["a", "b"]
```

### Objects

Keys must be strings in v0:
```moss
{
    "type": "ready",
    "ok": true,
    "count": 3
}
```

### Function calls

```moss
msg = make_message("ready", {"ok": true})
emit msg
```

### Operators

```
+  -  *  /
== !=
>  >=  <  <=
and  or  not
```

`+` supports `number + number` and `string + string`. No implicit coercion.

### Control flow

```moss
fn status(code)
    if code == 200
        return "ok"
    else if code == 404
        return "missing"
    else
        return "unknown"
```

---

## Builtins

### `emit(value)`

Wraps `value` in a PGAP envelope and writes one JSON line to stdout.

```moss
emit {"type": "ready", "payload": {"name": "demo"}}
```

stdout:
```json
{"protocol":"pgap/1","type":"ready","id":null,"payload":{"name":"demo"},"error":null}
```

The PGAP envelope is always:
```json
{
  "protocol": "pgap/1",
  "type":     "<from value>",
  "id":       null,
  "payload":  "<from value, or null>",
  "error":    null
}
```

`emit` reads `type` and `payload` from the object you pass. All other envelope fields are injected automatically.

Rules:
- Always compact JSON
- Always appends a newline
- If the value cannot be encoded, exits with code 1

### `fail(message)`

Emits a PGAP error envelope and exits with code 1.

```moss
fail("bad input")
```

stdout:
```json
{"protocol":"pgap/1","type":"error","id":null,"payload":null,"error":{"message":"bad input"}}
```

### `print(value)`

Plain string output for debugging. Not protocol-safe.

```moss
print("hello")
```

### `json(value)`

Returns the JSON string of a value without emitting.

```moss
text = json({"ok": true})
```

---

## Example programs

### Ready message

```moss
fn main
    emit {
        "type": "ready",
        "payload": {
            "service": "demo"
        }
    }
```

### Ping / pong

```moss
fn main
    emit {
        "type": "pong",
        "payload": {
            "time": 123
        }
    }
```

### Conditional response

```moss
fn main
    ok = true

    if ok
        emit {"type": "ready"}
    else
        fail("not ready")
```

### Using a helper function

```moss
fn message(kind, payload)
    return {
        "type": kind,
        "payload": payload
    }

fn main
    emit message("ready", {"service": "demo"})
```

---

## Compiler

```sh
moss build app.moss        # compile to binary
moss run app.moss          # compile and run
moss build app.moss --emit rust   # output Rust source
```

Moss compiles to Rust using `serde_json`. The generated output is readable and minimal.

Example — this Moss:
```moss
fn main
    emit {"type": "ready"}
```

Generates this Rust:
```rust
fn main() {
    let value = serde_json::json!({
        "protocol": "pgap/1",
        "type": "ready",
        "id": serde_json::Value::Null,
        "payload": serde_json::Value::Null,
        "error": serde_json::Value::Null,
    });
    println!("{}", value);
}
```

---

## Errors

Compile-time:
```
error: unknown function 'make_msg'
 --> app.moss:4:11
```

Runtime:
```
error: emit failed — value is not an object
 --> app.moss:2:5
```

---

## Grammar (minimal sketch)

```
program      := statement*
statement    := let_decl | fn_decl | expr_stmt | return_stmt | emit_stmt
let_decl     := "let" IDENT "=" expr
fn_decl      := "fn" IDENT params? NEWLINE block
params       := "(" ident_list? ")"
block        := INDENT statement+ DEDENT
return_stmt  := "return" expr?
emit_stmt    := "emit" expr
expr         := literal | IDENT | call | object | array | binary | if_expr | assignment
call         := IDENT "(" arg_list? ")"
object       := "{" pair_list? "}"
array        := "[" expr_list? "]"
binary       := expr op expr
op           := "+" | "-" | "*" | "/" | "==" | "!=" | ">" | ">=" | "<" | "<=" | "and" | "or"
```

---

## Implementation order

**Phase 1**
- Tokenizer
- Indentation-aware parser (indent/dedent)
- AST nodes
- Object/array/string/number/bool/null literals
- `fn main` + `emit`

**Phase 2**
- Function declarations and calls
- Local variables and reassignment
- `return`
- `if / else if / else`

**Phase 3**
- `--emit rust` mode
- `fail` builtin
- Nicer error messages with source locations

**Phase 4**
- Loops
- PGAP stdlib helpers (correlation IDs, message builders)
- LSP / syntax highlighting

---

## Type model

v0 is dynamically typed at the source level. All values map to `serde_json::Value` in generated Rust. No type annotations in source syntax.

Internal value kinds: `String`, `Number`, `Bool`, `Null`, `Array`, `Object`.

---

## Non-goals (v0)

- No optimizer
- No type checker
- No async
- No imports
- No classes
- No WASM target (yet)
