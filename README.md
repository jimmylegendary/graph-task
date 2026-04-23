# graph-task

A compact staged system for graph-based task execution.

Current direction:
1. graph-task core: canonical schema, expected-vs-actual contract, CLI/OpenClaw skill behavior
2. Obsidian-based visualization and semantic testing
3. autonomous completion using existing execution tools

## Current focus
Phase 1: freeze the canonical graph-task semantics before richer visualization or unattended automation.

## High-level schema

`graph-task` currently freezes this hierarchy first:

- `Project` = graph of `Step`
- `Step` = graph of `Phase`
- `Phase` = rooted graph of `Node` and `Edge`

Notes:
- `Step` includes `stepType` and `description`
- `Phase` uses the functional modes `diverge | converge | verify | commit`
- lower-level semantics for each entity are defined after the high-level graph shape is locked

See:
- `references/phase1-graph-task-spec.md`
- `references/schema.graph-task.json`
- `references/expected-result.schema.json`
- `references/phases.json`
