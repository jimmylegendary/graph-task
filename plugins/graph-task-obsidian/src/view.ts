import { ItemView, WorkspaceLeaf, setIcon, TFile } from 'obsidian';
import type GraphTaskPlugin from './main';
import { scanProjects, Entity, collectIssues } from './parser';

export const VIEW_TYPE_GRAPH_TASK = 'graph-task-explorer';

const TYPE_ICONS: Record<Entity['type'], string> = {
  project: 'folder-tree',
  step: 'list-ordered',
  phase: 'git-branch',
  node: 'circle-dot',
  result: 'check-circle-2',
};

export class GraphTaskView extends ItemView {
  plugin: GraphTaskPlugin;
  private collapsed: Set<string> = new Set();

  constructor(leaf: WorkspaceLeaf, plugin: GraphTaskPlugin) {
    super(leaf);
    this.plugin = plugin;
  }

  getViewType(): string {
    return VIEW_TYPE_GRAPH_TASK;
  }

  getDisplayText(): string {
    return 'graph-task explorer';
  }

  getIcon(): string {
    return 'folder-tree';
  }

  async onOpen(): Promise<void> {
    this.render();
  }

  async onClose(): Promise<void> {
    // no-op
  }

  refresh(): void {
    this.render();
  }

  private render(): void {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass('graph-task-view');

    // Toolbar
    const toolbar = container.createEl('div', { cls: 'graph-task-toolbar' });
    const refreshBtn = toolbar.createEl('button', { cls: 'graph-task-btn', text: 'Refresh' });
    setIcon(refreshBtn.createSpan({ cls: 'graph-task-btn-icon' }), 'refresh-cw');
    refreshBtn.addEventListener('click', () => this.refresh());

    const expandBtn = toolbar.createEl('button', { cls: 'graph-task-btn', text: 'Expand all' });
    expandBtn.addEventListener('click', () => {
      this.collapsed.clear();
      this.render();
    });

    const collapseBtn = toolbar.createEl('button', { cls: 'graph-task-btn', text: 'Collapse all' });

    // Warning banner (per obsidian-plugin-mvp-spec concurrency note)
    const warn = container.createEl('div', { cls: 'graph-task-warn' });
    warn.setText('Structural edits are safest with one active editor per project. MVP is read-only.');

    // Scan vault
    const { projects, globalIssues } = scanProjects(this.app);

    if (projects.length === 0) {
      const empty = container.createEl('div', { cls: 'graph-task-empty' });
      empty.createEl('p', {
        text: 'No graph-task projects found in this vault.',
      });
      empty.createEl('p', {
        text: 'A project is any folder containing an index.md with frontmatter entityType: project.',
      });
      return;
    }

    collapseBtn.addEventListener('click', () => {
      this.collapsed.clear();
      for (const p of projects) this.markAllCollapsed(p);
      this.render();
    });

    // Issue panel
    const issueList: string[] = [...globalIssues];
    for (const p of projects) collectIssues(p, issueList);
    if (issueList.length > 0) {
      const issueBox = container.createEl('details', { cls: 'graph-task-issues' });
      issueBox.createEl('summary', { text: `Validation issues (${issueList.length})` });
      const ul = issueBox.createEl('ul');
      for (const i of issueList) ul.createEl('li', { text: i });
    }

    const tree = container.createEl('div', { cls: 'graph-task-tree' });
    for (const project of projects) {
      this.renderEntity(tree, project, 0);
    }
  }

  private markAllCollapsed(entity: Entity): void {
    if (entity.children.length > 0) this.collapsed.add(this.entityKey(entity));
    for (const c of entity.children) this.markAllCollapsed(c);
  }

  private entityKey(entity: Entity): string {
    return `${entity.type}:${entity.file.path}`;
  }

  private renderEntity(parent: HTMLElement, entity: Entity, depth: number): void {
    const row = parent.createEl('div', { cls: 'graph-task-row' });
    row.style.paddingLeft = `${depth * 14}px`;

    const hasChildren = entity.children.length > 0;
    const key = this.entityKey(entity);
    const isCollapsed = this.collapsed.has(key);

    const caret = row.createEl('span', { cls: 'graph-task-caret' });
    if (hasChildren) {
      setIcon(caret, isCollapsed ? 'chevron-right' : 'chevron-down');
      caret.addEventListener('click', (e) => {
        e.stopPropagation();
        if (isCollapsed) this.collapsed.delete(key);
        else this.collapsed.add(key);
        this.render();
      });
    } else {
      caret.addClass('graph-task-caret-empty');
    }

    const icon = row.createEl('span', { cls: 'graph-task-type-icon' });
    setIcon(icon, TYPE_ICONS[entity.type]);

    const label = row.createEl('span', {
      cls: 'graph-task-label',
      text: `${entity.type}: ${entity.id}`,
    });

    // Badges
    const badges = row.createEl('span', { cls: 'graph-task-badges' });
    badges.createEl('span', {
      cls: `graph-task-badge status-${entity.status}`,
      text: entity.status,
    });
    if (entity.type === 'phase' && typeof entity.frontmatter.phaseType === 'string') {
      badges.createEl('span', {
        cls: 'graph-task-badge phase-type',
        text: String(entity.frontmatter.phaseType),
      });
    }
    if (entity.type === 'phase') {
      const resultCount = entity.children.filter((c) => c.type === 'result').length;
      if (resultCount > 0) {
        badges.createEl('span', {
          cls: 'graph-task-badge results',
          text: `${resultCount} result${resultCount === 1 ? '' : 's'}`,
        });
      }
    }
    if (entity.issues.length > 0) {
      badges.createEl('span', {
        cls: 'graph-task-badge issues',
        text: `${entity.issues.length} issue${entity.issues.length === 1 ? '' : 's'}`,
      });
    }

    const open = (newLeaf: boolean) => {
      this.openEntity(entity.file, newLeaf);
    };

    label.addEventListener('click', () => open(false));
    icon.addEventListener('click', () => open(false));
    row.addEventListener('auxclick', (e) => {
      if (e.button === 1) {
        e.preventDefault();
        open(true);
      }
    });

    if (hasChildren && !isCollapsed) {
      for (const child of entity.children) {
        this.renderEntity(parent, child, depth + 1);
      }
    }
  }

  private async openEntity(file: TFile, newLeaf: boolean): Promise<void> {
    const leaf = this.app.workspace.getLeaf(newLeaf ? 'tab' : false);
    await leaf.openFile(file);
  }
}
