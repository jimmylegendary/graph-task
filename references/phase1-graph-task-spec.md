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
- file-based run layout
- OpenClaw skill usage surface
- CLI commands for create/read/update/mutate flows
- deterministic-first transition rules
- explicit expected-vs-actual result ingestion
- minimal query/report rendering for human inspection

## Core high-level schema

`graph-task` should treat work as a hierarchical graph with exactly these top-level concepts:
- `Project`
- `Step`
- `Phase`
- `Node`
- `Edge`

The high-level shape is:

- `Project` = graph of `Step`
- `Step` = graph of `Phase`
- `Phase` = rooted graph of `Node` and `Edge`

### 1. Project
The top-level graph container.

Responsibilities:
- contain all steps for a work graph
- contain step-to-step connectivity
- act as the top-level inspection boundary

Minimum high-level shape:
- `id`
- `steps[]`
- `stepEdges[]`

### 2. Step
A project-level work unit for one kind of work.

A step should answer:
- what kind of work this step is for
- what this step is about
- which phases belong to this step
- how those phases connect

Important semantic rule:
- a `Step` is not the same as a `Phase`
- phases inside a step are different functional modes for the same step-level work
- the canonical phase types are `diverge`, `converge`, `verify`, `commit`

Minimum high-level shape:
- `id`
- `projectId`
- `stepType`
- `description`
- `phases[]`
- `phaseEdges[]`

### 3. Phase
A step-internal bounded graph unit.

Responsibilities:
- contain the actual node graph for one functional mode
- remain internally inspectable as a complete rooted subgraph
- allow selective visualization and filtering later

Structural rules:
- every phase must have exactly one root node
- every phase is a complete internal graph
- phase-to-phase connectivity should be modeled explicitly inside the parent step

Minimum high-level shape:
- `id`
- `stepId`
- `phaseType`
- `rootNodeId`
- `nodes[]`
- `edges[]`

Canonical phase types in this model:
- `diverge`
- `converge`
- `verify`
- `commit`

### 4. Node
The smallest graph vertex inside a phase.

At this level, node semantics are intentionally not expanded yet.
The high-level schema only needs node identity and phase membership.

Minimum high-level shape:
- `id`
- `phaseId`

### 5. Edge
The directed connection between nodes inside a phase.

At this level, edge semantics are intentionally not expanded yet.
The high-level schema only needs identity, phase membership, and endpoints.

Minimum high-level shape:
- `id`
- `phaseId`
- `fromNodeId`
- `toNodeId`

### 6. StepEdge
An explicit connection between two steps inside a project.

Minimum high-level shape:
- `id`
- `projectId`
- `fromStepId`
- `toStepId`

### 7. PhaseEdge
An explicit connection between two phases inside a step.

Minimum high-level shape:
- `id`
- `stepId`
- `fromPhaseId`
- `toPhaseId`

## High-level structural rules
- a project contains steps and step edges
- a step contains phases and phase edges
- a phase contains nodes and edges
- a phase always has exactly one root node
- a node edge connects only nodes in the same phase
- a phase edge connects only phases in the same step
- a step edge connects only steps in the same project

## Why this shape
This hierarchy is the minimum needed to support:
- honest append/refine graph evolution without deleting history
- phase-level collapse/expand visualization later
- step-level grouping by work purpose
- explicit separation between step-level work kind and phase-level functional mode
- future extension of lower-level semantics without changing the top-level graph model

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

Rule:
- `graph.json` is the canonical snapshot
- `events.jsonl` is the append-only mutation history
- `summary.md` is the human-readable state summary

## Phase 1 note on detail level
Phase 1 should freeze the high-level graph shape first.
Detailed internal semantics for Project, Step, Phase, Node, and Edge can be refined after this shape is accepted.

The immediate objective is to lock:
- hierarchy
- containment boundaries
- connection boundaries
- root-node rule for phases
- step-level type + description support

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
Phase 1 high-level schema is complete when all of the following are true:

1. A graph-task project can represent steps explicitly.
2. Each step can represent what kind of step it is via `stepType`.
3. Each step can store a human-readable `description`.
4. Each step can contain phases connected by explicit phase edges.
5. Each phase is modeled as a rooted internal node graph.
6. Project, step, and phase boundaries are explicit enough for future visualization.
7. Lower-level semantic detail can be added later without changing the high-level hierarchy.

## Recommended next implementation order
1. freeze the high-level schema
2. freeze minimum field semantics for Project / Step / Phase / Node / Edge
3. define transition and mutation rules
4. define expected-vs-actual result ingestion
5. define summary/report rendering
6. smoke-test on at least one happy-path and one divergence-path scenario
