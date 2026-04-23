# graph-task high-level rules

This document defines the structural and operating rules for the high-level graph-task model.
The entity structure itself lives in `references/schema.graph-task.json`.

## Top-level hierarchy

- `Project` = graph of `Step`
- `Step` = graph of `Phase`
- `Phase` = rooted graph of `Node` and `Edge`

## Project rules

### Role
A Project is the top-level work container.
It defines the outer boundary for the whole task graph.

### Rules
1. A Project owns its `steps` and `stepEdges`.
2. Every Step belongs to exactly one Project.
3. `stepEdges` may connect only Steps in the same Project.
4. A Project may start rough or partial; its Step graph does not need to be fully connected at initialization.
5. At the Project level, only Step-level structure is modeled. Node-level or Phase-level relations do not bypass Step boundaries.

## Step rules

### Role
A Step is a Project-level work unit for one kind of work.
A Step answers what kind of work is being done and what that work is about.

### Rules
1. Every Step belongs to exactly one Project.
2. A Step contains one or more Phases.
3. `phaseEdges` may connect only Phases in the same Step.
4. A Step represents one step-level work purpose; its internal Phases are functional modes for the same work, not separate higher-level tasks.
5. The order or return path between Phases is represented by `phaseEdges`, not by `phaseType` alone.
6. A Step may contain multiple `diverge`, `converge`, and `verify` Phases.
7. A Step may contain at most one `commit` Phase.
8. Phase history should be preserved. If a Step returns from `verify` to another `diverge`, the earlier Phases remain in the graph and the new path is expressed with `phaseEdges`.

## Phase rules

### Role
A Phase is a bounded Step-internal subgraph for one functional mode.
It is the smallest graph unit that must remain internally complete and inspectable.

### Rules
1. Every Phase belongs to exactly one Step.
2. `phaseType` must be one of: `diverge`, `converge`, `verify`, `commit`.
3. Every Phase must have exactly one root Node.
4. `rootNodeId` must point to a Node inside the same Phase.
5. The root Node acts as the meta anchor and entry point for the Phase.
6. `edges` may connect only Nodes in the same Phase.
7. Every Node in a Phase should be reachable from the root Node.
8. Phase-to-Phase connectivity is not stored inside a Phase. The source of truth is the parent Step's `phaseEdges`.

## Node rules

### Role
A Node is the smallest task unit inside a Phase.

### Rules
1. Every Node belongs to exactly one Phase.
2. Node-to-Node connectivity is not stored inside Node objects. The source of truth is the parent Phase's `edges`.
3. Every Phase must contain exactly one Node with `nodeType = root`.
4. The `id` of that root Node must equal the Phase's `rootNodeId`.
5. All non-root Nodes must use `nodeType = work`.
6. Cross-Phase Node links are not allowed.
7. A Node's meaning is interpreted in the context of its parent `phaseType`:
   - `diverge` => exploration / trial / option work
   - `converge` => synthesis / narrowing / restructuring work
   - `verify` => checking / testing / validation work
   - `commit` => finalization / lock-in work

## Edge rules

### Role
An Edge is a directed connection between two Nodes inside a Phase.

### Rules
1. Every Edge belongs to exactly one Phase.
2. `fromNodeId` and `toNodeId` must both reference Nodes in the same Phase.
3. Edge direction is meaningful and must be preserved.
4. Self-loops are not allowed.
5. Duplicate edges with the same `(phaseId, fromNodeId, toNodeId, edgeType)` are not allowed.
6. The root Node must not have incoming Edges.
7. Every non-root Node should be reachable from the root Node.
8. `edgeType = dependency` means the `toNode` depends on the `fromNode`.
9. `edgeType = flow` means the work or reasoning flow proceeds from `fromNode` to `toNode`.
10. Cross-Phase Node connectivity is not allowed. If higher-level connectivity is needed, express it with `phaseEdges` or `stepEdges` instead.

## PhaseEdge rules

### Role
A PhaseEdge is a directed connection between two Phases in the same Step.

### Rules
1. Every PhaseEdge belongs to exactly one Step.
2. `fromPhaseId` and `toPhaseId` must both reference Phases in the same Step.
3. PhaseEdge is the canonical way to represent movement, return, branching, or continuation between Phases.
4. Repeated functional loops such as `verify -> diverge` are valid and should be preserved explicitly.

## StepEdge rules

### Role
A StepEdge is a directed connection between two Steps in the same Project.

### Rules
1. Every StepEdge belongs to exactly one Project.
2. `fromStepId` and `toStepId` must both reference Steps in the same Project.
3. StepEdge is the canonical way to express Project-level sequencing or dependency between Steps.

## Why these rules exist

These rules are meant to keep the model:
- inspectable
- append/refine friendly
- compatible with later CLI and skill behavior
- safe for future visualization without changing the top-level graph contract
