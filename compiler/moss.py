#!/usr/bin/env python3
"""
Moss compiler — v0 runnable subset.

Source (.moss) -> AST -> Rust -> cargo run.

Supports:
- fn main (entry point)
- Variables with assignment (top-level and inside main)
- emit <value>
- Records (indented key: value blocks, no braces)
- Lists (inline [a, b, c])
- Strings with {name} interpolation
- Numbers, booleans, null
- Comments (#)

Not yet supported in this v0 runnable subset:
- Functions with parameters, return
- if / else / for / loops / stop / skip
- Arithmetic, comparison, logic operators
- Indexing, length()
"""

import sys
import os
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
RUNTIME_DIR = REPO_ROOT / "runtime"


# ----- ERRORS -------------------------------------------------------------

class MossError(Exception):
    def __init__(self, line_no, source_lines, message, filename):
        self.line_no = line_no
        self.source_lines = source_lines
        self.message = message
        self.filename = filename

    def format(self):
        out = [f"\n{self.filename}, line {self.line_no}", ""]
        if 0 < self.line_no <= len(self.source_lines):
            out.append(f"    {self.source_lines[self.line_no - 1]}")
            out.append("")
        out.append(self.message)
        out.append("")
        return "\n".join(out)


# ----- TOKENIZER ----------------------------------------------------------

# Produces a stream of logical lines with indentation levels.
# Each entry: (line_no, indent_spaces, content_tokens)

def tokenize_line(content, line_no, source_lines, filename):
    """Tokenize the content of a single line (after indentation stripped)."""
    tokens = []
    i = 0
    while i < len(content):
        c = content[i]
        if c == " " or c == "\t":
            i += 1
        elif c == "#":
            break  # comment — rest of line ignored
        elif c == '"':
            # string literal (may have {interp})
            end = i + 1
            while end < len(content) and content[end] != '"':
                if content[end] == "\\" and end + 1 < len(content):
                    end += 2
                else:
                    end += 1
            if end >= len(content):
                raise MossError(line_no, source_lines,
                    "This string is missing its closing quote.", filename)
            tokens.append(("STRING", content[i+1:end]))
            i = end + 1
        elif c.isdigit() or (c == "-" and i + 1 < len(content) and content[i+1].isdigit()):
            start = i
            if c == "-":
                i += 1
            while i < len(content) and (content[i].isdigit() or content[i] == "."):
                i += 1
            tokens.append(("NUMBER", content[start:i]))
        elif c.isalpha() or c == "_":
            start = i
            while i < len(content) and (content[i].isalnum() or content[i] == "_"):
                i += 1
            # extend for dotted access like input.user.name
            while (
                i + 1 < len(content)
                and content[i] == "."
                and (content[i+1].isalpha() or content[i+1] == "_")
            ):
                i += 1
                while i < len(content) and (content[i].isalnum() or content[i] == "_"):
                    i += 1
            word = content[start:i]
            if word in ("true", "false"):
                tokens.append(("BOOL", word))
            elif word == "null":
                tokens.append(("NULL", word))
            elif word in ("fn", "output", "return", "if", "else", "for", "in", "to",
                          "and", "or", "not", "stop", "skip"):
                tokens.append(("KEYWORD", word))
            else:
                tokens.append(("IDENT", word))
        elif c in "()[]{},:+-*/":
            tokens.append(("SYM", c))
            i += 1
        elif c == "=":
            tokens.append(("SYM", "="))
            i += 1
        else:
            raise MossError(line_no, source_lines,
                f"Moss doesn't understand the character '{c}' here.", filename)
    return tokens


def read_logical_lines(source, filename):
    """Split source into (line_no, indent, tokens). Blank and comment-only lines skipped."""
    source_lines = source.splitlines()
    result = []
    for idx, raw in enumerate(source_lines):
        line_no = idx + 1
        # strip trailing whitespace
        line = raw.rstrip()
        if not line:
            continue
        # measure indent
        indent = 0
        while indent < len(line) and line[indent] == " ":
            indent += 1
        if indent < len(line) and line[indent] == "\t":
            raise MossError(line_no, source_lines,
                "Moss uses spaces for indentation, not tabs. Replace the tab with spaces.", filename)
        content = line[indent:]
        if not content or content.lstrip().startswith("#"):
            continue
        toks = tokenize_line(content, line_no, source_lines, filename)
        if not toks:
            continue
        result.append((line_no, indent, toks))
    return result, source_lines


# ----- PARSER -------------------------------------------------------------

# AST node shapes (plain dicts for simplicity):
# {"kind": "program", "stmts": [...]}
# {"kind": "fn", "name": str, "body": [stmts]}
# {"kind": "assign", "name": str, "value": expr}
# {"kind": "output", "value": expr}
# {"kind": "record", "pairs": [(key, value), ...]}
# {"kind": "list", "items": [expr, ...]}
# {"kind": "string", "parts": [("lit", str) | ("var", name)]}
# {"kind": "number", "value": str}
# {"kind": "bool", "value": bool}
# {"kind": "null"}
# {"kind": "var", "name": str}


class Parser:
    def __init__(self, lines, source_lines, filename):
        self.lines = lines
        self.source_lines = source_lines
        self.filename = filename
        self.pos = 0

    def peek(self):
        if self.pos >= len(self.lines):
            return None
        return self.lines[self.pos]

    def advance(self):
        line = self.lines[self.pos]
        self.pos += 1
        return line

    def error(self, line_no, message):
        raise MossError(line_no, self.source_lines, message, self.filename)

    def parse_program(self):
        stmts = []
        while self.peek() is not None:
            line_no, indent, toks = self.peek()
            if indent != 0:
                self.error(line_no, "This line is indented but it shouldn't be — top-level code starts at the left margin.")
            stmts.append(self.parse_top_stmt())
        return {"kind": "program", "stmts": stmts}

    def parse_top_stmt(self):
        line_no, indent, toks = self.peek()
        # fn NAME
        if toks[0] == ("KEYWORD", "fn"):
            if len(toks) < 2 or toks[1][0] != "IDENT":
                self.error(line_no, "A function needs a name after 'fn', like: fn main")
            name = toks[1][1]
            if len(toks) > 2:
                # parens allowed for no-op if empty; params not supported yet
                if toks[2:] == [("SYM", "("), ("SYM", ")")]:
                    pass
                else:
                    self.error(line_no, "Functions with parameters aren't supported yet in this version. Use 'fn main' with no parentheses.")
            self.advance()
            body = self.parse_block(indent)
            return {"kind": "fn", "name": name, "body": body, "line_no": line_no}
        # IDENT = value
        if toks[0][0] == "IDENT" and len(toks) >= 2 and toks[1] == ("SYM", "="):
            name = toks[0][1]
            return self.parse_assignment(line_no, indent, toks, name)
        self.error(line_no, "Moss expected a variable assignment (name = value) or a function definition (fn main) here.")

    def parse_block(self, parent_indent):
        """Parse statements more deeply indented than parent_indent."""
        stmts = []
        first = self.peek()
        if first is None:
            return stmts
        first_line, first_indent, _ = first
        if first_indent <= parent_indent:
            return stmts  # empty block
        block_indent = first_indent
        while self.peek() is not None:
            line_no, indent, toks = self.peek()
            if indent < block_indent:
                break
            if indent > block_indent:
                self.error(line_no,
                    f"The indentation jumped from {block_indent} spaces to {indent} — "
                    f"each level should go in by the same amount.")
            stmts.append(self.parse_block_stmt(block_indent))
        return stmts

    def parse_block_stmt(self, block_indent):
        line_no, indent, toks = self.peek()
        # emit
        if toks[0] == ("KEYWORD", "output"):
            self.advance()
            rest = toks[1:]
            if rest:
                value = self.parse_inline_expr(line_no, rest)
            else:
                value = self.parse_indented_value(block_indent, line_no)
            return {"kind": "output", "value": value, "line_no": line_no}
        # name = value
        if toks[0][0] == "IDENT" and len(toks) >= 2 and toks[1] == ("SYM", "="):
            name = toks[0][1]
            return self.parse_assignment(line_no, indent, toks, name)
        self.error(line_no, "Inside a function, Moss expected either an 'output' or a variable assignment (name = value).")

    def parse_assignment(self, line_no, indent, toks, name):
        rest = toks[2:]  # after name and =
        self.advance()
        if rest:
            value = self.parse_inline_expr(line_no, rest)
        else:
            value = self.parse_indented_value(indent, line_no)
        return {"kind": "assign", "name": name, "value": value, "line_no": line_no}

    def parse_indented_value(self, parent_indent, parent_line_no):
        """Parse a record (key: value block) starting at the next indented line."""
        first = self.peek()
        if first is None:
            self.error(parent_line_no, "Moss expected a value here — either on the same line, or on indented lines below.")
        first_line, first_indent, _ = first
        if first_indent <= parent_indent:
            self.error(parent_line_no, "Moss expected a value here — either on the same line, or on indented lines below.")
        block_indent = first_indent
        pairs = []
        while self.peek() is not None:
            line_no, indent, toks = self.peek()
            if indent < block_indent:
                break
            if indent > block_indent:
                self.error(line_no,
                    f"The indentation jumped from {block_indent} spaces to {indent} — "
                    f"each level should go in by the same amount.")
            # expect: IDENT : [value]
            if len(toks) < 2 or toks[0][0] != "IDENT" or toks[1] != ("SYM", ":"):
                self.error(line_no, "Moss expected a 'key: value' line here. Keys are plain words like 'type' or 'name'.")
            key = toks[0][1]
            rest = toks[2:]
            self.advance()
            if rest:
                value = self.parse_inline_expr(line_no, rest)
            else:
                value = self.parse_indented_value(indent, line_no)
            pairs.append((key, value))
        return {"kind": "record", "pairs": pairs}

    def parse_inline_expr(self, line_no, toks):
        """Parse an inline expression from a list of tokens."""
        expr, rest = self._inline(toks, line_no)
        if rest:
            self.error(line_no, f"Moss found extra tokens it didn't expect at the end of this line.")
        return expr

    def _inline(self, toks, line_no):
        if not toks:
            self.error(line_no, "Moss expected a value here.")
        head = toks[0]
        if head[0] == "STRING":
            parts = parse_string_parts(head[1])
            return {"kind": "string", "parts": parts}, toks[1:]
        if head[0] == "NUMBER":
            return {"kind": "number", "value": head[1]}, toks[1:]
        if head[0] == "BOOL":
            return {"kind": "bool", "value": head[1] == "true"}, toks[1:]
        if head[0] == "NULL":
            return {"kind": "null"}, toks[1:]
        if head == ("SYM", "["):
            items = []
            rest = toks[1:]
            if rest and rest[0] == ("SYM", "]"):
                return {"kind": "list", "items": []}, rest[1:]
            while True:
                item, rest = self._inline(rest, line_no)
                items.append(item)
                if not rest:
                    self.error(line_no, "This list is missing its closing bracket ']'.")
                if rest[0] == ("SYM", ","):
                    rest = rest[1:]
                    continue
                if rest[0] == ("SYM", "]"):
                    return {"kind": "list", "items": items}, rest[1:]
                self.error(line_no, "Inside a list, Moss expected a comma ',' or a closing bracket ']'.")
        if head[0] == "IDENT":
            return {"kind": "var", "name": head[1]}, toks[1:]
        self.error(line_no, f"Moss didn't expect this here.")


def parse_string_parts(raw):
    """Parse 'hello {name} world' into [('lit','hello '), ('var','name'), ('lit',' world')]."""
    parts = []
    i = 0
    buf = ""
    while i < len(raw):
        c = raw[i]
        if c == "{":
            if i + 1 < len(raw) and raw[i+1] == "{":
                buf += "{"
                i += 2
                continue
            # find closing }
            end = raw.find("}", i + 1)
            if end == -1:
                # treat as literal
                buf += c
                i += 1
                continue
            if buf:
                parts.append(("lit", buf))
                buf = ""
            name = raw[i+1:end].strip()
            parts.append(("var", name))
            i = end + 1
        elif c == "\\" and i + 1 < len(raw):
            nxt = raw[i+1]
            esc = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt)
            buf += esc
            i += 2
        else:
            buf += c
            i += 1
    if buf:
        parts.append(("lit", buf))
    return parts


# ----- CODEGEN (Moss AST -> Rust) -----------------------------------------

RUNTIME_PREAMBLE = r"""
// Generated by Moss. Do not edit by hand.

#![allow(unused_imports, dead_code, unused_variables, unused_mut)]

use serde_json::{json, Value};
use std::io::{IsTerminal, Read};

fn moss_str(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        Value::Null => String::from(""),
        Value::Bool(b) => b.to_string(),
        Value::Number(n) => n.to_string(),
        _ => v.to_string(),
    }
}

fn moss_read_input() -> Value {
    if std::io::stdin().is_terminal() {
        return Value::Null;
    }
    let mut buf = String::new();
    if std::io::stdin().read_to_string(&mut buf).is_err() {
        return Value::Null;
    }
    if buf.trim().is_empty() {
        return Value::Null;
    }
    serde_json::from_str(&buf).unwrap_or(Value::Null)
}
"""


def escape_rust_string(s):
    return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\t", "\\t")


def gen_expr(node):
    """Generate Rust code that produces a serde_json::Value."""
    k = node["kind"]
    if k == "string":
        # compose via format! then wrap
        fmt = ""
        args = []
        for kind, val in node["parts"]:
            if kind == "lit":
                fmt += escape_rust_string(val).replace("{", "{{").replace("}", "}}")
            else:
                fmt += "{}"
                # val may be dotted like input.user.name
                parts = val.split(".")
                root = parts[0]
                rest = parts[1:]
                if rest:
                    pointer = "/" + "/".join(rest)
                    args.append(
                        f'moss_str(&{root}.pointer("{pointer}").cloned().unwrap_or(Value::Null))'
                    )
                else:
                    args.append(f'moss_str(&{val})')
        if args:
            return f'Value::String(format!("{fmt}", {", ".join(args)}))'
        return f'Value::String(String::from("{fmt}"))'
    if k == "number":
        v = node["value"]
        if "." in v:
            return f'json!({v}f64)'
        return f'json!({v}i64)'
    if k == "bool":
        return f'json!({"true" if node["value"] else "false"})'
    if k == "null":
        return "Value::Null"
    if k == "var":
        name = node["name"]
        parts = name.split(".")
        root = parts[0]
        rest = parts[1:]
        if rest:
            pointer = "/" + "/".join(rest)
            return f'{root}.pointer("{pointer}").cloned().unwrap_or(Value::Null)'
        return f'{root}.clone()'
    if k == "list":
        parts = [gen_expr(it) for it in node["items"]]
        return f'json!([{", ".join(parts)}])' if False else f'Value::Array(vec![{", ".join(parts)}])'
    if k == "record":
        lines = []
        for key, val in node["pairs"]:
            lines.append(f'    map.insert(String::from("{escape_rust_string(key)}"), {gen_expr(val)});')
        body = "\n".join(lines)
        return (
            "{\n"
            "    let mut map = serde_json::Map::new();\n"
            f"{body}\n"
            "    Value::Object(map)\n"
            "}"
        )
    raise RuntimeError(f"unknown expr kind: {k}")


def gen_block(stmts):
    out = []
    for s in stmts:
        k = s["kind"]
        if k == "assign":
            out.append(f'let {s["name"]}: Value = {gen_expr(s["value"])};')
        elif k == "output":
            out.append(f'{{ let _moss_v: Value = {gen_expr(s["value"])}; println!("{{}}", _moss_v); }}')
        else:
            raise RuntimeError(f"unknown block stmt kind: {k}")
    return "\n".join("    " + line for line in "\n".join(out).splitlines())


def compile_program(ast, filename, source_lines):
    # Collect top-level assigns and the main function.
    top_assigns = []
    main_fn = None
    seen_fn = set()
    for stmt in ast["stmts"]:
        if stmt["kind"] == "assign":
            top_assigns.append(stmt)
        elif stmt["kind"] == "fn":
            if stmt["name"] in seen_fn:
                raise MossError(stmt["line_no"], source_lines,
                    f"You have two functions called \"{stmt['name']}\". Rename one, or delete the one you don't need.", filename)
            seen_fn.add(stmt["name"])
            if stmt["name"] == "main":
                main_fn = stmt
        else:
            raise RuntimeError(f"unexpected top-level stmt: {stmt['kind']}")
    if main_fn is None:
        raise MossError(1, source_lines,
            "Every Moss program needs a function called \"main\". Add one like this:\n\n    fn main\n        emit \"hello\"", filename)

    # Generate the main function body with top-level assigns first, then main body.
    combined = top_assigns + main_fn["body"]
    body_code = gen_block(combined)

    rust = (
        RUNTIME_PREAMBLE
        + "\nfn main() {\n"
        + "    let input: Value = moss_read_input();\n"
        + body_code
        + "\n}\n"
    )
    return rust


# ----- DRIVER -------------------------------------------------------------

def usage():
    print("Moss — a small language that reads like English.\n")
    print("Commands:")
    print("  moss run FILE.moss        compile and run")
    print("  moss build FILE.moss      compile to a standalone binary")
    print("  moss show-rust FILE.moss  print the Rust Moss would generate")
    sys.exit(1)


def compile_source(path):
    source = Path(path).read_text()
    filename = os.path.basename(path)
    lines, source_lines = read_logical_lines(source, filename)
    parser = Parser(lines, source_lines, filename)
    ast = parser.parse_program()
    rust = compile_program(ast, filename, source_lines)
    return rust


def cmd_show_rust(path):
    try:
        print(compile_source(path))
    except MossError as e:
        print(e.format(), file=sys.stderr)
        sys.exit(1)


def _cargo_invoke(rust, subcommand):
    """Run `cargo <subcommand>` in a per-invocation temp workspace with shared target dir."""
    import tempfile, shutil
    target_dir = RUNTIME_DIR / "target"
    target_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="moss_") as tmp:
        pkg = Path(tmp)
        (pkg / "src").mkdir()
        shutil.copy2(RUNTIME_DIR / "Cargo.toml", pkg / "Cargo.toml")
        (pkg / "src" / "main.rs").write_text(rust)
        env = os.environ.copy()
        env["CARGO_TARGET_DIR"] = str(target_dir)
        r = subprocess.run(
            ["cargo", subcommand, "--quiet", "--release"],
            cwd=str(pkg),
            env=env,
        )
        return r.returncode, target_dir / "release" / "moss_run"


def _cache_dir():
    d = Path.home() / ".moss" / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_binary(rust):
    """Compile Moss-generated Rust to a cached binary, keyed by source hash.
    Returns a ready-to-exec path. Subsequent runs of the same source skip cargo entirely."""
    import hashlib, shutil
    h = hashlib.sha1(rust.encode()).hexdigest()[:16]
    bin_path = _cache_dir() / f"moss_{h}"
    if bin_path.exists():
        return bin_path
    code, built = _cargo_invoke(rust, "build")
    if code != 0:
        sys.exit(code)
    shutil.copy2(built, bin_path)
    os.chmod(bin_path, 0o755)
    return bin_path


def cmd_run(path):
    try:
        rust = compile_source(path)
    except MossError as e:
        print(e.format(), file=sys.stderr)
        sys.exit(1)
    bin_path = _ensure_binary(rust)
    os.execv(str(bin_path), [str(bin_path)])


def cmd_build(path):
    try:
        rust = compile_source(path)
    except MossError as e:
        print(e.format(), file=sys.stderr)
        sys.exit(1)
    import shutil
    bin_path = _ensure_binary(rust)
    out_path = Path.cwd() / Path(path).stem
    shutil.copy2(bin_path, out_path)
    print(f"built: {out_path}")


def main():
    if len(sys.argv) < 3:
        usage()
    cmd = sys.argv[1]
    path = sys.argv[2]
    if not os.path.exists(path):
        print(f"file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if cmd == "run":
        cmd_run(path)
    elif cmd == "build":
        cmd_build(path)
    elif cmd == "show-rust":
        cmd_show_rust(path)
    else:
        usage()


if __name__ == "__main__":
    main()
