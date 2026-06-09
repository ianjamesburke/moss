#!/usr/bin/env python3
"""
Moss compiler — v0 runnable subset.

Source (.moss) -> AST -> Rust -> cargo run.

Supports:
- fn main (entry point)
- fn name(param1, param2) — functions with parameters
- Variables with assignment (top-level and inside main)
- output <value>
- return expr — return a value from a function
- Records (indented key: value blocks, no braces)
- Lists (inline [a, b, c])
- Strings with {name} interpolation
- Numbers, booleans, null
- Comments (#)
- Arithmetic: +, -, *, /
- Comparisons: ==, !=, >, >=, <, <=
- Logic: and, or, not
- Control flow: if / else if / else
- Loops: for item in list, for n in 1 to 10, stop (break), skip (continue)
- Function calls: name(arg1, arg2)
- List indexing: list[n] (1-based)
- length(list) — built-in returning list length
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
            if i + 1 < len(content) and content[i+1] == "=":
                tokens.append(("SYM", "=="))
                i += 2
            else:
                tokens.append(("SYM", "="))
                i += 1
        elif c == "!":
            if i + 1 < len(content) and content[i+1] == "=":
                tokens.append(("SYM", "!="))
                i += 2
            else:
                raise MossError(line_no, source_lines,
                    "Moss doesn't understand '!' here. Did you mean 'not'?", filename)
        elif c in "<>":
            if i + 1 < len(content) and content[i+1] == "=":
                tokens.append(("SYM", c + "="))
                i += 2
            else:
                tokens.append(("SYM", c))
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
# {"kind": "binop", "op": str, "left": expr, "right": expr}
# {"kind": "for_in", "var": str, "iter": expr, "body": [stmts], "line_no": N}
# {"kind": "for_range", "var": str, "start": expr, "end": expr, "body": [stmts], "line_no": N}
# {"kind": "stop"}
# {"kind": "skip"}


class Parser:
    def __init__(self, lines, source_lines, filename):
        self.lines = lines
        self.source_lines = source_lines
        self.filename = filename
        self.pos = 0
        self.loop_depth = 0
        self.current_fn = None  # name of function being parsed, None = top-level

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
        # fn NAME  or  fn NAME(param, ...)
        if toks[0] == ("KEYWORD", "fn"):
            if len(toks) < 2 or toks[1][0] != "IDENT":
                self.error(line_no, "A function needs a name after 'fn', like: fn main")
            name = toks[1][1]
            params = []
            rest_toks = toks[2:]
            if rest_toks:
                if rest_toks[0] != ("SYM", "("):
                    self.error(line_no, "After a function name, Moss expected '(' for parameters or the body on the next line.")
                rest_toks = rest_toks[1:]  # skip (
                if rest_toks and rest_toks[0] == ("SYM", ")"):
                    rest_toks = rest_toks[1:]  # empty params
                else:
                    while True:
                        if not rest_toks or rest_toks[0][0] != "IDENT":
                            self.error(line_no, "Function parameters must be names, like: fn greet(name, age)")
                        params.append(rest_toks[0][1])
                        rest_toks = rest_toks[1:]
                        if not rest_toks:
                            self.error(line_no, "Function parameter list is missing its closing ')'.")
                        if rest_toks[0] == ("SYM", ")"):
                            rest_toks = rest_toks[1:]
                            break
                        if rest_toks[0] == ("SYM", ","):
                            rest_toks = rest_toks[1:]
                            continue
                        self.error(line_no, "In function parameters, Moss expected ',' or ')'. Got something else.")
                if rest_toks:
                    self.error(line_no, "Moss found unexpected tokens after the function parameter list.")
            prev_fn = self.current_fn
            self.current_fn = name
            self.advance()
            body = self.parse_block(indent)
            self.current_fn = prev_fn
            return {"kind": "fn", "name": name, "params": params, "body": body, "line_no": line_no}
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
        # output
        if toks[0] == ("KEYWORD", "output"):
            self.advance()
            rest = toks[1:]
            if rest:
                value = self.parse_inline_expr(line_no, rest)
            else:
                value = self.parse_indented_value(block_indent, line_no)
            return {"kind": "output", "value": value, "line_no": line_no}
        # if / else if / else
        if toks[0] == ("KEYWORD", "if"):
            return self.parse_if_stmt(line_no, indent, toks)
        # for IDENT in EXPR [to EXPR]
        if toks[0] == ("KEYWORD", "for"):
            return self.parse_for_stmt(line_no, indent, toks)
        # return
        if toks[0] == ("KEYWORD", "return"):
            if self.current_fn == "main":
                self.error(line_no, "'return' cannot be used inside 'main'. Use 'return' only in named functions.")
            if self.current_fn is None:
                self.error(line_no, "'return' can only be used inside a function body.")
            self.advance()
            rest = toks[1:]
            value = self.parse_inline_expr(line_no, rest) if rest else {"kind": "null"}
            return {"kind": "return", "value": value, "line_no": line_no}
        # stop / skip
        if toks[0] == ("KEYWORD", "stop"):
            if self.loop_depth == 0:
                self.error(line_no, "'stop' can only be used inside a loop.")
            if len(toks) > 1:
                self.error(line_no, "'stop' takes no arguments — it just stops the loop.")
            self.advance()
            return {"kind": "stop", "line_no": line_no}
        if toks[0] == ("KEYWORD", "skip"):
            if self.loop_depth == 0:
                self.error(line_no, "'skip' can only be used inside a loop.")
            if len(toks) > 1:
                self.error(line_no, "'skip' takes no arguments — it skips to the next iteration.")
            self.advance()
            return {"kind": "skip", "line_no": line_no}
        # name = value
        if toks[0][0] == "IDENT" and len(toks) >= 2 and toks[1] == ("SYM", "="):
            name = toks[0][1]
            return self.parse_assignment(line_no, indent, toks, name)
        self.error(line_no, "Inside a function, Moss expected either an 'output', 'if', 'for', 'stop', 'skip', or a variable assignment (name = value).")

    def parse_if_stmt(self, line_no, block_indent, toks):
        """Parse an if/else if/else chain starting at the current line."""
        # toks[0] == ("KEYWORD", "if")
        cond_toks = toks[1:]
        if not cond_toks:
            self.error(line_no, "An 'if' needs a condition after it, like: if x > 0")
        cond = self.parse_inline_expr(line_no, cond_toks)
        self.advance()  # consume the 'if ...' line
        body = self.parse_block(block_indent)
        if not body:
            self.error(line_no, "The 'if' block is empty — add at least one statement inside it.")

        branches = [{"cond": cond, "body": body}]
        else_body = None

        while self.peek() is not None:
            next_line_no, next_indent, next_toks = self.peek()
            if next_indent != block_indent:
                break
            if next_toks[0] != ("KEYWORD", "else"):
                break
            # else if <cond>  OR  bare else
            if len(next_toks) >= 2 and next_toks[1] == ("KEYWORD", "if"):
                ei_cond_toks = next_toks[2:]
                if not ei_cond_toks:
                    self.error(next_line_no, "An 'else if' needs a condition after it.")
                ei_cond = self.parse_inline_expr(next_line_no, ei_cond_toks)
                self.advance()  # consume 'else if ...' line
                ei_body = self.parse_block(block_indent)
                if not ei_body:
                    self.error(next_line_no, "The 'else if' block is empty.")
                branches.append({"cond": ei_cond, "body": ei_body})
            else:
                # bare else
                if len(next_toks) > 1:
                    self.error(next_line_no, "'else' should be on its own line with no extra tokens.")
                self.advance()  # consume 'else' line
                else_body = self.parse_block(block_indent)
                if not else_body:
                    self.error(next_line_no, "The 'else' block is empty.")
                break  # nothing can follow bare else

        return {"kind": "if", "branches": branches, "else_body": else_body, "line_no": line_no}

    def parse_for_stmt(self, line_no, block_indent, toks):
        """Parse 'for IDENT in EXPR' or 'for IDENT in EXPR to EXPR'."""
        # toks[0] == ("KEYWORD", "for")
        if len(toks) < 2 or toks[1][0] != "IDENT":
            self.error(line_no, "A 'for' loop needs a variable name, like: for item in my_list")
        if len(toks) < 3 or toks[2] != ("KEYWORD", "in"):
            self.error(line_no, "A 'for' loop needs 'in' after the variable, like: for item in my_list")
        var = toks[1][1]
        rest = toks[3:]
        if not rest:
            self.error(line_no, "A 'for' loop needs something to iterate over after 'in'.")
        # Try to split on 'to' keyword at the top level (not inside parens/brackets).
        # We parse the first expr and then check if the remaining tokens start with 'to'.
        start_expr, remaining = self._parse_or(rest, line_no)
        self.advance()  # consume the 'for ...' line
        self.loop_depth += 1
        body = self.parse_block(block_indent)
        self.loop_depth -= 1
        if not body:
            self.error(line_no, "The 'for' loop body is empty — add at least one statement inside it.")
        if remaining and remaining[0] == ("KEYWORD", "to"):
            # range loop: for n in START to END
            end_toks = remaining[1:]
            if not end_toks:
                self.error(line_no, "A range loop needs an end value after 'to', like: for n in 1 to 10")
            end_expr, leftover = self._parse_or(end_toks, line_no)
            if leftover:
                self.error(line_no, "Moss found extra tokens after the range end value.")
            return {"kind": "for_range", "var": var, "start": start_expr, "end": end_expr,
                    "body": body, "line_no": line_no}
        if remaining:
            self.error(line_no, "Moss found extra tokens after the iterable expression.")
        return {"kind": "for_in", "var": var, "iter": start_expr, "body": body, "line_no": line_no}

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
        expr, rest = self._parse_or(toks, line_no)
        if rest:
            self.error(line_no, "Moss found extra tokens it didn't expect at the end of this line.")
        return expr

    # Precedence (lowest to highest):
    # 1. or
    # 2. and
    # 3. not (unary)
    # 4. comparisons: ==, !=, >, >=, <, <=
    # 5. + -
    # 6. * /
    # 7. atoms

    def _parse_or(self, toks, line_no):
        """Lowest precedence: or."""
        left, toks = self._parse_and(toks, line_no)
        while toks and toks[0] == ("KEYWORD", "or"):
            right, toks = self._parse_and(toks[1:], line_no)
            left = {"kind": "binop", "op": "or", "left": left, "right": right}
        return left, toks

    def _parse_and(self, toks, line_no):
        """and."""
        left, toks = self._parse_not(toks, line_no)
        while toks and toks[0] == ("KEYWORD", "and"):
            right, toks = self._parse_not(toks[1:], line_no)
            left = {"kind": "binop", "op": "and", "left": left, "right": right}
        return left, toks

    def _parse_not(self, toks, line_no):
        """Unary not."""
        if toks and toks[0] == ("KEYWORD", "not"):
            operand, rest = self._parse_not(toks[1:], line_no)
            return {"kind": "unop", "op": "not", "operand": operand}, rest
        return self._parse_comparison(toks, line_no)

    _CMP_OPS = {("SYM", "=="): "==", ("SYM", "!="): "!=",
                ("SYM", ">"): ">",   ("SYM", ">="): ">=",
                ("SYM", "<"): "<",   ("SYM", "<="): "<="}

    def _parse_comparison(self, toks, line_no):
        """Non-associative comparisons."""
        left, toks = self._parse_add(toks, line_no)
        if toks and toks[0] in self._CMP_OPS:
            op = self._CMP_OPS[toks[0]]
            right, toks = self._parse_add(toks[1:], line_no)
            # check for chained comparison and reject it
            if toks and toks[0] in self._CMP_OPS:
                self.error(line_no,
                    "Chained comparisons like 'a < b < c' aren't supported. "
                    "Use 'a < b and b < c' instead.")
            return {"kind": "binop", "op": op, "left": left, "right": right}, toks
        return left, toks

    def _parse_add(self, toks, line_no):
        """+ and -."""
        left, toks = self._parse_term(toks, line_no)
        while toks and toks[0] in (("SYM", "+"), ("SYM", "-")):
            op = toks[0][1]
            right, toks = self._parse_term(toks[1:], line_no)
            left = {"kind": "binop", "op": op, "left": left, "right": right}
        return left, toks

    def _parse_term(self, toks, line_no):
        """* and /."""
        left, toks = self._parse_primary(toks, line_no)
        while toks and toks[0] in (("SYM", "*"), ("SYM", "/")):
            op = toks[0][1]
            right, toks = self._parse_primary(toks[1:], line_no)
            left = {"kind": "binop", "op": op, "left": left, "right": right}
        return left, toks

    def _parse_primary(self, toks, line_no):
        """Atoms: literals, variables, lists, parenthesised expressions."""
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
        if head == ("SYM", "("):
            expr, rest = self._parse_or(toks[1:], line_no)
            if not rest or rest[0] != ("SYM", ")"):
                self.error(line_no, "Moss expected a closing parenthesis ')' here.")
            return expr, rest[1:]
        if head == ("SYM", "["):
            items = []
            rest = toks[1:]
            if rest and rest[0] == ("SYM", "]"):
                return {"kind": "list", "items": []}, rest[1:]
            while True:
                item, rest = self._parse_or(rest, line_no)
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
            name = head[1]
            rest = toks[1:]
            # function call: name(arg1, arg2, ...)
            if rest and rest[0] == ("SYM", "("):
                args = []
                rest = rest[1:]  # skip (
                if rest and rest[0] == ("SYM", ")"):
                    rest = rest[1:]  # no args
                else:
                    while True:
                        arg, rest = self._parse_or(rest, line_no)
                        args.append(arg)
                        if not rest:
                            self.error(line_no, "Function call is missing its closing ')'.")
                        if rest[0] == ("SYM", ")"):
                            rest = rest[1:]
                            break
                        if rest[0] == ("SYM", ","):
                            rest = rest[1:]
                            continue
                        self.error(line_no, "In a function call, Moss expected ',' or ')'. Got something else.")
                return {"kind": "call", "name": name, "args": args, "line_no": line_no}, rest
            # variable (possibly dotted), optionally indexed with [n]
            node = {"kind": "var", "name": name}
            if rest and rest[0] == ("SYM", "["):
                rest = rest[1:]  # skip [
                idx_expr, rest = self._parse_or(rest, line_no)
                if not rest or rest[0] != ("SYM", "]"):
                    self.error(line_no, "List indexing is missing its closing ']'.")
                rest = rest[1:]  # skip ]
                node = {"kind": "index", "list": node, "idx": idx_expr}
            return node, rest
        self.error(line_no, "Moss didn't expect this here.")


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

#![allow(unused_imports, dead_code, unused_variables, unused_mut, unreachable_code)]

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

fn moss_add(a: &Value, b: &Value) -> Value {
    match (a, b) {
        (Value::Number(n1), Value::Number(n2)) => {
            if n1.is_f64() || n2.is_f64() {
                json!(n1.as_f64().unwrap() + n2.as_f64().unwrap())
            } else {
                match n1.as_i64().zip(n2.as_i64()) {
                    Some((a, b)) => match a.checked_add(b) {
                        Some(r) => json!(r),
                        None => json!(n1.as_f64().unwrap() + n2.as_f64().unwrap()),
                    },
                    None => json!(n1.as_f64().unwrap() + n2.as_f64().unwrap()),
                }
            }
        }
        _ => Value::String(format!("{}{}", moss_str(a), moss_str(b))),
    }
}

fn moss_sub(a: &Value, b: &Value) -> Value {
    match (a, b) {
        (Value::Number(n1), Value::Number(n2)) => {
            if n1.is_f64() || n2.is_f64() {
                json!(n1.as_f64().unwrap() - n2.as_f64().unwrap())
            } else {
                match n1.as_i64().zip(n2.as_i64()) {
                    Some((a, b)) => match a.checked_sub(b) {
                        Some(r) => json!(r),
                        None => json!(n1.as_f64().unwrap() - n2.as_f64().unwrap()),
                    },
                    None => json!(n1.as_f64().unwrap() - n2.as_f64().unwrap()),
                }
            }
        }
        _ => Value::Null,
    }
}

fn moss_mul(a: &Value, b: &Value) -> Value {
    match (a, b) {
        (Value::Number(n1), Value::Number(n2)) => {
            if n1.is_f64() || n2.is_f64() {
                json!(n1.as_f64().unwrap() * n2.as_f64().unwrap())
            } else {
                match n1.as_i64().zip(n2.as_i64()) {
                    Some((a, b)) => match a.checked_mul(b) {
                        Some(r) => json!(r),
                        None => json!(n1.as_f64().unwrap() * n2.as_f64().unwrap()),
                    },
                    None => json!(n1.as_f64().unwrap() * n2.as_f64().unwrap()),
                }
            }
        }
        _ => Value::Null,
    }
}

fn moss_div(a: &Value, b: &Value) -> Value {
    // Division always produces a float in Moss.
    match (a, b) {
        (Value::Number(n1), Value::Number(n2)) => {
            let denom = n2.as_f64().unwrap();
            if denom == 0.0 {
                Value::Null
            } else {
                json!(n1.as_f64().unwrap() / denom)
            }
        }
        _ => Value::Null,
    }
}

fn moss_lt(a: &Value, b: &Value) -> Value {
    match (a.as_f64(), b.as_f64()) {
        (Some(x), Some(y)) => json!(x < y),
        // NOTE: string ordering not supported — returns null
        _ => Value::Null,
    }
}

fn moss_gt(a: &Value, b: &Value) -> Value {
    match (a.as_f64(), b.as_f64()) {
        (Some(x), Some(y)) => json!(x > y),
        // NOTE: string ordering not supported — returns null
        _ => Value::Null,
    }
}

fn moss_lte(a: &Value, b: &Value) -> Value {
    match (a.as_f64(), b.as_f64()) {
        (Some(x), Some(y)) => json!(x <= y),
        // NOTE: string ordering not supported — returns null
        _ => Value::Null,
    }
}

fn moss_gte(a: &Value, b: &Value) -> Value {
    match (a.as_f64(), b.as_f64()) {
        (Some(x), Some(y)) => json!(x >= y),
        // NOTE: string ordering not supported — returns null
        _ => Value::Null,
    }
}

fn moss_eq(a: &Value, b: &Value) -> Value {
    match (a.as_f64(), b.as_f64()) {
        (Some(x), Some(y)) => json!(x == y),
        _ => json!(a == b),
    }
}
fn moss_neq(a: &Value, b: &Value) -> Value {
    match (a.as_f64(), b.as_f64()) {
        (Some(x), Some(y)) => json!(x != y),
        _ => json!(a != b),
    }
}
"""


def escape_rust_string(s):
    return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\t", "\\t")


_ARITH_OP_FNS = {"+": "moss_add", "-": "moss_sub", "*": "moss_mul", "/": "moss_div"}
_CMP_OP_FNS = {"<": "moss_lt", ">": "moss_gt", "<=": "moss_lte", ">=": "moss_gte",
               "==": "moss_eq", "!=": "moss_neq"}


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
    if k == "unop":
        if node["op"] == "not":
            operand = gen_expr(node["operand"])
            return f'json!(!({operand}).as_bool().unwrap_or(false))'
        raise RuntimeError(f"unknown unop: {node['op']}")
    if k == "binop":
        op = node["op"]
        left = gen_expr(node["left"])
        right = gen_expr(node["right"])
        if op in _ARITH_OP_FNS:
            return f'{_ARITH_OP_FNS[op]}(&({left}), &({right}))'
        if op in _CMP_OP_FNS:
            return f'{_CMP_OP_FNS[op]}(&({left}), &({right}))'
        if op == "and":
            return f'json!(({left}).as_bool().unwrap_or(false) && ({right}).as_bool().unwrap_or(false))'
        if op == "or":
            return f'json!(({left}).as_bool().unwrap_or(false) || ({right}).as_bool().unwrap_or(false))'
        raise RuntimeError(f"unknown binop: {op}")
    if k == "call":
        fn_name = node["name"]
        args = [gen_expr(a) for a in node["args"]]
        if fn_name == "length":
            if len(args) != 1:
                raise RuntimeError("length() takes exactly one argument")
            return f'json!(({args[0]}).as_array().map_or(0, |a| a.len()) as i64)'
        arg_refs = ", ".join(f"&({a})" for a in args)
        return f'moss_fn_{fn_name}({arg_refs})'
    if k == "index":
        list_code = gen_expr(node["list"])
        idx_code = gen_expr(node["idx"])
        return (
            "{ let _idx = ("
            + idx_code
            + ").as_i64().unwrap_or(0) - 1; "
            + "if _idx >= 0 { ("
            + list_code
            + ").as_array().and_then(|a| a.get(_idx as usize)).cloned().unwrap_or(Value::Null) } else { Value::Null } }"
        )
    if k == "list":
        parts = [gen_expr(it) for it in node["items"]]
        return f'Value::Array(vec![{", ".join(parts)}])'
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


def gen_block(stmts, indent=1, declared=None):
    """Generate Rust for a block of statements.

    `declared` is the set of variable names already bound in enclosing scopes.
    Assignments to names already in `declared` emit `name = expr;` (mutation)
    rather than `let mut name: Value = expr;` (new binding), so that loop bodies
    can accumulate into variables declared in the surrounding function scope.
    """
    if declared is None:
        declared = set()
    out = []
    pad = "    " * indent
    for s in stmts:
        k = s["kind"]
        if k == "assign":
            name = s["name"]
            expr_code = gen_expr(s["value"])
            if name not in declared:
                out.append(f'{pad}let mut {name}: Value = {expr_code};')
                declared.add(name)
            else:
                out.append(f'{pad}{name} = {expr_code};')
        elif k == "output":
            out.append(f'{pad}{{ let _moss_v: Value = {gen_expr(s["value"])}; println!("{{}}", _moss_v); }}')
        elif k == "if":
            out.append(gen_if(s, indent, declared))
        elif k == "for_in":
            out.append(gen_for_in(s, indent, declared))
        elif k == "for_range":
            out.append(gen_for_range(s, indent, declared))
        elif k == "stop":
            out.append(f'{pad}break;')
        elif k == "skip":
            out.append(f'{pad}continue;')
        elif k == "return":
            out.append(f'{pad}return {gen_expr(s["value"])};')
        else:
            raise RuntimeError(f"unknown block stmt kind: {k}")
    return "\n".join(out)


def gen_if(node, indent=1, declared=None):
    if declared is None:
        declared = set()
    pad = "    " * indent
    snapshot = set(declared)

    # Pass 1: dry-run each branch with an isolated copy to discover new variables.
    branch_new_sets = []
    for branch in node["branches"]:
        branch_declared = set(declared)
        gen_block(branch["body"], indent + 1, branch_declared)
        branch_new_sets.append(branch_declared - snapshot)

    has_else = node["else_body"] is not None
    else_new = set()
    if has_else:
        else_declared = set(declared)
        gen_block(node["else_body"], indent + 1, else_declared)
        else_new = else_declared - snapshot

    # Collect all newly-introduced names across every branch.
    all_new = set()
    for s in branch_new_sets:
        all_new |= s
    all_new |= else_new

    # Pre-declare every new variable before the if block so Rust can see it in
    # subsequent statements.  Both "declared in all paths" and "declared in some
    # paths" cases need this — the difference is only semantic (the latter may
    # remain Value::Null when the branch was not taken).
    lines = []
    for v in sorted(all_new):
        lines.append(f'{pad}let mut {v}: Value = Value::Null;')
        declared.add(v)

    # Pass 2: generate actual branch code.  declared now includes the pre-declared
    # names, so gen_block will emit plain assignment (not let mut) inside branches.
    for i, branch in enumerate(node["branches"]):
        cond_code = gen_expr(branch["cond"])
        kw = "if" if i == 0 else "} else if"
        lines.append(f'{pad}{kw} ({cond_code}).as_bool().unwrap_or(false) {{')
        lines.append(gen_block(branch["body"], indent + 1, set(declared)))
    if has_else:
        lines.append(f'{pad}}} else {{')
        lines.append(gen_block(node["else_body"], indent + 1, set(declared)))
    lines.append(f'{pad}}}')
    return "\n".join(lines)


def gen_for_in(node, indent=1, declared=None):
    if declared is None:
        declared = set()
    pad = "    " * indent
    var = node["var"]
    iter_code = gen_expr(node["iter"])
    # The loop variable is a fresh binding inside the loop block.
    inner_declared = set(declared)
    inner_declared.add(var)
    body_code = gen_block(node["body"], indent + 1, inner_declared)
    # Do NOT propagate loop-body declarations to the outer scope — variables
    # introduced inside the loop are not in scope after it.
    lines = [
        f'{pad}for _moss_{var} in ({iter_code}).as_array().cloned().unwrap_or_default() {{',
        f'{pad}    let {var}: Value = _moss_{var};',
        body_code,
        f'{pad}}}',
    ]
    return "\n".join(lines)


def gen_for_range(node, indent=1, declared=None):
    if declared is None:
        declared = set()
    pad = "    " * indent
    var = node["var"]
    start_code = gen_expr(node["start"])
    end_code = gen_expr(node["end"])
    inner_declared = set(declared)
    inner_declared.add(var)
    body_code = gen_block(node["body"], indent + 2, inner_declared)
    # Do NOT propagate loop-body declarations to the outer scope.
    lines = [
        f'{pad}{{',
        f'{pad}    let _start = ({start_code}).as_i64().unwrap_or(0);',
        f'{pad}    let _end = ({end_code}).as_i64().unwrap_or(0);',
        f'{pad}    for _moss_{var} in _start..=_end {{',
        f'{pad}        let {var}: Value = json!(_moss_{var});',
        body_code,
        f'{pad}    }}',
        f'{pad}}}',
    ]
    return "\n".join(lines)


def gen_user_fn(fn_node):
    """Generate a Rust function for a user-defined Moss function."""
    params_sig = ", ".join(f"{p}: &Value" for p in fn_node["params"])
    body = fn_node["body"]
    declared = set(fn_node["params"])
    body_code = gen_block(body, 1, declared)
    # Only append the implicit null return when the last statement is not already
    # a return — avoids the unreachable_code lint for functions that always return.
    has_explicit_return = bool(body) and body[-1]["kind"] == "return"
    fallthrough = "" if has_explicit_return else "\n    Value::Null\n"
    return (
        f'fn moss_fn_{fn_node["name"]}({params_sig}) -> Value {{\n'
        + body_code
        + fallthrough
        + "}\n"
    )


def _calls_in_expr(node):
    """Recursively yield all call nodes in an expression tree."""
    k = node.get("kind")
    if k == "call":
        yield node
        for arg in node["args"]:
            yield from _calls_in_expr(arg)
    elif k == "binop":
        yield from _calls_in_expr(node["left"])
        yield from _calls_in_expr(node["right"])
    elif k == "unop":
        yield from _calls_in_expr(node["operand"])
    elif k == "index":
        yield from _calls_in_expr(node["list"])
        yield from _calls_in_expr(node["idx"])
    elif k == "list":
        for item in node["items"]:
            yield from _calls_in_expr(item)
    elif k == "record":
        for _, val in node["pairs"]:
            yield from _calls_in_expr(val)


def _calls_in_stmts(stmts):
    """Recursively yield all call nodes in a list of statements."""
    for stmt in stmts:
        k = stmt.get("kind")
        if k in ("assign", "output", "return"):
            yield from _calls_in_expr(stmt["value"])
        elif k == "if":
            for branch in stmt["branches"]:
                yield from _calls_in_stmts(branch["body"])
            if stmt.get("else_body"):
                yield from _calls_in_stmts(stmt["else_body"])
        elif k == "for_in":
            yield from _calls_in_expr(stmt["iter"])
            yield from _calls_in_stmts(stmt["body"])
        elif k == "for_range":
            yield from _calls_in_expr(stmt["start"])
            yield from _calls_in_expr(stmt["end"])
            yield from _calls_in_stmts(stmt["body"])


def _validate_calls(all_stmts, known_fns, source_lines, filename):
    """Walk all stmts and raise MossError on unknown or wrong-arity calls."""
    for call in _calls_in_stmts(all_stmts):
        name = call["name"]
        line_no = call.get("line_no", 1)
        if name not in known_fns:
            raise MossError(line_no, source_lines,
                f'Unknown function "{name}". Did you define it?', filename)
        expected = known_fns[name]
        got = len(call["args"])
        if got != expected:
            s = "" if expected == 1 else "s"
            raise MossError(line_no, source_lines,
                f'Function "{name}" takes {expected} argument{s}, but you passed {got}.',
                filename)


def compile_program(ast, filename, source_lines):
    # Collect top-level assigns, user-defined functions, and main.
    top_assigns = []
    user_fns = []
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
                user_fns.append(stmt)
        else:
            raise RuntimeError(f"unexpected top-level stmt: {stmt['kind']}")
    if main_fn is None:
        raise MossError(1, source_lines,
            "Every Moss program needs a function called \"main\". Add one like this:\n\n    fn main\n        output \"hello\"", filename)

    # Arity / existence validation pass.
    known_fns = {fn["name"]: len(fn["params"]) for fn in user_fns}
    known_fns["length"] = 1
    all_stmts = (
        top_assigns
        + main_fn["body"]
        + [stmt for fn in user_fns for stmt in fn["body"]]
    )
    _validate_calls(all_stmts, known_fns, source_lines, filename)

    # Generate user-defined functions (emitted before main so they're in scope).
    user_fn_code = "".join(gen_user_fn(fn) + "\n" for fn in user_fns)

    # Generate the main function body with top-level assigns first, then main body.
    combined = top_assigns + main_fn["body"]
    body_code = gen_block(combined)

    rust = (
        RUNTIME_PREAMBLE
        + "\n"
        + user_fn_code
        + "fn main() {\n"
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
