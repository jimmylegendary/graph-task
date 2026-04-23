# Phase 1 — graph-task spec

## Purpose
Phase 1 is the smallest meaningful implementation of the reset direction chosen on 2026-04-23.

Its job is to prove that we can represent work as an explicit graph, mutate that graph honestly from results, and inspect the state clearly before adding richer visualization or unattended autonomy.

This phase is **not** about full overnight automation.
It is about locking the canonical semantics for `graph-task`.

## Validation question
Can we define a graph-task model and command surface that is:
- explicit enough for honest state mutation
- inspectable enough for human review
- narrow enough to implement quickly as an OpenClaw skill + CLI
- stable enough to become the canonical state layer for later Obsidian and autonomous execution phases

## Out of scope
Do not build these in Phase 1:
- heartbeat-driven autonomous completion loops
- lobster scheduling/execution integration beyond placeholder contracts
- rich graph visualization
- multi-user or multi-tenant concerns
- generalized workflow DSL
- hidden LLM replanning with no persisted rationale

## Deliverable
A first usable `graph-task` skill/package with:
- canonical persisted schema
- separately documented high-level structural rules
- file-based run layout
- OpenClaw skill usage surface
- CLI commands for create/read/update/mutate flows
- deterministic-first transition rules
- explicit expected-vs-actual result ingestion
- minimal query/report rendering for human inspection

## Core references

The high-level graph contract is now split into two references:

- `references/schema.graph-task.json`
  - entity structure
  - required vs optional fields
  - containment hierarchy

- `references/rules.graph-task.md`
  - structural rules
  - ownership rules
  - connectivity rules
  - root-node rules
  - repetition / history-preservation rules

Supporting references:
- `references/expected-result.schema.json`
- `references/phases.json`
- `references/test-levels.json`

## High-level hierarchy

`graph-task` currently freezes this hierarchy first:

- `Project` = graph of `Step`
- `Step` = graph of `Phase`
- `Phase` = rooted graph of `Node` and `Edge`

Current high-level semantics:
- `Step` includes `stepType` and `description`
- `Phase` includes `phaseType` and `description`
- `Phase.phaseType` uses the functional modes `diverge | converge | verify | commit`
- a Step may repeat `diverge`, `converge`, and `verify`
- a Step may contain at most one `commit` Phase
- lower-level execution semantics are defined after the high-level graph contract is locked

## Canonical run layout
Each run should create a directory from the beginning with at least:

- `objective.json`
- `plan.json`
- `graph.json`
- `events.jsonl`
- `summary.md`

Optional derived files allowed in Phase 1:
- `report.json`
- `report.md`
- `artifacts/`

Rules:
- `graph.json` is the canonical snapshot
- `events.jsonl` is the append-only mutation history
- `summary.md` is the human-readable state summary

## Human inspection surface
Phase 1 must support basic human verification without external visualization.

Minimum inspection outputs:
- current project structure
- step graph summary
- selected step's phase graph summary
- selected phase's rooted node graph summary
- recent event timeline
- expected-vs-actual summary for latest completed/failed nodes

This can be plain text or markdown.
That is enough for Phase 1.

## Acceptance criteria
Phase 1 high-level contract is complete when all of the following are true:

1. The schema and rules are documented separately.
2. A graph-task project can represent Steps explicitly.
3. Each Step can represent what kind of Step it is via `stepType`.
4. Each Step can store a human-readable `description`.
5. Each Step can contain Phases connected by explicit `phaseEdges`.
6. Each Phase is modeled as a rooted internal Node graph.
7. Repeated `diverge`, `converge`, and `verify` Phases can be represented without deleting history.
8. Project, Step, and Phase boundaries are explicit enough for future CLI, skill, and visualization work.

## Recommended next implementation order
1. freeze the high-level schema
2. freeze the high-level rules
3. freeze minimum field semantics for Project / Step / Phase / Node / Edge
4. define transition and mutation rules
5. define expected-vs-actual result ingestion
6. define summary/report rendering
7. smoke-test on at least one happy-path and one divergence-path scenario
