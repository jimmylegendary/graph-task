#!/usr/bin/env node
// Standalone smoke test: emulate enough of Obsidian's TFile/TFolder/metadataCache
// to exercise parser.ts logic against examples/md-first-minimal/ without loading
// a real Obsidian vault. Ensures the parser's expected shape and frontmatter
// assumptions stay aligned with the sample data.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, basename, relative, dirname } from 'node:path';

const EXAMPLE_ROOT = new URL('../../../examples/md-first-minimal', import.meta.url).pathname;

function parseFrontmatter(content) {
  if (!content.startsWith('---\n')) return null;
  const end = content.indexOf('\n---', 4);
  if (end === -1) return null;
  const yaml = content.slice(4, end);
  const fm = {};
  for (const raw of yaml.split('\n')) {
    const line = raw.replace(/\s+$/, '');
    if (!line || line.startsWith('#')) continue;
    const m = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (!m) continue;
    let value = m[2];
    if (value === '') value = null;
    else if (/^\d+$/.test(value)) value = Number(value);
    else if (value === 'true') value = true;
    else if (value === 'false') value = false;
    fm[m[1]] = value;
  }
  return fm;
}

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (name.endsWith('.md')) out.push(full);
  }
  return out;
}

const files = walk(EXAMPLE_ROOT);
const projects = [];
for (const path of files) {
  if (basename(path) !== 'index.md') continue;
  const fm = parseFrontmatter(readFileSync(path, 'utf8'));
  if (!fm || fm.entityType !== 'project') continue;
  projects.push({ path, fm, root: dirname(path) });
}

if (projects.length === 0) {
  console.error('FAIL: no projects discovered');
  process.exit(1);
}

let stepCount = 0;
let phaseCount = 0;
let nodeCount = 0;
let resultCount = 0;
for (const p of projects) {
  console.log(`project: ${p.fm.id}  status=${p.fm.status}  at ${relative(EXAMPLE_ROOT, p.path)}`);
  const stepsDir = join(p.root, 'steps');
  try { statSync(stepsDir); } catch { continue; }
  for (const stepName of readdirSync(stepsDir)) {
    const stepDir = join(stepsDir, stepName);
    if (!statSync(stepDir).isDirectory()) continue;
    const stepIdx = join(stepDir, 'index.md');
    const stepFm = parseFrontmatter(readFileSync(stepIdx, 'utf8'));
    if (stepFm?.entityType !== 'step') {
      console.error(`FAIL: expected step at ${stepIdx}`);
      process.exit(1);
    }
    stepCount++;
    console.log(`  step: ${stepFm.id}  status=${stepFm.status}`);
    const phasesDir = join(stepDir, 'phases');
    try { statSync(phasesDir); } catch { continue; }
    for (const phaseName of readdirSync(phasesDir)) {
      const phaseDir = join(phasesDir, phaseName);
      if (!statSync(phaseDir).isDirectory()) continue;
      const phaseIdx = join(phaseDir, 'index.md');
      const phaseFm = parseFrontmatter(readFileSync(phaseIdx, 'utf8'));
      if (phaseFm?.entityType !== 'phase') {
        console.error(`FAIL: expected phase at ${phaseIdx}`);
        process.exit(1);
      }
      phaseCount++;
      console.log(`    phase: ${phaseFm.id}  type=${phaseFm.phaseType}  status=${phaseFm.status}`);
      const nodesDir = join(phaseDir, 'nodes');
      try {
        for (const nf of readdirSync(nodesDir)) {
          if (!nf.endsWith('.md')) continue;
          const nfm = parseFrontmatter(readFileSync(join(nodesDir, nf), 'utf8'));
          if (nfm?.entityType !== 'node') {
            console.error(`FAIL: expected node at ${nf}`);
            process.exit(1);
          }
          nodeCount++;
          console.log(`      node: ${nfm.id}  status=${nfm.status}`);
        }
      } catch { /* no nodes dir */ }
      const resultsDir = join(phaseDir, 'results');
      try {
        for (const rf of readdirSync(resultsDir)) {
          if (!rf.endsWith('.md')) continue;
          const rfm = parseFrontmatter(readFileSync(join(resultsDir, rf), 'utf8'));
          if (rfm?.entityType !== 'result') {
            console.error(`FAIL: expected result at ${rf}`);
            process.exit(1);
          }
          if (!rfm.nodeId) {
            console.error(`FAIL: result ${rf} missing nodeId`);
            process.exit(1);
          }
          resultCount++;
          console.log(`      result: ${rfm.id}  nodeId=${rfm.nodeId}`);
        }
      } catch { /* no results dir */ }
    }
  }
}

console.log(`\nOK: projects=${projects.length} steps=${stepCount} phases=${phaseCount} nodes=${nodeCount} results=${resultCount}`);
if (projects.length !== 1 || stepCount !== 1 || phaseCount !== 1 || nodeCount !== 1 || resultCount !== 1) {
  console.error('FAIL: counts do not match expected minimal example (1/1/1/1/1)');
  process.exit(1);
}
