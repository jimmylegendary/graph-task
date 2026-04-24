---
name: graph-task
description: "Manage graph-task work runs with the md-first protocol: canonical markdown files, YAML frontmatter validation, and tree-first Obsidian collaboration. Use when you need to inspect or author the md-first run layout, validate frontmatter/file structure, review the legacy JSON CLI, or understand how markdown-canonical graph-task projects should be organized."
---

# graph-task

## Canonical rule

vNext `graph-task` is **md-first**.

Canonical state lives in markdown files arranged as the project/step/phase/node tree, with required YAML frontmatter on every canonical entity note.

Treat JSON as support-only in this direction:
- schema references
- parser fixtures / tests
- optional snapshots or exports
- legacy prototype compatibility

Do **not** treat `graph.json` as the durable source of truth for md-first runs.

## Read these references first

- `references/md-first-vnext-spec.md` — canonical md-first protocol
- `references/obsidian-plugin-mvp-spec.md` — deterministic Obsidian client expectations
- `examples/md-first-minimal/` — smallest canonical markdown example

## Legacy prototype status

This repo still includes a legacy `graph.json` CLI prototype in `scripts/graph_task.py`.
That prototype is useful for learning, migration, and fixture generation, but it is no longer the primary contract.

If you touch legacy JSON paths, label them clearly as one of:
- legacy prototype behavior
- migration aid
- derived snapshot / export

## Current operating model

- Canonical md-first discovery comes from folder structure + required frontmatter.
- Use one shared minimal status vocabulary everywhere: `pending | active | done | blocked | cancelled`.
- Preserve history; prefer append-only logs/results over destructive rewrites.
- Keep tree/containment semantics primary; use graph relationships as secondary metadata.
- Validate frontmatter and filesystem reachability before claiming the structure is sound.

## Recommended workflow

1. Start from `references/md-first-vnext-spec.md` or `examples/md-first-minimal/`.
2. Create or edit canonical markdown entities (`index.md`, node notes, result notes) in the md-first folder layout.
3. Keep required frontmatter valid and stable.
4. Record outcomes in append-only result notes and log files.
5. Use Obsidian/plugin surfaces as working clients for the markdown tree.
6. If you use the legacy CLI or export paths, describe them as derived/non-canonical.

## Legacy CLI note

The bundled CLI remains:

```bash
python3 scripts/graph_task.py <command> ...
```

But unless a task is explicitly about the legacy prototype, assume markdown-canonical work is the real target.

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
