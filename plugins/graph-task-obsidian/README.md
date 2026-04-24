# graph-task Obsidian plugin MVP

This is the first tree-first Obsidian plugin for the md-first `graph-task` direction.

## What it does
- scans the current vault for graph-task projects
- detects a project when a folder contains `index.md` with `entityType: project`
- renders a side-panel tree:
  - Project
  - Step
  - Phase
  - Node
  - Result
- shows compact badges for status, phase type, result count, and validation issues
- lets you click an item to open the canonical markdown file
- includes a refresh command / button
- shows a validation issue panel instead of failing silently when structure is broken

## Current scope
This MVP is intentionally read-only.

Included:
- parse md-first project structure
- inspect the tree in Obsidian
- open canonical markdown files
- refresh the parsed state
- surface validation issues

Not included yet:
- create or edit entities from the plugin
- lock / lease handling
- graph rendering
- conflict resolution
- rich detail pane

## Build
From this plugin folder:

```bash
npm install
npm run typecheck
npm run build
```

## Smoke test against the sample project
From this plugin folder:

```bash
node scripts/smoke-parse.mjs
```

Expected output includes:
- `project: project-alpha`
- `step: step-1`
- `phase: phase-diverge-1`
- `node: node-compare-layout`
- `result: result-0001`
- final line: `OK: projects=1 steps=1 phases=1 nodes=1 results=1`

## Load into Obsidian
### Option A — use the sample vault directly
1. Open Obsidian.
2. Choose **Open folder as vault**.
3. Select `examples/md-first-minimal/` from this repo.
4. Create the community plugin folder inside that vault if needed:
   - `<vault>/.obsidian/plugins/graph-task-obsidian/`
5. Copy these plugin files into that folder:
   - `manifest.json`
   - `main.js`
   - `styles.css`
6. In Obsidian:
   - Settings → Community plugins
   - turn off Restricted mode
   - enable **Graph-Task Explorer**
7. Click the ribbon icon or run the command:
   - `Graph-Task Explorer: Open project explorer`

### Option B — use your real vault
If your real vault contains md-first graph-task project folders with the same structure, install the plugin the same way and open the explorer.

## Expected first visual result in Obsidian
If you load `examples/md-first-minimal/`, the plugin should show a tree roughly like:

```text
project: project-alpha [active]
  step: step-1 [active]
    phase: phase-diverge-1 [done] [diverge] [1 result]
      node: node-compare-layout [done]
      result: result-0001 [done]
```

When you click each row, Obsidian should open the corresponding canonical markdown note.

## Validation behavior
The plugin currently flags issues such as:
- missing required frontmatter
- wrong `entityType`
- id mismatch with folder/file name
- missing `steps/` folder on a project
- multiple commit phases inside one step
- result missing `nodeId`

## Next likely steps
- detail pane for selected entity
- create entity commands
- status mutation commands
- validator shared with CLI/runtime
- lightweight lock / lease awareness
