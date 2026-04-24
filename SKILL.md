---
name: graph-task
description: Create, inspect, and update graph-backed work runs using the Project/Step/Phase/Node/Edge model and the bundled graph_task.py CLI. Use when you need to initialize a graph-task run, add steps/phases/nodes/edges, record expected-vs-actual node results, regenerate summaries, validate graph structure, or preserve task history without introducing a separate mutation engine.
---

# graph-task

Use the bundled CLI:

```bash
python3 scripts/graph_task.py <command> ...
```

## Read these references as needed

- `references/schema.graph-task.json` — entity shape
- `references/rules.graph-task.md` — structural rules
- `references/result-record.schema.json` — result writeback shape
- `references/cli.graph-task.md` — command examples and flags

## Current operating model

- Keep the graph in `graph.json` as the canonical state.
- Use one shared minimal status vocabulary everywhere: `pending | active | done | blocked | cancelled`.
- Do not introduce a separate mutation engine in this stage.
- If the work structure changes, append new Steps, Phases, Nodes, and Edges instead of deleting history.
- Record execution or verification outcomes by appending result records to `node.results` with expected vs actual text.

## Recommended workflow

1. Initialize a run with `init`.
2. Add Steps.
3. Add Phases to each Step; each Phase gets an automatic root node.
4. Add work Nodes and node Edges.
5. Add PhaseEdges and StepEdges where needed.
6. Update statuses directly with `set-status`.
7. Record outcomes with `write-result`.
8. Use `summary` and `validate` before reporting completion.
9. When human inspection or graph visualization matters, use `export-obsidian` to project the run into an Obsidian-friendly markdown vault.
10. For repo-backed runs, use `git-status` to inspect sync state and `git-sync --message ...` for explicit manual pull/commit/push cycles.

## Repo-backed vault workflow

- `init --repo-url <repo> --repo-branch <branch>` creates or refreshes a local checkout, then writes the run into `<checkout>/<project-id-slug>/`.
- Repo metadata is recorded in `project.repo` so later sync commands can find the checkout again.
- Use `git-status` before and after meaningful work blocks.
- Use `git-push --message ...` when you only want to commit/push current local changes.
- Use `git-pull` when you need the latest remote state and your local repo is clean.
- Use `git-sync --message ...` as the normal manual sync path: fast-forward pull first, then commit all pending changes, then push.
- These commands operate on the entire repo checkout. Be honest if unrelated dirty files in the same repo make sync unsafe.
- Avoid hidden merge behavior: this workflow intentionally prefers `pull --ff-only` and surfaces divergence instead of auto-resolving it.

## Minimum validation before claiming success

Run:

```bash
python3 scripts/graph_task.py validate <run-dir>
python3 scripts/graph_task.py summary <run-dir>
```

If you changed the skill itself, also run:

```bash
python3 -m unittest tests/test_graph_task_cli.py
python3 /home/jimmy/.npm-global/lib/node_modules/openclaw/skills/skill-creator/scripts/package_skill.py <skill-dir> <output-dir>
```
