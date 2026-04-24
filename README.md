# graph-task

A compact staged system for graph-based task execution.

Current direction:
1. learn from the JSON-canonical prototype already built
2. redesign toward an md-first collaborative task protocol
3. build an Obsidian plugin as the deterministic task client

## Current focus
The repo now contains two layers of thinking:
- the implemented Phase 1 / Phase 2 prototype, where `graph.json` is canonical
- the newer vNext direction, where structured markdown becomes canonical and Obsidian becomes a first-class working surface

Recent additions:
- `init` can target a git-backed repo checkout so each project run is created under its own top-level folder inside a shared vault/work repo.
- repo-backed runs now have manual sync helpers: `git-status`, `git-pull`, `git-push`, and `git-sync`.
- added `references/md-first-vnext-spec.md` to capture the current redesign toward structured-markdown canonical state and a protocol-aware Obsidian plugin

## High-level contract

`graph-task` currently freezes this hierarchy first:

- `project` = graph of `step`
- `step` = graph of `phase`
- `phase` = rooted graph of `node` and `edge`

Notes:
- `step` includes `stepType` and `description`
- `phase` includes `phaseType` and `description`
- `phase` uses the functional modes `diverge | converge | verify | commit`
- a step may repeat `diverge`, `converge`, and `verify`
- a step may contain at most one `commit` phase
- the current stage uses one shared status vocabulary and direct graph edits instead of a separate mutation engine

## Main files

- `SKILL.md` — skill instructions
- `scripts/graph_task.py` — bundled CLI
- `references/schema.graph-task.json` — high-level entity schema
- `references/rules.graph-task.md` — high-level structural rules
- `references/result-record.schema.json` — result writeback shape
- `references/cli.graph-task.md` — CLI command surface
- `references/phase2-obsidian-spec.md` — Phase 2 export / projection contract
- `references/md-first-vnext-spec.md` — proposed md-first canonical redesign for collaborative use
- `references/obsidian-plugin-mvp-spec.md` — proposed deterministic Obsidian client for md-first graph-task
- `examples/minimal-project/` — smallest valid example with one result record
- `examples/self-dogfood-project/` — richer dogfood example with repeated phases, step edges, and recorded findings
- `examples/self-dogfood-obsidian-vault/` — exported Obsidian-friendly markdown vault for the richer dogfood example
- `examples/md-first-minimal/` — smallest canonical markdown example for the vNext direction
- `tests/test_graph_task_cli.py` — independent smoke tests
