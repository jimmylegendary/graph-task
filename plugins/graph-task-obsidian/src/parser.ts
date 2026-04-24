import { App, TFile, TFolder, TAbstractFile } from 'obsidian';

export type EntityType = 'project' | 'step' | 'phase' | 'node' | 'result';

export interface Entity {
  type: EntityType;
  id: string;
  title: string;
  status: string;
  file: TFile;
  folderPath: string | null;
  frontmatter: Record<string, unknown>;
  children: Entity[];
  issues: string[];
  extras?: Record<string, unknown>;
}

export interface ScanResult {
  projects: Entity[];
  globalIssues: string[];
}

const REQUIRED_COMMON = ['graphTaskVersion', 'entityType', 'id', 'status'] as const;

function getFrontmatter(app: App, file: TFile): Record<string, unknown> | null {
  const cache = app.metadataCache.getFileCache(file);
  const fm = cache?.frontmatter;
  if (!fm) return null;
  const copy: Record<string, unknown> = {};
  for (const k of Object.keys(fm)) {
    if (k === 'position') continue;
    copy[k] = (fm as Record<string, unknown>)[k];
  }
  return copy;
}

function findChildFolder(folder: TFolder, name: string): TFolder | null {
  for (const child of folder.children) {
    if (child instanceof TFolder && child.name === name) return child;
  }
  return null;
}

function findIndexFile(folder: TFolder): TFile | null {
  for (const child of folder.children) {
    if (child instanceof TFile && child.name === 'index.md') return child;
  }
  return null;
}

function listMdFiles(folder: TFolder): TFile[] {
  const out: TFile[] = [];
  for (const child of folder.children) {
    if (child instanceof TFile && child.extension === 'md' && child.name !== 'index.md') {
      out.push(child);
    }
  }
  out.sort((a, b) => a.name.localeCompare(b.name));
  return out;
}

function checkCommonFields(fm: Record<string, unknown>, expectedType: EntityType, expectedId: string | null): string[] {
  const issues: string[] = [];
  for (const key of REQUIRED_COMMON) {
    if (fm[key] === undefined || fm[key] === null || fm[key] === '') {
      issues.push(`missing required frontmatter field: ${key}`);
    }
  }
  if (fm.entityType && fm.entityType !== expectedType) {
    issues.push(`entityType mismatch: got '${String(fm.entityType)}', expected '${expectedType}'`);
  }
  if (expectedId && fm.id && fm.id !== expectedId) {
    issues.push(`id mismatch: frontmatter id '${String(fm.id)}' does not match location '${expectedId}'`);
  }
  return issues;
}

function entityFromIndex(
  app: App,
  folder: TFolder,
  expectedType: EntityType,
): Entity | null {
  const indexFile = findIndexFile(folder);
  if (!indexFile) return null;
  const fm = getFrontmatter(app, indexFile);
  if (!fm) return null;
  if (fm.entityType !== expectedType) return null;

  const id = typeof fm.id === 'string' ? fm.id : folder.name;
  const title = typeof fm.title === 'string' ? fm.title : id;
  const status = typeof fm.status === 'string' ? fm.status : 'unknown';
  const issues = checkCommonFields(fm, expectedType, folder.name);

  return {
    type: expectedType,
    id,
    title,
    status,
    file: indexFile,
    folderPath: folder.path,
    frontmatter: fm,
    children: [],
    issues,
  };
}

function entityFromLeafFile(
  app: App,
  file: TFile,
  expectedType: EntityType,
): Entity | null {
  const fm = getFrontmatter(app, file);
  if (!fm) return null;
  if (fm.entityType !== expectedType) return null;

  const expectedId = file.basename;
  const id = typeof fm.id === 'string' ? fm.id : expectedId;
  const title = typeof fm.title === 'string' ? fm.title : id;
  const status = typeof fm.status === 'string' ? fm.status : 'unknown';
  const issues = checkCommonFields(fm, expectedType, expectedId);

  return {
    type: expectedType,
    id,
    title,
    status,
    file,
    folderPath: null,
    frontmatter: fm,
    children: [],
    issues,
  };
}

function buildPhase(app: App, phaseFolder: TFolder): Entity {
  const phase = entityFromIndex(app, phaseFolder, 'phase');
  if (!phase) {
    // Synthesize a placeholder so the tree still shows the gap.
    return {
      type: 'phase',
      id: phaseFolder.name,
      title: phaseFolder.name,
      status: 'unknown',
      file: (findIndexFile(phaseFolder) as TFile) ?? (phaseFolder as unknown as TFile),
      folderPath: phaseFolder.path,
      frontmatter: {},
      children: [],
      issues: ['phase folder missing valid index.md with entityType: phase'],
    };
  }

  const nodesFolder = findChildFolder(phaseFolder, 'nodes');
  if (nodesFolder) {
    for (const f of listMdFiles(nodesFolder)) {
      const node = entityFromLeafFile(app, f, 'node');
      if (node) {
        phase.children.push(node);
      } else {
        phase.issues.push(`node file '${f.name}' missing valid frontmatter (entityType: node)`);
      }
    }
  }

  const resultsFolder = findChildFolder(phaseFolder, 'results');
  if (resultsFolder) {
    for (const f of listMdFiles(resultsFolder)) {
      const result = entityFromLeafFile(app, f, 'result');
      if (result) {
        const nodeId = typeof result.frontmatter.nodeId === 'string' ? (result.frontmatter.nodeId as string) : null;
        if (!nodeId) {
          result.issues.push('result is missing nodeId');
        }
        phase.children.push(result);
      } else {
        phase.issues.push(`result file '${f.name}' missing valid frontmatter (entityType: result)`);
      }
    }
  }

  // Phase-level coherence checks.
  const commitCount = phase.children.filter((c) => c.type === 'phase').length;
  if (commitCount > 0) {
    phase.issues.push('unexpected nested phase inside phase folder');
  }

  return phase;
}

function buildStep(app: App, stepFolder: TFolder): Entity {
  const step = entityFromIndex(app, stepFolder, 'step');
  if (!step) {
    return {
      type: 'step',
      id: stepFolder.name,
      title: stepFolder.name,
      status: 'unknown',
      file: (findIndexFile(stepFolder) as TFile) ?? (stepFolder as unknown as TFile),
      folderPath: stepFolder.path,
      frontmatter: {},
      children: [],
      issues: ['step folder missing valid index.md with entityType: step'],
    };
  }

  const phasesFolder = findChildFolder(stepFolder, 'phases');
  if (phasesFolder) {
    const phaseFolders: TFolder[] = [];
    for (const child of phasesFolder.children) {
      if (child instanceof TFolder) phaseFolders.push(child);
    }
    phaseFolders.sort((a, b) => a.name.localeCompare(b.name));

    let commitPhases = 0;
    for (const pf of phaseFolders) {
      const phase = buildPhase(app, pf);
      if (phase.frontmatter.phaseType === 'commit') commitPhases += 1;
      step.children.push(phase);
    }
    if (commitPhases > 1) {
      step.issues.push(`step contains ${commitPhases} commit phases (expected at most 1)`);
    }
  }

  return step;
}

function buildProject(app: App, projectFolder: TFolder): Entity {
  const project = entityFromIndex(app, projectFolder, 'project');
  if (!project) {
    // Should not happen — caller already confirmed project index.
    throw new Error(`buildProject called on non-project folder ${projectFolder.path}`);
  }

  const stepsFolder = findChildFolder(projectFolder, 'steps');
  if (stepsFolder) {
    const stepFolders: TFolder[] = [];
    for (const child of stepsFolder.children) {
      if (child instanceof TFolder) stepFolders.push(child);
    }
    stepFolders.sort((a, b) => a.name.localeCompare(b.name));
    for (const sf of stepFolders) {
      project.children.push(buildStep(app, sf));
    }
  } else {
    project.issues.push("project has no 'steps/' folder");
  }

  return project;
}

export function scanProjects(app: App): ScanResult {
  const projects: Entity[] = [];
  const globalIssues: string[] = [];

  const seenProjectIds = new Set<string>();

  for (const file of app.vault.getMarkdownFiles()) {
    if (file.name !== 'index.md') continue;
    const fm = getFrontmatter(app, file);
    if (!fm) continue;
    if (fm.entityType !== 'project') continue;

    const parent = file.parent;
    if (!(parent instanceof TFolder)) continue;

    const project = buildProject(app, parent);
    if (seenProjectIds.has(project.id)) {
      globalIssues.push(`duplicate project id '${project.id}' at ${parent.path}`);
    }
    seenProjectIds.add(project.id);

    projects.push(project);
  }

  projects.sort((a, b) => a.id.localeCompare(b.id));
  return { projects, globalIssues };
}

export function collectIssues(entity: Entity, out: string[] = []): string[] {
  for (const issue of entity.issues) {
    out.push(`[${entity.type} ${entity.id}] ${issue}`);
  }
  for (const child of entity.children) collectIssues(child, out);
  return out;
}
