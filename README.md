# graph-task

A compact staged system for graph-based task execution.

Current direction:
1. graph-task core: canonical schema, direct-edit CLI/skill, expected-vs-actual result contract
2. Obsidian-based visualization and semantic testing
3. autonomous completion using existing execution tools

## Current focus
Phase 2 baseline: project Phase 1 graph-task runs into an Obsidian-friendly markdown vault for visualization and semantic testing, while keeping `graph.json` as the canonical state.

Recent additions:
- `init` can target a git-backed repo checkout so each project run is created under its own top-level folder inside a shared vault/work repo.
- repo-backed runs now have manual sync helpers: `git-status`, `git-pull`, `git-push`, and `git-sync`.

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
- `examples/minimal-project/` — smallest valid example with one result record
- `examples/self-dogfood-project/` — richer dogfood example with repeated phases, step edges, and recorded findings
- `examples/self-dogfood-obsidian-vault/` — exported Obsidian-friendly markdown vault for the richer dogfood example
- `tests/test_graph_task_cli.py` — independent smoke tests
