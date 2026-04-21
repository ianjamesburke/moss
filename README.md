# Moss

A small language that reads like English and compiles to Rust.

Moss is designed so a non-coder can learn it in a day. You write what you mean, and Moss handles the rest — no punctuation puzzles, no jargon, no compiler errors that read like machine code.

```moss
fn main
    emit
        type: ready
        payload:
            service: "demo"
            ok: true
```

Running this prints one line of JSON:
```json
{"type":"ready","payload":{"service":"demo","ok":true}}
```

---

## The rules of Moss

**One page.** The whole language fits on this page.

**One day.** You can learn it in an afternoon.

**One way.** There is exactly one way to write each thing. No shortcuts, no alternate forms.

**Fail first.** If something is wrong, Moss tells you immediately and stops. One error at a time, in plain English.

**Never make the writer feel dumb.** Every error is phrased so a 12-year-old can read it once and know what to do.

---

## Syntax

### Comments

```moss
# this is a comment
```

### Variables

Just assign a name to a value. No keyword.

```moss
name = "ian"
count = 3
active = true
```

Assigning an existing name updates it:
```moss
count = count + 1
```

### Strings

```moss
greeting = "hello, world"
```

Put values into strings with `{name}`:
```moss
message = "count is {count}"
```

You can put anything inside `{}` — numbers, booleans, other variables. Moss converts them for you.

### Numbers

```moss
port = 8080
ratio = 0.75
```

### Booleans

```moss
active = true
done = false
```

### Lists

Short lists on one line:
```moss
tags = ["fast", "simple", "clear"]
```

Long lists as indented items:
```moss
steps =
    - "connect"
    - "authenticate"
    - "listen"
```

### Records (key/value data)

Indented key-value pairs. No braces, no quoted keys.

```moss
config =
    host: "localhost"
    port: 8080
    debug: true
```

Records can nest:
```moss
response =
    type: ready
    payload:
        service: "demo"
        version: "1.0"
```

If you need to pass a record to a function, give it a name first. That makes your code easier to read.

### Functions

```moss
fn greet(name)
    return "hello, {name}"
```

Functions without parameters skip the parentheses:
```moss
fn title
    return "Moss Program"
```

### Returning values

```moss
fn answer
    return 42
```

You can return early:
```moss
fn check(value)
    if value == ""
        return false
    return true
```

### If, else if, else

```moss
fn label(code)
    if code == 200
        return "ok"
    else if code == 404
        return "missing"
    else
        return "unknown"
```

### Math

```
+  -  *  /
```

`+` also joins strings. If either side is a string, Moss turns the other side into a string automatically:
```moss
message = "count: " + count
# if count is 3, message becomes "count: 3"
```

### Comparing

```
==  !=  >  >=  <  <=
```

### Logic

Words, not symbols:
```moss
if ready and count > 0
    emit type: go

if not done
    emit type: waiting
```

Use parentheses when mixing `and` / `or` — Moss will ask you to, if you don't.

---

## The two things Moss does

### `emit`

Sends a value out as JSON.

```moss
fn main
    emit
        type: ready
        ok: true
```

Output:
```json
{"type":"ready","ok":true}
```

### `print`

Prints plain text. For trying things out.

Wait — that's a second way to output. Moss only has `emit`. Use `emit` with a string if you want to see something:

```moss
fn main
    emit "hello, world"
```

Output:
```json
"hello, world"
```

One output, one rule. Simpler.

---

## How Moss runs your code

Moss uses Rust underneath, but you don't need to know Rust to use Moss.

Two commands:

```sh
moss run hello.moss
```
Runs your program right now. Feels instant. Moss translates your code into Rust in the background, compiles it, and runs it. You never see the Rust.

```sh
moss build hello.moss
```
Creates a real program file you can share with anyone. It runs on its own — they don't need Moss installed.

One-way relationship: Moss is the source, Rust is the output. You write Moss, Moss makes Rust, Rust becomes a program. You never write Rust yourself, and Rust code can't come back into Moss.

If you're curious, you can see the Rust Moss generated:
```sh
moss build hello.moss --show-rust
```
This is a great way to start learning Rust later, if you want. But you never need to.

---

## Error messages

Moss errors look like a friend explaining what went wrong. No jargon. No codes. No symbols pointing at characters. Just: the filename, the line of code, and one sentence.

**Mistyped a function name:**
```
hello.moss, line 6

    emit greet("ian")

You're calling "greet" but there's no function named "greet" in this file.
Check the spelling, or add it above.
```

**Used a variable before creating it:**
```
hello.moss, line 4

    message = "count: " + count

Moss doesn't know what "count" is yet.
Did you forget to create it above?
```

**Two functions with the same name:**
```
hello.moss, line 7

    fn greet(name)
    fn greet(other)

You have two functions called "greet".
Rename one, or delete the one you don't need.
```

**Inconsistent indentation:**
```
hello.moss, line 9

        port: 8080
    debug: true

The indentation changed partway through this block.
Line 8 uses 8 spaces, but line 9 uses 4 — pick one.
```

**Ambiguous logic:**
```
hello.moss, line 5

    if ready and count > 0 or retry

Moss isn't sure which part to check first.
Try putting parentheses around the part you mean,
like: (ready and count > 0) or retry
```

**No `main` function:**
```
hello.moss

Every Moss program needs a function called "main".
Add one like this:

    fn main
        emit "hello"
```

One error at a time. Fix it, run again. Moss never dumps a list of problems at you.

---

## Example programs

### Hello

```moss
fn main
    emit "hello, world"
```

### A ready message

```moss
fn main
    emit
        type: ready
        ok: true
```

### Using a variable

```moss
service = "demo"

fn main
    emit
        type: ready
        payload:
            service: service
```

### A helper function

```moss
fn message(kind, data)
    return
        type: kind
        payload: data

fn main
    info =
        service: "demo"
    emit message("ready", info)
```

### Making decisions

```moss
fn respond(code)
    if code == 200
        emit type: success
    else if code == 404
        emit type: not_found
    else
        emit
            type: error
            message: "unexpected status: {code}"

fn main
    respond(200)
```

### Validating input

```moss
fn is_valid(name)
    return not name == ""

fn greet(name)
    if not is_valid(name)
        return "name is required"
    return "hello, {name}"

fn main
    emit greet("ian")
```

### Building a response from parts

```moss
version = "1.0"

fn make_response(data)
    return
        type: success
        version: version
        payload: data

fn main
    info =
        service: "demo"
        ready: true
    emit make_response(info)
```

### Using lists

```moss
fn main
    tags = ["fast", "simple", "clear"]
    emit
        type: info
        tags: tags
        count: 3
```

---

## What you can't do yet (coming later)

- **Loops.** For v1. `retry` is reserved for loop control when it lands.
- **Multiple files.** For v1. Right now, one file per program.
- **Reading input.** For v1. Programs only output for now.
- **Custom error handling.** For v1. Right now, if something breaks, the program stops.

---

## What Moss is not

- Not a systems language
- Not for building apps with screens
- Not object-oriented (no classes)
- Not for math-heavy work
- Not a shell replacement

Moss is for: writing small programs that take input, make a decision, and emit structured output. Think of it as the language for the middle of a pipeline.

---

## Getting Moss

```sh
brew install moss
```

Then:
```sh
moss run hello.moss
```

That's it. No Rust installation, no configuration, no project setup.

---

## Under the hood

Moss compiles to readable Rust using `serde_json`. The compiler is written in Rust and published to crates.io as `moss-lang`. The CLI tool is named `moss`.

```sh
cargo install moss-lang   # if you'd rather install from source
```

---

## For the curious: how `emit` works

When you write:
```moss
emit
    type: ready
    ok: true
```

Moss generates:
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

Run that Rust and you get:
```json
{"type":"ready","ok":true}
```

You never see this Rust unless you ask. But it's there — readable, ordinary, and a stepping-stone if you ever want to learn Rust proper.
