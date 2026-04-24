# graph-task-obsidian (MVP)

Obsidian community plugin that renders the md-first `graph-task` protocol
(`references/md-first-vnext-spec.md`) as a tree view: **Project → Step → Phase → Nodes / Results**.

This is a read-heavy MVP. You can browse, refresh, and click to open the
canonical markdown notes. Writes (scaffold / status / log / result) are
intentionally **out of scope** for this first cut — see *Limitations* below.

## What the plugin does

- Scans every `index.md` in the vault and treats any file whose frontmatter
  has `entityType: project` as a graph-task project root.
- Walks `steps/<step-id>/phases/<phase-id>/{nodes,results}/*.md`, building the
  tree using the folder contract from the md-first spec.
- Shows each entity with compact badges:
  - status (`active`, `done`, `pending`, `blocked`, `cancelled`)
  - phase type for phase rows (`diverge`, `converge`, `verify`, `commit`)
  - result count for phase rows
  - issue count when validation flags the entity
- Click a row (label or icon) to open the underlying note in the main editor.
- Middle-click opens in a new tab.
- A **Refresh** button in the view toolbar and a `graph-task: Refresh projects`
  command force a re-scan. The view also auto-refreshes when Obsidian's
  metadata cache changes.
- Validation surface: a collapsible "Validation issues" panel lists everything
  the parser flagged (missing `index.md`, missing required frontmatter fields,
  `id` / folder-name mismatches, unknown `entityType`, results missing
  `nodeId`, duplicate sibling ids, multiple commit phases in one step).

## How to load it in Obsidian

The plugin is not in the community catalog — load it as a local plugin.

1. Build the bundle (already done during development, but re-run after edits):
   ```bash
   cd plugins/graph-task-obsidian
   npm install
   npm run build
   ```
   This produces `main.js` next to `manifest.json` and `styles.css`.

2. Pick (or create) an Obsidian vault where you want to test. The easiest path
   is to point Obsidian at **a copy of `examples/md-first-minimal/`** as its
   own vault root, but you can also drop the example into any existing vault.

3. Install the plugin into that vault:
   ```bash
   # from the repo root
   mkdir -p "<your-vault>/.obsidian/plugins/graph-task-obsidian"
   cp plugins/graph-task-obsidian/manifest.json \
      plugins/graph-task-obsidian/main.js \
      plugins/graph-task-obsidian/styles.css \
      "<your-vault>/.obsidian/plugins/graph-task-obsidian/"
   ```
   Or symlink the whole folder if you want live rebuilds:
   ```bash
   ln -s "$(pwd)/plugins/graph-task-obsidian" \
         "<your-vault>/.obsidian/plugins/graph-task-obsidian"
   ```

4. In Obsidian:
   - Open *Settings → Community plugins*.
   - If prompted, turn off *Restricted mode / Safe mode*.
   - Click **Reload plugins** (or restart Obsidian).
   - Enable **Graph-Task Explorer** in the installed plugins list.

5. The right sidebar should show a **graph-task explorer** view with a
   `folder-tree` icon. If it doesn't open automatically, run the
   *graph-task: Open project explorer* command from the command palette.

## Testing against `examples/md-first-minimal/`

The example ships with exactly one of each entity type, which is ideal for a
first visual confirmation:

- 1 project (`project-alpha`)
- 1 step (`step-1`)
- 1 phase (`phase-diverge-1`, type `diverge`, status `done`)
- 1 node (`node-compare-layout`)
- 1 result (`result-0001`)

Quickest path:

```bash
# Fastest: open the example directory itself as an Obsidian vault.
# Obsidian will create examples/md-first-minimal/.obsidian on first launch.
#   File → Open vault → Open folder as vault
#   → pick examples/md-first-minimal
```

Then install the plugin into `examples/md-first-minimal/.obsidian/plugins/graph-task-obsidian/`
using the copy/symlink step above, enable it, and you should see:

```
project: project-alpha        [active]
  step: step-1                [active]
    phase: phase-diverge-1    [diverge] [done] [1 result]
      node: node-compare-layout [done]
      result: result-0001     [done]
```

Clicking any row should open the underlying note. Clicking the caret on a row
with children collapses that subtree.

A non-Obsidian smoke test is also included:

```bash
cd plugins/graph-task-obsidian
node scripts/smoke-parse.mjs
```

This runs a minimal re-implementation of the parser's expected shape over the
example and asserts the 1/1/1/1/1 counts. It doesn't exercise the real
`parser.ts` (that one depends on Obsidian's `App`), but it keeps the file
contract honest without booting Obsidian.

## Validation / error surface

The plugin reports structural problems without rewriting files. Current
checks:

- required common frontmatter fields (`graphTaskVersion`, `entityType`, `id`,
  `status`) are present
- `entityType` matches the location (step folder must declare `step`, etc.)
- `id` frontmatter matches the folder or file basename
- every phase folder contains a valid `index.md`
- each result file has a `nodeId`
- a step does not contain more than one commit phase
- no duplicate sibling project ids

If anything fails, the row gets a `N issues` badge and the full list is shown
in the collapsible *Validation issues* panel at the top of the view.

## Limitations (MVP — honest)

- **Read-only.** No scaffold / status / log / result commands yet. The full
  list of safe mutations from `references/obsidian-plugin-mvp-spec.md` is a
  follow-up.
- **No detail / inspector pane.** The tree shows badges; to see full
  frontmatter and body, open the note.
- **No graph rendering.** Intentional — the spec is tree-first.
- **No concurrency / lock awareness.** A banner warns that structural edits
  are safest with one writer per project; the plugin does not enforce it.
- **Obsidian's parsed frontmatter only.** The parser relies on
  `metadataCache`, so files opened before Obsidian finished indexing may show
  as "missing frontmatter" until the cache catches up — hit Refresh.
- **No cross-link validation.** Wiki-link hygiene inside bodies is not
  checked (the spec treats links as navigation aids, not canonical).

## Relationship to the existing JSON-canonical prototype

The JSON-canonical prototype (`scripts/graph_task.py`, Phase 1/2 tooling,
JSON-first tests) is **not modified** by this MVP. It stays the working
reference implementation. This plugin only reads md-first trees and does not
write or convert between the two formats.

## File layout

```
plugins/graph-task-obsidian/
  manifest.json           Obsidian plugin manifest
  package.json            dev deps (obsidian, esbuild, typescript)
  tsconfig.json           strict TS config, DOM + ES2020
  esbuild.config.mjs      bundles src/main.ts → main.js (CJS, externalises obsidian)
  styles.css              tree / badge styling
  src/
    main.ts               plugin entry, commands, ribbon, view activation
    parser.ts             vault-scan + per-entity validation
    view.ts               ItemView: toolbar, warn banner, issue panel, tree
  scripts/
    smoke-parse.mjs       standalone parser sanity check against the sample
```
