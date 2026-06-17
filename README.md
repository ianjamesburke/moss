<div align="center">

<pre>
<font color="#2f8f46">      vvv        vv                 vv        vvv
  vvvv\|/vvvv   \|/   .-~~~~~~~~-.   \|/   vvvv\|/vvvv
 vv\|/vvvv\|/vv      /  <b>M O S S</b>   \      vv\|/vvvv\|/vv
   `~~~~~~\|/~~~~~._/              \_.~~~~~\|/~~~~~~'
          \|/        .-..-..-..-.        \|/
     ~ ~ ~ ~ ~ ~ ~  /_/\/_/\/\_\  ~ ~ ~ ~ ~ ~ ~
   ~ ~ ~ ~ ~ ~ ~ ~ /_/\/_/\/\_\_\ ~ ~ ~ ~ ~ ~ ~ ~
      ||  ||       '~~~~~~~~~~~~'       ||  ||
      ||  ||     .  .  .    .  .       ||  ||
   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~</font>
</pre>

</div>

A small language that reads like English and compiles to Rust.

Moss is designed so a non-coder can learn it in a day. You write what you mean, and Moss handles the rest — no punctuation puzzles, no jargon, no compiler errors that read like machine code.

```moss
fn main
    output
        type: "ready"
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
    type: "ready"
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
    output type: "go"

if not done
    output type: "waiting"
```

Use parentheses when mixing `and` / `or` — Moss will ask you to, if you don't.

### Loops

Go through every item in a list:
```moss
for tag in tags
    output tag
```

Count from one number to another:
```moss
for n in 1 to 10
    output n
```

That's both kinds of loop in Moss. No other forms.

**`stop`** exits the loop early. **`skip`** jumps to the next item.

```moss
for code in codes
    if code == 0
        skip
    if code == 999
        stop
    output code
```

### Working with lists

Get an item by its position (starting at 1):
```moss
first = tags[1]
second = tags[2]
```

Count the items in a list:
```moss
count = length(tags)
```

That's it. If you need more, use a `for` loop.

---

## The two things Moss does

### `output`

Sends a value out as JSON.

```moss
fn main
    output
        type: "ready"
        ok: true
```

Output:
```json
{"type":"ready","ok":true}
```

### `print`

Prints plain text. For trying things out.

Wait — that's a second way to output. Moss only has `output`. Use `output` with a string if you want to see something:

```moss
fn main
    output "hello, world"
```

Output:
```json
"hello, world"
```

One output, one rule. Simpler.

### `input`

Reads JSON piped in on stdin. Use dot access to reach into it.

```moss
fn main
    output
        message: "hello, {input.name}"
        count: input.count
```

```sh
echo '{"name":"ada","count":3}' | moss run greet.moss
```

```json
{"message":"hello, ada","count":3}
```

If nothing is piped in, `input` is `null`. Programs can be used standalone or as stages in a pipeline.

```sh
moss run source.moss | moss run transform.moss | moss run sink.moss
```

---

## How Moss runs your code

Moss uses Rust underneath, but you don't need to know Rust to use Moss.

Useful commands:

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
moss show-rust hello.moss
```
This is a great way to start learning Rust later, if you want. But you never need to.

To update a git-installed copy:
```sh
moss update
```

---

## Error messages

Moss errors look like a friend explaining what went wrong. No jargon. No codes. No symbols pointing at characters. Just: the filename, the line of code, and one sentence.

**Mistyped a function name:**
```
hello.moss, line 6

    output greet("ian")

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
        output "hello"
```

One error at a time. Fix it, run again. Moss never dumps a list of problems at you.

---

## Example programs

### Hello

```moss
fn main
    output "hello, world"
```

### A ready message

```moss
fn main
    output
        type: "ready"
        ok: true
```

### Using a variable

```moss
service = "demo"

fn main
    output
        type: "ready"
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
    output message("ready", info)
```

### Making decisions

```moss
fn respond(code)
    if code == 200
        output type: "success"
    else if code == 404
        output type: "not_found"
    else
        output
            type: "error"
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
    output greet("ian")
```

### Building a response from parts

```moss
version = "1.0"

fn make_response(data)
    return
        type: "success"
        version: version
        payload: data

fn main
    info =
        service: "demo"
        ready: true
    output make_response(info)
```

### Using lists

```moss
fn main
    tags = ["fast", "simple", "clear"]
    output
        type: "info"
        tags: tags
        count: length(tags)
```

### Looping over a list

```moss
fn main
    tags = ["fast", "simple", "clear"]
    for tag in tags
        output
            type: "tag_found"
            name: tag
```

### Counting with a range

```moss
fn main
    for n in 1 to 5
        output
            type: "tick"
            number: n
```

### Skipping and stopping

```moss
fn main
    codes = [200, 0, 404, 999, 500]
    for code in codes
        if code == 0
            skip
        if code == 999
            stop
        output
            type: code
            value: code
```

---

## What you can't do yet (coming later)

- **Multiple files.** For v1. Right now, one file per program.
- **Custom error handling.** For v1. Right now, if something breaks, the program stops.
- **List helpers** like `map`, `filter`, `first`, `last`. For v1. In v0, use a `for` loop.

---

## What Moss is not

- Not a systems language
- Not for building apps with screens
- Not object-oriented (no classes)
- Not for math-heavy work
- Not a shell replacement

Moss is for: writing small programs that take input, make a decision, and produce structured output. Think of it as the language for the middle of a pipeline.

---

## Getting Moss

```sh
curl -fsSL https://raw.githubusercontent.com/ianjamesburke/moss/main/install.sh | bash
```

Then:
```sh
moss run hello.moss
```

The installer clones Moss to `~/.moss/src` and links `moss` into `~/.local/bin`.
It checks for Python 3 and Rust before installing.
Homebrew packaging is not wired up in this repo yet.

---

## Under the hood

Moss compiles to readable Rust using `serde_json`. The compiler is the Python script at `compiler/moss.py`; generated programs build against the Rust runtime template under `runtime/`.

---

## For the curious: how `output` works

When you write:
```moss
output
    type: "ready"
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
