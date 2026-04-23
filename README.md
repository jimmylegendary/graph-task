# graph-task

A compact staged system for graph-based task execution.

Current direction:
1. graph-task core: canonical schema, expected-vs-actual contract, CLI/OpenClaw skill behavior
2. Obsidian-based visualization and semantic testing
3. autonomous completion using existing execution tools

## Current focus
Phase 1: freeze the canonical graph-task semantics before richer visualization or unattended automation.

## High-level contract

`graph-task` currently freezes this hierarchy first:

- `Project` = graph of `Step`
- `Step` = graph of `Phase`
- `Phase` = rooted graph of `Node` and `Edge`

Notes:
- `Step` includes `stepType` and `description`
- `Phase` includes `phaseType` and `description`
- `Phase` uses the functional modes `diverge | converge | verify | commit`
- a Step may repeat `diverge`, `converge`, and `verify`
- a Step may contain at most one `commit` Phase

## References

- `references/phase1-graph-task-spec.md` — Phase 1 overview
- `references/schema.graph-task.json` — high-level entity schema
- `references/rules.graph-task.md` — high-level structural rules
- `references/expected-result.schema.json` — expected-vs-actual result contract
- `references/phases.json` — staged roadmap
