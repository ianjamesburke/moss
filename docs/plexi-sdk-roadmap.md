# Moss Plexi SDK Roadmap

Moss should become the simplest way to build useful Plexi apps.

That does not mean Moss should build every possible Plexi app. It means Moss
should make the common app shape almost impossible to get wrong: a small app
with state, a declarative view, a few event handlers, a manifest, and explicit
capabilities.

## Thesis

Plexi apps speak PGAP over stdin and stdout. The Python SDK is one wrapper
around that protocol, not the protocol itself.

Moss should compile to a PGAP-speaking app binary. It should not depend on the
Python SDK.

The first Moss SDK target should emit Plexi's declarative UiNode tree:

- app bars
- columns
- labels
- sections
- lists
- buttons
- text inputs
- footer key rows
- cards
- spacers

The first target should not expose raw pixel drawing. Pixel math belongs in
Python or Rust apps until Moss earns that surface.

## Product Boundary

Moss is good for:

- small stateful tools
- dashboards
- forms
- list managers
- pipeline viewers
- notification senders
- agent frontends
- apps that call Plexi host APIs through capabilities

Moss is not the right first tool for:

- games
- custom canvas rendering
- low-latency audio or video apps
- raw terminal control
- apps that need arbitrary async orchestration

The boundary matters. If Moss tries to cover every PGAP feature immediately,
it becomes a smaller, weaker Python. If Moss owns the boring app path, it has a
reason to exist.

## Architecture

The compiler gets a second target:

```sh
moss plexi build path/to/app.moss
```

That target generates:

- a `manifest.toml`
- a Rust app binary
- a PGAP event loop
- built-in helpers for UiNode records
- built-in helpers for app state and host effects

The generated app handles:

- `init`
- `render`
- `key`
- `component_event`
- `text_submitted`
- `shutdown`

The generated app emits:

- `ready`
- `component_tree`
- `frame_done`
- `schedule_render`
- `save_app_state`
- `notify`
- `log`

Later releases can add more host requests one capability at a time.

## Syntax Direction

Do not settle final syntax too early. The first syntax only needs to prove the
shape.

Possible shape:

```moss
app counter
    name: "Counter"
    version: "0.1.0"

state
    count = 0

fn view
    return column([
        app_bar("Counter"),
        spacer(grow: true),
        label(count),
        spacer(grow: true),
        footer_keys([
            key("+", "increment"),
            key("-", "decrement")
        ])
    ])

on key "+"
    count = count + 1
    render

on key "-"
    count = count - 1
    render
```

This is deliberately narrower than Python. The app has a view. Events mutate
state. State changes ask Plexi to render again.

## Milestones

### 1. Trust The Compiler

Before Moss grows a Plexi target, it needs tests and semantic validation.

Ship:

- example golden tests
- negative diagnostic tests
- CLI tests
- GitHub Actions CI
- variable and scope validation before Rust codegen

Done means bad Moss fails inside Moss, not later as a Rust compiler error.

### 2. Define The Plexi Contract

Write the contract before writing the target.

Ship:

- `docs/plexi-sdk-spec.md`
- current PGAP version reference
- supported UiNode list
- supported event list
- supported host effects
- manifest generation rules
- explicit non-goals

Done means a contributor can tell what Moss accepts, rejects, and emits.

### 3. Build The Counter

Build one app end to end.

Ship:

- `moss plexi init counter`
- `moss plexi build counter/app.moss`
- generated `manifest.toml`
- generated app binary
- counter app example
- PGAP transcript test for `init -> ready -> render -> component_tree -> frame_done`
- key event test that changes state

Done means Plexi can launch a Moss-built counter app.

### 4. Make Boring Apps Comfortable

Add the app primitives needed for real tools.

Ship:

- `select_list`
- `text_input`
- `text_edit`
- `button`
- `section`
- `card`
- `footer_keys`
- `on text submitted`
- `on component event`
- state persistence through `save_app_state`

Done means a todo app can be written in Moss without raw JSON records.

### 5. Add Host Powers Carefully

Expose host effects only when the language has a clear way to represent the
response.

First effects:

- `notify`
- `log`
- `schedule_render`
- `save_state`

Later effects:

- `http_request`
- `secret_get`
- `ai_query`
- `spawn_pane`
- `stream_process`

Done means each capability has syntax, generated JSON, error behavior, and
tests.

## Issue Spine

Start with a short issue set:

0. Roadmap: make Moss the simple app language for Plexi - #9
1. Add a Moss compiler test harness and CI - #10
2. Add variable and scope validation - #11
3. Define the Moss Plexi SDK spec - #12
4. Replace the stale PGAP v1 proof of concept - #13
5. Add `moss plexi init` - #14
6. Add manifest generation for Moss Plexi apps - #15
7. Add the PGAP runtime target - #16
8. Add UiNode built-ins - #17
9. Add app state and render scheduling - #18
10. Ship the counter example - #19

Do not file issues for every future PGAP command yet. Each new host power
should earn its own issue after the counter app works.

## Dependency Order

The issues are wired in GitHub as sub-issues of #9. Blocking relationships
encode the order:

```text
#10
├─ #11
│  ├─ #14
│  └─ #15
└─ #12
   ├─ #13
   ├─ #14
   └─ #15

#15
└─ #16
   ├─ #17
   └─ #18

#14 + #15 + #17 + #18
└─ #19
```

The only task ready to start immediately is #10. After #10 closes, #11 and
#12 can run in parallel. After those close, #13, #14, and #15 open up. The
counter example waits until the app scaffold, manifest generation, UiNode
built-ins, and state/render work are all done.
