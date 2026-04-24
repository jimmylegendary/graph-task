# graph-task

A structured task protocol with a **markdown-canonical** working model.

Current direction:
1. keep the old JSON CLI only as a legacy prototype / migration aid
2. freeze the md-first collaborative protocol as the real contract
3. make Obsidian the deterministic human-facing client for that protocol

## Current focus
The repo contains both:
- a legacy `graph.json` prototype that still helps with fixtures and experimentation
- the current vNext direction, where structured markdown is canonical and Obsidian is a first-class working surface

The intended default is the second one.
If a doc or example still presents `graph.json` as canonical, treat that as legacy material that should be corrected or clearly labeled.

Recent additions:
- `references/md-first-vnext-spec.md` captures the markdown-canonical protocol
- `references/obsidian-plugin-mvp-spec.md` defines the deterministic md-first plugin surface
- `examples/md-first-minimal/` gives the smallest canonical markdown example

## High-level contract

Canonical md-first `graph-task` freezes this hierarchy first:

- `project` = graph of `step`
- `step` = graph of `phase`
- `phase` = rooted graph of `node` and `edge`

Notes:
- `step` includes `stepType` and `description`
- `phase` includes `phaseType` and `description`
- `phase` uses the functional modes `diverge | converge | verify | commit`
- a step may repeat `diverge`, `converge`, and `verify`
- a step may contain at most one `commit` phase
- canonical discovery should come from folder layout + YAML frontmatter, not body links alone
- the shared status vocabulary is `pending | active | done | blocked | cancelled`

## Main files

- `SKILL.md` — skill instructions
- `scripts/graph_task.py` — bundled CLI
- `references/schema.graph-task.json` — high-level entity schema
- `references/rules.graph-task.md` — high-level structural rules
- `references/result-record.schema.json` — result writeback shape
- `references/cli.graph-task.md` — CLI command surface
- `references/phase2-obsidian-spec.md` — **legacy** export/projection contract from the JSON-canonical phase
- `references/md-first-vnext-spec.md` — canonical md-first protocol for collaborative use
- `references/obsidian-plugin-mvp-spec.md` — deterministic Obsidian client for md-first graph-task
- `examples/minimal-project/` — smallest valid example from the legacy JSON prototype
- `examples/self-dogfood-project/` — richer legacy dogfood example with repeated phases, step edges, and recorded findings
- `examples/self-dogfood-obsidian-vault/` — derived export from the legacy JSON prototype, not canonical state
- `examples/md-first-minimal/` — smallest canonical markdown example for the vNext direction
- standalone plugin repo: `https://github.com/jimmylegendary/graph-task-obsidian` — Obsidian community plugin MVP for tree-first exploration of md-first graph-task projects
- `tests/test_graph_task_cli.py` — smoke tests for the legacy CLI prototype
