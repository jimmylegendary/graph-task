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

## Core model

### 1. Graph
A graph is the canonical state object for a work run.

It contains:
- graph identity and metadata
- objective
- plan summary
- nodes
- edges / dependencies
- branch lineage
- policy summary
- event history references
- current graph status

The graph is the source of truth.
Other surfaces may render or edit it later, but should not replace it.

### 2. Node
A node is the minimum executable or reviewable unit.

Each node should answer:
- what is supposed to happen
- what must be true before it can start
- what happened in reality
- what artifacts came out
- whether the path should continue, retry, branch, replan, or stop

### 3. Observation/result
A result is the structured write-back from execution or review.
It must preserve the difference between:
- expected outcome
- actual outcome
- evidence/artifacts
- interpretation
- severity/escalation

### 4. Transition
A transition is an explicit graph mutation with a reason.
Every state change should be representable as an event.

### 5. Branch
A branch is an explicit alternative path created because:
- the original path failed
- a materially different tactic is needed
- exploration is intentionally diverging

Branches must never be implicit.

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

## Schema draft

### objective.json
Minimum fields:
- `id`
- `title`
- `goal`
- `success_definition`
- `constraints`
- `created_at`
- `updated_at`

### plan.json
Minimum fields:
- `id`
- `objective_id`
- `summary`
- `assumptions`
- `strategy`
- `completion_shape`
- `created_at`
- `updated_at`

### graph.json
Minimum top-level fields:
- `graph_id`
- `objective_id`
- `plan_id`
- `status`
- `nodes`
- `edges`
- `branches`
- `policy`
- `created_at`
- `updated_at`

### Node schema
Minimum node fields:
- `id`
- `title`
- `kind`
- `status`
- `depends_on`
- `expected_outcome`
- `actual_outcome`
- `artifacts`
- `attempt_count`
- `branch_id`
- `created_at`
- `updated_at`

Recommended Phase 1 additions:
- `description`
- `acceptance_criteria`
- `failure_mode`
- `owner`
- `tags`
- `escalation`

### Edge schema
Minimum edge fields:
- `from`
- `to`
- `type`

Allowed Phase 1 edge types:
- `depends_on`
- `branch_from`
- `replans`
- `supersedes`

### Branch schema
Minimum fields:
- `id`
- `parent_branch_id`
- `parent_node_id`
- `reason`
- `status`
- `created_at`

### Event schema
Each line in `events.jsonl` should contain at least:
- `id`
- `timestamp`
- `entity_type`
- `entity_id`
- `verb`
- `reason`
- `payload`

## Status model

### Graph statuses
- `draft`
- `active`
- `paused`
- `completed`
- `canceled`
- `failed`

### Node statuses
- `planned`
- `ready`
- `running`
- `blocked`
- `done`
- `failed`
- `canceled`
- `superseded`

### Branch statuses
- `open`
- `paused`
- `closed`
- `superseded`

## Transition vocabulary
Required verbs:
- `seed`
- `start`
- `complete`
- `fail`
- `retry`
- `branch`
- `cancel`
- `replan`
- `escalate`
- `resume`
- `supersede`

## Decision model
Phase 1 should be deterministic-first.

Meaning:
- basic graph state transitions should come from explicit rules
- LLM help may propose plans, summaries, or branch rationale
- but the mutation contract must stay policy-checked and inspectable

Recommendation:
- allow LLM-proposed mutation suggestions later
- keep actual mutation application rule-driven in Phase 1

## Result ingestion contract
A node result write-back should include:
- `node_id`
- `attempt`
- `result_status`
- `expected_outcome`
- `actual_outcome`
- `artifacts`
- `notes`
- `escalation_level`
- `escalation_message`
- `recommended_next_action`

Allowed `result_status` values:
- `done`
- `failed`
- `blocked`
- `canceled`

Allowed `recommended_next_action` values:
- `continue`
- `retry`
- `branch`
- `replan`
- `cancel`
- `escalate`
- `complete`

Important rule:
The engine stores both the raw result and the applied mutation.
A recommendation is not itself a mutation.

## Escalation model
Severity levels:
- `info`
- `warning`
- `blocking`
- `critical`

Phase 1 rule:
- `info` and `warning` can coexist with forward progress
- `blocking` pauses the affected path until a valid next mutation exists
- `critical` pauses the graph and requires human review

## Minimal policy rules

### Ready rule
A node becomes `ready` when all `depends_on` nodes are `done`.

### Completion rule
When a node result is ingested as `done`:
- mark the node `done`
- record actual outcome and artifacts
- evaluate downstream nodes for `ready`
- if no remaining open nodes exist, mark graph `completed`

### Failure rule
When a node result is ingested as `failed`:
- mark the node `failed`
- require one of: `retry`, `branch`, `replan`, `cancel`, `escalate`
- never silently continue as if success occurred

### Retry rule
Retry should:
- increment `attempt_count`
- preserve prior failure history in events
- return the same node to `ready` or create a retry-attempt record

### Branch rule
Branch should:
- create a new branch record
- create one or more new nodes on that branch
- preserve lineage to the parent node/path
- optionally supersede future nodes on the failed path

### Replan rule
Replan should:
- preserve history
- write explicit rationale
- mutate future graph structure, not erase prior events

### Cancel rule
Cancel should:
- explicitly mark affected nodes/branch/graph as canceled
- include a reason
- never masquerade as completion

## CLI surface
Phase 1 CLI should stay small.

Recommended commands:
- `graph-task init`
- `graph-task seed`
- `graph-task show`
- `graph-task list-ready`
- `graph-task ingest-result`
- `graph-task decide-next`
- `graph-task retry`
- `graph-task branch`
- `graph-task replan`
- `graph-task cancel`
- `graph-task summarize`

### Command expectations
`graph-task init`
- creates run directory and required files
- writes objective + initial plan shell

`graph-task seed`
- creates initial nodes/edges into `graph.json`
- appends seed event(s)

`graph-task show`
- renders current graph or a specific node/branch

`graph-task list-ready`
- returns nodes currently executable under policy

`graph-task ingest-result`
- records structured result write-back
- applies policy-allowed mutation(s)
- appends event(s)
- refreshes summary

`graph-task decide-next`
- reports the valid next action set for a node/branch/graph
- should explain why

`graph-task retry`
- performs explicit retry mutation

`graph-task branch`
- performs explicit branch mutation

`graph-task replan`
- updates future structure with rationale preserved

`graph-task cancel`
- cancels node/branch/graph explicitly

`graph-task summarize`
- regenerates `summary.md`

## OpenClaw skill surface
The skill should primarily be used when the operator needs to:
- initialize a graph-backed work run
- inspect current graph state
- mutate the graph after a result or observation
- decide next legal moves
- preserve resumable state for later review or automation

The skill should frame `graph-task` as:
- canonical state layer now
- visualization substrate for Obsidian later
- execution substrate contract for lobster/heartbeat later

## Human inspection surface
Phase 1 must support basic human verification without external visualization.

Minimum inspection outputs:
- current graph status
- ready nodes
- blocked/failed nodes
- branch lineage summary
- recent event timeline
- expected-vs-actual summary for latest completed/failed nodes

This can be plain text or markdown.
That is enough for Phase 1.

## Acceptance criteria
Phase 1 is complete when all of the following are true:

1. A new graph-task run can be initialized from scratch.
2. The required files are present immediately.
3. An initial graph can be seeded and inspected.
4. A result can be ingested with explicit expected-vs-actual fields.
5. The graph mutates honestly under deterministic rules.
6. Retry, branch, replan, and cancel are explicit commands, not hidden behavior.
7. A human can inspect current state from generated text/markdown alone.
8. The resulting schema is stable enough for Obsidian mapping in Phase 2.

## Non-acceptance signals
Phase 1 is not complete if:
- the graph cannot be reconstructed from persisted files
- transitions happen without explicit event history
- branch lineage is ambiguous
- expected-vs-actual is hand-wavy instead of structured
- command surface is so broad that semantics are still unclear
- automation concerns distort the state model before human verification works

## Phase boundary to Phase 2
Only move to Phase 2 after Phase 1 proves:
- canonical graph schema is usable
- mutation semantics are understandable
- human inspection is sufficient to catch semantic mistakes

Phase 2 can then treat Obsidian as:
- graph browser
- review/edit surface
- semantic debugging tool

Not as the canonical state store.

## Recommended next implementation order
1. freeze JSON schema draft
2. implement run initialization
3. implement graph seeding
4. implement result ingestion
5. implement deterministic transition rules
6. implement summary/report rendering
7. smoke-test on at least one happy-path and one divergence-path scenario
