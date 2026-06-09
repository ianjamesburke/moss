<!-- DEV_LOG.md — Newest entries first. Captures decisions, gotchas, and the WHY behind non-obvious choices. Read the top 100–150 lines to orient quickly. -->

## 2026-04-21 — [DECISION] Bare words are always variable references; strings always need quotes

Previously, record values accepted bare words as string atoms (`type: ready`), but variable assignments treated bare words as variable references (`name = ian` → Rust `ian.clone()`). This created two parsing rules for the same syntax depending on context. Unified to one rule: bare words everywhere mean variable references, string literals always require quotes (`type: "ready"`). Updated README and all examples accordingly. No compiler change needed — `_inline()` already produced `{"kind": "var"}` for bare words; the inconsistency was only in the docs/examples.

## 2026-04-21 — [CHANGED] Renamed `emit` → `output` in all docs and examples

The compiler renamed `emit` to `output` in commit 8e59a2f but the README, compiler docstring, and error messages still referenced `emit`. Updated all occurrences. Two prose spots needed manual fixes to avoid "output structured output" redundancy → changed to "produce structured output".

## 2026-04-21 — [ADDED] `input` documented in main README

`input` (stdin JSON with dot access) was implemented in 8e59a2f but the README still listed "Reading input — For v1" in the "What you can't do yet" section. Added an `input` section under "The two things Moss does" with usage example and pipeline syntax. Removed the stale v1 bullet.
