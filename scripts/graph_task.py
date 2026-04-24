#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import uuid
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

STATUS_VALUES = ["pending", "active", "done", "blocked", "cancelled"]
PHASE_TYPES = ["diverge", "converge", "verify", "commit"]
EDGE_TYPES = ["flow", "dependency"]
NODE_TYPES = ["root", "work"]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_paths(path_arg: str) -> tuple[Path, Path]:
    raw = Path(path_arg)
    if raw.suffix == ".json":
        graph_path = raw
        run_dir = raw.parent
    else:
        run_dir = raw
        graph_path = run_dir / "graph.json"
    return run_dir, graph_path


def slugify_project_dir(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "project"


def run_git(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)


def prepare_repo_backed_run_dir(base_path: str, repo_url: str, branch: str, project_id: str) -> tuple[Path, Path, dict]:
    repo_dir = Path(base_path)
    project_dir_name = slugify_project_dir(project_id)

    if repo_dir.exists() and repo_dir.is_file():
        raise SystemExit(f"Repo checkout path must be a directory: {repo_dir}")

    if not repo_dir.exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            run_git(["git", "clone", "--branch", branch, repo_url, str(repo_dir)])
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise SystemExit(f"Failed to clone repo {repo_url}: {message}")
    else:
        git_dir = repo_dir / ".git"
        if not git_dir.exists():
            raise SystemExit(f"Checkout path exists but is not a git repo: {repo_dir}")
        try:
            existing_origin = run_git(["git", "remote", "get-url", "origin"], cwd=repo_dir).stdout.strip()
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise SystemExit(f"Failed to inspect repo origin at {repo_dir}: {message}")
        if existing_origin != repo_url:
            raise SystemExit(
                f"Repo origin mismatch at {repo_dir}: expected {repo_url}, found {existing_origin}"
            )
        try:
            run_git(["git", "fetch", "origin", branch], cwd=repo_dir)
            run_git(["git", "checkout", branch], cwd=repo_dir)
            run_git(["git", "pull", "--ff-only", "origin", branch], cwd=repo_dir)
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise SystemExit(f"Failed to refresh repo {repo_dir}: {message}")

    run_dir = repo_dir / project_dir_name
    graph_path = run_dir / "graph.json"
    repo_meta = {
        "url": repo_url,
        "branch": branch,
        "projectDir": project_dir_name,
        "checkoutPath": str(repo_dir),
    }
    return run_dir, graph_path, repo_meta


def git_error(exc: subprocess.CalledProcessError) -> str:
    return exc.stderr.strip() or exc.stdout.strip() or str(exc)


def project_repo_meta(data: dict) -> dict | None:
    return project(data).get("repo")


def resolve_repo_checkout_dir(run_dir: Path, data: dict) -> tuple[Path, dict]:
    repo_meta = project_repo_meta(data)
    if not repo_meta:
        raise SystemExit("This graph-task run is not repo-backed. Re-initialize with --repo-url first.")

    checkout_path = repo_meta.get("checkoutPath")
    if checkout_path:
        repo_dir = Path(checkout_path)
    else:
        repo_dir = run_dir.parent

    if not (repo_dir / ".git").exists():
        raise SystemExit(f"Repo checkout not found at {repo_dir}")
    return repo_dir, repo_meta


def ensure_clean_repo(repo_dir: Path) -> None:
    try:
        status = run_git(["git", "status", "--porcelain"], cwd=repo_dir).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Failed to inspect repo status: {git_error(exc)}")
    if status:
        raise SystemExit("Repo has uncommitted changes. Commit/stash them before pulling.")


def render_repo_status(repo_dir: Path, repo_meta: dict) -> str:
    branch = repo_meta.get("branch", "main")
    lines = [
        f"repo: {repo_dir}",
        f"origin: {repo_meta.get('url', '')}",
        f"branch: {branch}",
    ]
    try:
        lines.append(f"head: {run_git(['git', 'rev-parse', '--short', 'HEAD'], cwd=repo_dir).stdout.strip()}")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Failed to read HEAD: {git_error(exc)}")

    try:
        dirty = run_git(["git", "status", "--porcelain"], cwd=repo_dir).stdout.strip().splitlines()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Failed to read repo status: {git_error(exc)}")
    lines.append(f"dirty: {'yes' if dirty else 'no'}")
    if dirty:
        lines.append("changes:")
        lines.extend(f"- {line}" for line in dirty[:20])
        if len(dirty) > 20:
            lines.append(f"- ... ({len(dirty) - 20} more)")

    try:
        run_git(["git", "fetch", "origin", branch], cwd=repo_dir)
        local_head = run_git(["git", "rev-parse", "HEAD"], cwd=repo_dir).stdout.strip()
        remote_head = run_git(["git", "rev-parse", f"origin/{branch}"], cwd=repo_dir).stdout.strip()
        base_head = run_git(["git", "merge-base", "HEAD", f"origin/{branch}"], cwd=repo_dir).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Failed to compare local/remote branch state: {git_error(exc)}")

    if local_head == remote_head:
        sync_state = "in-sync"
    elif local_head == base_head:
        sync_state = "behind"
    elif remote_head == base_head:
        sync_state = "ahead"
    else:
        sync_state = "diverged"
    lines.append(f"sync: {sync_state}")
    return "\n".join(lines) + "\n"


def git_commit_all(repo_dir: Path, message: str) -> bool:
    try:
        dirty = run_git(["git", "status", "--porcelain"], cwd=repo_dir).stdout.strip()
        if not dirty:
            return False
        run_git(["git", "add", "-A"], cwd=repo_dir)
        run_git(["git", "commit", "-m", message], cwd=repo_dir)
        return True
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Failed to commit repo changes: {git_error(exc)}")


def git_pull_ff_only(repo_dir: Path, branch: str) -> None:
    ensure_clean_repo(repo_dir)
    try:
        run_git(["git", "fetch", "origin", branch], cwd=repo_dir)
        run_git(["git", "checkout", branch], cwd=repo_dir)
        run_git(["git", "pull", "--ff-only", "origin", branch], cwd=repo_dir)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Failed to pull latest changes: {git_error(exc)}")


def git_push(repo_dir: Path, branch: str) -> None:
    try:
        run_git(["git", "push", "origin", branch], cwd=repo_dir)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Failed to push changes: {git_error(exc)}")


def load_graph(path_arg: str) -> tuple[Path, Path, dict]:
    run_dir, graph_path = resolve_paths(path_arg)
    if not graph_path.exists():
        raise SystemExit(f"Graph file not found: {graph_path}")
    with graph_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return run_dir, graph_path, data


def save_graph(graph_path: Path, data: dict) -> None:
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    with graph_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ensure_status(value: str) -> str:
    if value not in STATUS_VALUES:
        raise SystemExit(f"Invalid status '{value}'. Allowed: {', '.join(STATUS_VALUES)}")
    return value


def ensure_unique_id(items: list[dict], item_id: str, label: str) -> None:
    if any(item.get("id") == item_id for item in items):
        raise SystemExit(f"Duplicate {label} id: {item_id}")


def project(data: dict) -> dict:
    if "project" not in data:
        raise SystemExit("Invalid graph: missing top-level 'project'")
    return data["project"]


def iter_steps(data: dict):
    for step in project(data).get("steps", []):
        yield step


def iter_phases(data: dict):
    for step in iter_steps(data):
        for phase in step.get("phases", []):
            yield step, phase


def iter_nodes(data: dict):
    for step, phase in iter_phases(data):
        for node in phase.get("nodes", []):
            yield step, phase, node


def find_step(data: dict, step_id: str) -> dict:
    matches = [step for step in iter_steps(data) if step.get("id") == step_id]
    if not matches:
        raise SystemExit(f"Step not found: {step_id}")
    if len(matches) > 1:
        raise SystemExit(f"Step id is not unique: {step_id}")
    return matches[0]


def find_phase(data: dict, phase_id: str) -> tuple[dict, dict]:
    matches = [(step, phase) for step, phase in iter_phases(data) if phase.get("id") == phase_id]
    if not matches:
        raise SystemExit(f"Phase not found: {phase_id}")
    if len(matches) > 1:
        raise SystemExit(f"Phase id is not unique: {phase_id}")
    return matches[0]


def find_node(data: dict, node_id: str) -> tuple[dict, dict, dict]:
    matches = [(step, phase, node) for step, phase, node in iter_nodes(data) if node.get("id") == node_id]
    if not matches:
        raise SystemExit(f"Node not found: {node_id}")
    if len(matches) > 1:
        raise SystemExit(f"Node id is not unique: {node_id}")
    return matches[0]


def append_result(node: dict, expected: str, actual: str, status: str, artifacts: list[str], notes: str | None) -> dict:
    results = node.setdefault("results", [])
    result = {
        "id": f"result-{uuid.uuid4().hex[:10]}",
        "nodeId": node["id"],
        "expected": expected,
        "actual": actual,
        "status": status,
        "artifacts": artifacts,
        "at": now_iso(),
    }
    if notes:
        result["notes"] = notes
    results.append(result)
    node["status"] = status
    return result


def parse_artifacts(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def render_summary(data: dict) -> str:
    proj = project(data)
    lines = [
        f"# {proj.get('title', proj.get('id', 'project'))}",
        "",
        f"- projectId: `{proj.get('id', '')}`",
        f"- status: `{proj.get('status', 'pending')}`",
        f"- goal: {proj.get('goal', '')}",
        f"- description: {proj.get('description', '')}",
        f"- steps: {len(proj.get('steps', []))}",
        "",
        "## Steps",
    ]

    for step in proj.get("steps", []):
        lines.extend(
            [
                f"- `{step['id']}` [{step.get('stepType', '')}] status=`{step.get('status', 'pending')}`",
                f"  - description: {step.get('description', '')}",
                f"  - phases: {len(step.get('phases', []))}",
            ]
        )
        for phase in step.get("phases", []):
            lines.extend(
                [
                    f"    - phase `{phase['id']}` [{phase.get('phaseType', '')}] status=`{phase.get('status', 'pending')}`",
                    f"      - description: {phase.get('description', '')}",
                    f"      - nodes: {len(phase.get('nodes', []))}",
                    f"      - edges: {len(phase.get('edges', []))}",
                ]
            )
            for node in phase.get("nodes", []):
                lines.append(
                    f"        - node `{node['id']}` [{node.get('nodeType', '')}] status=`{node.get('status', 'pending')}` — {node.get('title', '')}"
                )
                latest = node.get("results", [])[-1] if node.get("results") else None
                if latest:
                    lines.extend(
                        [
                            f"          - latestResult: `{latest.get('status', '')}` at {latest.get('at', '')}",
                            f"          - expected: {latest.get('expected', '')}",
                            f"          - actual: {latest.get('actual', '')}",
                        ]
                    )
                    if latest.get("notes"):
                        lines.append(f"          - notes: {latest['notes']}")
                    if latest.get("artifacts"):
                        lines.append(f"          - artifacts: {', '.join(latest['artifacts'])}")
        if step.get("phaseEdges"):
            lines.append("  - phaseEdges:")
            for phase_edge in step["phaseEdges"]:
                lines.append(
                    f"    - `{phase_edge['fromPhaseId']}` -> `{phase_edge['toPhaseId']}`"
                )

    lines.extend(["", "## Step edges"])
    if proj.get("stepEdges"):
        for edge in proj["stepEdges"]:
            lines.append(f"- `{edge['fromStepId']}` -> `{edge['toStepId']}`")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_summary(run_dir: Path, data: dict) -> Path:
    summary_path = run_dir / "summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_summary(data), encoding="utf-8")
    return summary_path


def obsidian_frontmatter(fields: dict[str, str]) -> list[str]:
    lines = ["---"]
    for key, value in fields.items():
        escaped = str(value).replace('"', '\\"')
        lines.append(f'{key}: "{escaped}"')
    lines.extend(["---", ""])
    return lines


def obsidian_link(path_without_suffix: str, alias: str | None = None) -> str:
    if alias:
        return f"[[{path_without_suffix}|{alias}]]"
    return f"[[{path_without_suffix}]]"


def obsidian_step_note_name(step: dict) -> str:
    return step["id"]


def obsidian_phase_note_name(step: dict, phase: dict) -> str:
    return f"{step['id']}__{phase['id']}"


def obsidian_node_note_name(step: dict, phase: dict, node: dict) -> str:
    return f"{step['id']}__{phase['id']}__{node['id']}"


def format_obsidian_result(result: dict) -> list[str]:
    lines = [
        f"### Result `{result.get('id', '')}`",
        f"- status: `{result.get('status', '')}`",
        f"- at: `{result.get('at', '')}`",
        f"- expected: {result.get('expected', '')}",
        f"- actual: {result.get('actual', '')}",
    ]
    if result.get("notes"):
        lines.append(f"- notes: {result['notes']}")
    if result.get("artifacts"):
        lines.append(f"- artifacts: {', '.join(result['artifacts'])}")
    lines.append("")
    return lines


def render_obsidian_index(data: dict) -> str:
    proj = project(data)
    lines = [
        "# graph-task Obsidian export",
        "",
        f"- project: {obsidian_link(f'projects/{proj['id']}', proj.get('title', proj['id']))}",
        f"- steps: {len(proj.get('steps', []))}",
        f"- exportedAt: `{now_iso()}`",
        "",
        "This vault is a projection of `graph.json`. The canonical state remains the graph-task run.",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_obsidian_project(proj: dict) -> str:
    lines = obsidian_frontmatter(
        {
            "graphTaskEntityType": "project",
            "graphTaskId": proj["id"],
            "status": proj.get("status", "pending"),
        }
    )
    lines.extend(
        [
            f"# {proj.get('title', proj['id'])}",
            "",
            f"- projectId: `{proj['id']}`",
            f"- status: `{proj.get('status', 'pending')}`",
            f"- goal: {proj.get('goal', '')}",
            f"- description: {proj.get('description', '')}",
            "",
            "## Steps",
        ]
    )

    for step in proj.get("steps", []):
        lines.append(
            f"- {obsidian_link(f'steps/{obsidian_step_note_name(step)}', step['id'])} [{step.get('stepType', '')}] status=`{step.get('status', 'pending')}`"
        )

    lines.extend(["", "## Step edges"])
    if proj.get("stepEdges"):
        step_lookup = {step["id"]: step for step in proj.get("steps", [])}
        for edge in proj["stepEdges"]:
            from_step = step_lookup.get(edge["fromStepId"], {"id": edge["fromStepId"]})
            to_step = step_lookup.get(edge["toStepId"], {"id": edge["toStepId"]})
            lines.append(
                f"- {obsidian_link(f'steps/{obsidian_step_note_name(from_step)}', edge['fromStepId'])} -> {obsidian_link(f'steps/{obsidian_step_note_name(to_step)}', edge['toStepId'])}"
            )
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def render_obsidian_step(proj: dict, step: dict) -> str:
    lines = obsidian_frontmatter(
        {
            "graphTaskEntityType": "step",
            "graphTaskId": step["id"],
            "projectId": proj["id"],
            "stepType": step.get("stepType", ""),
            "status": step.get("status", "pending"),
        }
    )
    lines.extend(
        [
            f"# Step {step['id']}",
            "",
            f"- project: {obsidian_link(f'projects/{proj['id']}', proj.get('title', proj['id']))}",
            f"- stepType: `{step.get('stepType', '')}`",
            f"- status: `{step.get('status', 'pending')}`",
            f"- description: {step.get('description', '')}",
            "",
            "## Phases",
        ]
    )

    for phase in step.get("phases", []):
        lines.append(
            f"- {obsidian_link(f'phases/{obsidian_phase_note_name(step, phase)}', phase['id'])} [{phase.get('phaseType', '')}] status=`{phase.get('status', 'pending')}`"
        )

    lines.extend(["", "## Phase edges"])
    if step.get("phaseEdges"):
        phase_lookup = {phase["id"]: phase for phase in step.get("phases", [])}
        for edge in step["phaseEdges"]:
            from_phase = phase_lookup.get(edge["fromPhaseId"], {"id": edge["fromPhaseId"]})
            to_phase = phase_lookup.get(edge["toPhaseId"], {"id": edge["toPhaseId"]})
            lines.append(
                f"- {obsidian_link(f'phases/{obsidian_phase_note_name(step, from_phase)}', edge['fromPhaseId'])} -> {obsidian_link(f'phases/{obsidian_phase_note_name(step, to_phase)}', edge['toPhaseId'])}"
            )
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def render_obsidian_phase(proj: dict, step: dict, phase: dict) -> str:
    root_link = None
    lines = obsidian_frontmatter(
        {
            "graphTaskEntityType": "phase",
            "graphTaskId": phase["id"],
            "projectId": proj["id"],
            "stepId": step["id"],
            "phaseType": phase.get("phaseType", ""),
            "status": phase.get("status", "pending"),
            "rootNodeId": phase.get("rootNodeId", ""),
        }
    )
    lines.extend(
        [
            f"# Phase {phase['id']}",
            "",
            f"- project: {obsidian_link(f'projects/{proj['id']}', proj.get('title', proj['id']))}",
            f"- step: {obsidian_link(f'steps/{obsidian_step_note_name(step)}', step['id'])}",
            f"- phaseType: `{phase.get('phaseType', '')}`",
            f"- status: `{phase.get('status', 'pending')}`",
            f"- description: {phase.get('description', '')}",
        ]
    )

    root_node = next((node for node in phase.get("nodes", []) if node.get("id") == phase.get("rootNodeId")), None)
    if root_node:
        root_link = obsidian_link(
            f"nodes/{obsidian_node_note_name(step, phase, root_node)}",
            root_node["id"],
        )
        lines.append(f"- rootNode: {root_link}")

    lines.extend(["", "## Nodes"])
    for node in phase.get("nodes", []):
        lines.append(
            f"- {obsidian_link(f'nodes/{obsidian_node_note_name(step, phase, node)}', node['id'])} [{node.get('nodeType', '')}] status=`{node.get('status', 'pending')}` — {node.get('title', '')}"
        )

    lines.extend(["", "## Node edges"])
    if phase.get("edges"):
        node_lookup = {node["id"]: node for node in phase.get("nodes", [])}
        for edge in phase["edges"]:
            from_node = node_lookup.get(edge["fromNodeId"], {"id": edge["fromNodeId"]})
            to_node = node_lookup.get(edge["toNodeId"], {"id": edge["toNodeId"]})
            lines.append(
                f"- {obsidian_link(f'nodes/{obsidian_node_note_name(step, phase, from_node)}', edge['fromNodeId'])} -[{edge.get('edgeType', '')}]-> {obsidian_link(f'nodes/{obsidian_node_note_name(step, phase, to_node)}', edge['toNodeId'])}"
            )
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def render_obsidian_node(proj: dict, step: dict, phase: dict, node: dict) -> str:
    lines = obsidian_frontmatter(
        {
            "graphTaskEntityType": "node",
            "graphTaskId": node["id"],
            "projectId": proj["id"],
            "stepId": step["id"],
            "phaseId": phase["id"],
            "nodeType": node.get("nodeType", ""),
            "status": node.get("status", "pending"),
        }
    )
    lines.extend(
        [
            f"# Node {node['id']}",
            "",
            f"- project: {obsidian_link(f'projects/{proj['id']}', proj.get('title', proj['id']))}",
            f"- step: {obsidian_link(f'steps/{obsidian_step_note_name(step)}', step['id'])}",
            f"- phase: {obsidian_link(f'phases/{obsidian_phase_note_name(step, phase)}', phase['id'])}",
            f"- nodeType: `{node.get('nodeType', '')}`",
            f"- status: `{node.get('status', 'pending')}`",
            f"- title: {node.get('title', '')}",
            f"- description: {node.get('description', '')}",
            "",
            "## Results",
        ]
    )

    if node.get("results"):
        for result in node.get("results", []):
            lines.extend(format_obsidian_result(result))
    else:
        lines.append("No results recorded yet.\n")

    return "\n".join(lines)


def write_obsidian_export(output_dir: Path, data: dict) -> None:
    proj = project(data)
    for folder in ["projects", "steps", "phases", "nodes"]:
        (output_dir / folder).mkdir(parents=True, exist_ok=True)

    (output_dir / "index.md").write_text(render_obsidian_index(data), encoding="utf-8")
    (output_dir / "projects" / f"{proj['id']}.md").write_text(render_obsidian_project(proj), encoding="utf-8")

    for step in proj.get("steps", []):
        (output_dir / "steps" / f"{obsidian_step_note_name(step)}.md").write_text(
            render_obsidian_step(proj, step),
            encoding="utf-8",
        )
        for phase in step.get("phases", []):
            (output_dir / "phases" / f"{obsidian_phase_note_name(step, phase)}.md").write_text(
                render_obsidian_phase(proj, step, phase),
                encoding="utf-8",
            )
            for node in phase.get("nodes", []):
                (output_dir / "nodes" / f"{obsidian_node_note_name(step, phase, node)}.md").write_text(
                    render_obsidian_node(proj, step, phase, node),
                    encoding="utf-8",
                )


def prepare_obsidian_output_dir(output_dir: Path, force: bool) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        if not force:
            raise SystemExit(f"Output directory already exists and is not empty: {output_dir}. Use --force to overwrite.")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def validate_graph(data: dict) -> list[str]:
    errors: list[str] = []
    proj = data.get("project")
    if not isinstance(proj, dict):
        return ["Missing top-level project object"]

    for field in ["id", "title", "description", "goal", "steps", "stepEdges"]:
        if field not in proj:
            errors.append(f"project missing required field: {field}")

    if proj.get("status") and proj["status"] not in STATUS_VALUES:
        errors.append(f"project has invalid status: {proj['status']}")

    steps = proj.get("steps", []) or []
    step_ids = set()
    for step in steps:
        step_id = step.get("id")
        if not step_id:
            errors.append("step missing id")
            continue
        if step_id in step_ids:
            errors.append(f"duplicate step id: {step_id}")
        step_ids.add(step_id)
        if step.get("projectId") != proj.get("id"):
            errors.append(f"step {step_id} has wrong projectId")
        if step.get("status") and step["status"] not in STATUS_VALUES:
            errors.append(f"step {step_id} has invalid status: {step['status']}")

        phase_ids = set()
        commit_count = 0
        for phase in step.get("phases", []) or []:
            phase_id = phase.get("id")
            if not phase_id:
                errors.append(f"step {step_id} has phase without id")
                continue
            if phase_id in phase_ids:
                errors.append(f"duplicate phase id in step {step_id}: {phase_id}")
            phase_ids.add(phase_id)
            if phase.get("stepId") != step_id:
                errors.append(f"phase {phase_id} has wrong stepId")
            if phase.get("phaseType") not in PHASE_TYPES:
                errors.append(f"phase {phase_id} has invalid phaseType")
            if phase.get("phaseType") == "commit":
                commit_count += 1
            if phase.get("status") and phase["status"] not in STATUS_VALUES:
                errors.append(f"phase {phase_id} has invalid status: {phase['status']}")

            nodes = phase.get("nodes", []) or []
            node_ids = set()
            root_nodes = []
            for node in nodes:
                node_id = node.get("id")
                if not node_id:
                    errors.append(f"phase {phase_id} has node without id")
                    continue
                if node_id in node_ids:
                    errors.append(f"duplicate node id in phase {phase_id}: {node_id}")
                node_ids.add(node_id)
                if node.get("phaseId") != phase_id:
                    errors.append(f"node {node_id} has wrong phaseId")
                if node.get("nodeType") not in NODE_TYPES:
                    errors.append(f"node {node_id} has invalid nodeType")
                if node.get("nodeType") == "root":
                    root_nodes.append(node_id)
                if node.get("status") and node["status"] not in STATUS_VALUES:
                    errors.append(f"node {node_id} has invalid status: {node['status']}")
                for result in node.get("results", []) or []:
                    for required in ["id", "nodeId", "expected", "actual", "status", "at"]:
                        if required not in result:
                            errors.append(f"node {node_id} result missing required field: {required}")
                    if result.get("nodeId") != node_id:
                        errors.append(f"node {node_id} has result with wrong nodeId")
                    if result.get("status") not in STATUS_VALUES:
                        errors.append(f"node {node_id} result has invalid status: {result.get('status')}")

            if len(root_nodes) != 1:
                errors.append(f"phase {phase_id} must contain exactly one root node")
            if phase.get("rootNodeId") not in node_ids:
                errors.append(f"phase {phase_id} rootNodeId does not point to a node in the phase")
            if root_nodes and phase.get("rootNodeId") != root_nodes[0]:
                errors.append(f"phase {phase_id} rootNodeId does not match root node id")

            incoming: dict[str, int] = {node_id: 0 for node_id in node_ids}
            adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
            edge_keys = set()
            for edge in phase.get("edges", []) or []:
                edge_id = edge.get("id")
                if not edge_id:
                    errors.append(f"phase {phase_id} has edge without id")
                if edge.get("phaseId") != phase_id:
                    errors.append(f"edge {edge_id} has wrong phaseId")
                if edge.get("edgeType") not in EDGE_TYPES:
                    errors.append(f"edge {edge_id} has invalid edgeType")
                from_id = edge.get("fromNodeId")
                to_id = edge.get("toNodeId")
                if from_id not in node_ids or to_id not in node_ids:
                    errors.append(f"edge {edge_id} points outside phase {phase_id}")
                    continue
                if from_id == to_id:
                    errors.append(f"edge {edge_id} is a self-loop")
                key = (from_id, to_id, edge.get("edgeType"))
                if key in edge_keys:
                    errors.append(f"phase {phase_id} has duplicate edge {key}")
                edge_keys.add(key)
                incoming[to_id] += 1
                adjacency[from_id].append(to_id)

            root_id = phase.get("rootNodeId")
            if root_id in incoming and incoming[root_id] != 0:
                errors.append(f"phase {phase_id} root node must not have incoming edges")

            if root_id in adjacency:
                seen = set([root_id])
                queue = deque([root_id])
                while queue:
                    current = queue.popleft()
                    for nxt in adjacency[current]:
                        if nxt not in seen:
                            seen.add(nxt)
                            queue.append(nxt)
                unreachable = node_ids - seen
                if unreachable:
                    errors.append(
                        f"phase {phase_id} has nodes unreachable from root: {', '.join(sorted(unreachable))}"
                    )

        if step.get("phases") and len(step.get("phases", [])):
            phase_edge_ids = set()
            for phase_edge in step.get("phaseEdges", []) or []:
                phase_edge_id = phase_edge.get("id")
                if not phase_edge_id:
                    errors.append(f"step {step_id} has phaseEdge without id")
                    continue
                if phase_edge_id in phase_edge_ids:
                    errors.append(f"duplicate phaseEdge id in step {step_id}: {phase_edge_id}")
                phase_edge_ids.add(phase_edge_id)
                if phase_edge.get("stepId") != step_id:
                    errors.append(f"phaseEdge {phase_edge_id} has wrong stepId")
                if phase_edge.get("fromPhaseId") not in phase_ids or phase_edge.get("toPhaseId") not in phase_ids:
                    errors.append(f"phaseEdge {phase_edge_id} points outside step {step_id}")

        if commit_count > 1:
            errors.append(f"step {step_id} has more than one commit phase")

    step_edge_ids = set()
    for step_edge in proj.get("stepEdges", []) or []:
        edge_id = step_edge.get("id")
        if not edge_id:
            errors.append("project has stepEdge without id")
            continue
        if edge_id in step_edge_ids:
            errors.append(f"duplicate stepEdge id: {edge_id}")
        step_edge_ids.add(edge_id)
        if step_edge.get("projectId") != proj.get("id"):
            errors.append(f"stepEdge {edge_id} has wrong projectId")
        if step_edge.get("fromStepId") not in step_ids or step_edge.get("toStepId") not in step_ids:
            errors.append(f"stepEdge {edge_id} points outside project")

    return errors


def cmd_init(args: argparse.Namespace) -> int:
    repo_meta = None
    if args.repo_url:
        run_dir, graph_path, repo_meta = prepare_repo_backed_run_dir(
            args.path,
            args.repo_url,
            args.repo_branch,
            args.id,
        )
    else:
        run_dir, graph_path = resolve_paths(args.path)
    run_dir.mkdir(parents=True, exist_ok=True)
    if graph_path.exists() and not args.force:
        raise SystemExit(f"Graph file already exists: {graph_path}. Use --force to overwrite.")
    data = {
        "project": {
            "id": args.id,
            "title": args.title,
            "description": args.description,
            "goal": args.goal,
            "steps": [],
            "stepEdges": [],
            "status": ensure_status(args.status),
        }
    }
    if repo_meta:
        data["project"]["repo"] = repo_meta
    save_graph(graph_path, data)
    summary_path = write_summary(run_dir, data)
    print(f"Initialized graph-task run at {graph_path}")
    if repo_meta:
        print(f"Repo-backed project directory: {run_dir}")
    print(f"Wrote summary to {summary_path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    if args.format == "json":
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_summary(data))
    return 0


def cmd_add_step(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    proj = project(data)
    ensure_unique_id(proj["steps"], args.id, "step")
    proj["steps"].append(
        {
            "id": args.id,
            "projectId": proj["id"],
            "stepType": args.step_type,
            "description": args.description,
            "phases": [],
            "phaseEdges": [],
            "status": ensure_status(args.status),
        }
    )
    save_graph(graph_path, data)
    write_summary(run_dir, data)
    print(f"Added step {args.id}")
    return 0


def cmd_add_step_edge(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    proj = project(data)
    ensure_unique_id(proj["stepEdges"], args.id, "stepEdge")
    find_step(data, args.from_step)
    find_step(data, args.to_step)
    proj["stepEdges"].append(
        {
            "id": args.id,
            "projectId": proj["id"],
            "fromStepId": args.from_step,
            "toStepId": args.to_step,
        }
    )
    save_graph(graph_path, data)
    write_summary(run_dir, data)
    print(f"Added stepEdge {args.id}")
    return 0


def cmd_add_phase(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    step = find_step(data, args.step_id)
    existing_phase_ids = [phase.get("id") for phase in step.get("phases", [])]
    if args.id in existing_phase_ids:
        raise SystemExit(f"Duplicate phase id in step {args.step_id}: {args.id}")
    if args.phase_type == "commit":
        commit_count = sum(1 for phase in step.get("phases", []) if phase.get("phaseType") == "commit")
        if commit_count >= 1:
            raise SystemExit(f"Step {args.step_id} already has a commit phase")
    root_node_id = args.root_node_id or f"{args.id}-root"
    root_title = args.root_title or "Root"
    root_description = args.root_description or f"Root node for phase {args.id}"
    phase = {
        "id": args.id,
        "stepId": step["id"],
        "phaseType": args.phase_type,
        "description": args.description,
        "rootNodeId": root_node_id,
        "nodes": [
            {
                "id": root_node_id,
                "phaseId": args.id,
                "nodeType": "root",
                "title": root_title,
                "description": root_description,
                "status": ensure_status(args.status),
            }
        ],
        "edges": [],
        "status": ensure_status(args.status),
    }
    step.setdefault("phases", []).append(phase)
    save_graph(graph_path, data)
    write_summary(run_dir, data)
    print(f"Added phase {args.id}")
    return 0


def cmd_add_phase_edge(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    step = find_step(data, args.step_id)
    ensure_unique_id(step.get("phaseEdges", []), args.id, "phaseEdge")
    phase_ids = {phase.get("id") for phase in step.get("phases", [])}
    if args.from_phase not in phase_ids or args.to_phase not in phase_ids:
        raise SystemExit(f"Both phases must belong to step {args.step_id}")
    step.setdefault("phaseEdges", []).append(
        {
            "id": args.id,
            "stepId": step["id"],
            "fromPhaseId": args.from_phase,
            "toPhaseId": args.to_phase,
        }
    )
    save_graph(graph_path, data)
    write_summary(run_dir, data)
    print(f"Added phaseEdge {args.id}")
    return 0


def cmd_add_node(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    step, phase = find_phase(data, args.phase_id)
    ensure_unique_id(phase.get("nodes", []), args.id, "node")
    phase.setdefault("nodes", []).append(
        {
            "id": args.id,
            "phaseId": phase["id"],
            "nodeType": "work",
            "title": args.title,
            "description": args.description,
            "status": ensure_status(args.status),
        }
    )
    save_graph(graph_path, data)
    write_summary(run_dir, data)
    print(f"Added node {args.id}")
    return 0


def cmd_add_edge(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    _, phase = find_phase(data, args.phase_id)
    ensure_unique_id(phase.get("edges", []), args.id, "edge")
    node_ids = {node.get("id") for node in phase.get("nodes", [])}
    if args.from_node not in node_ids or args.to_node not in node_ids:
        raise SystemExit(f"Both nodes must belong to phase {args.phase_id}")
    if args.from_node == args.to_node:
        raise SystemExit("Self-loop edges are not allowed")
    if args.to_node == phase.get("rootNodeId"):
        raise SystemExit("Root node cannot have incoming edges")
    duplicate = any(
        edge.get("fromNodeId") == args.from_node
        and edge.get("toNodeId") == args.to_node
        and edge.get("edgeType") == args.edge_type
        for edge in phase.get("edges", [])
    )
    if duplicate:
        raise SystemExit("Duplicate edge in phase")
    edge = {
        "id": args.id,
        "phaseId": phase["id"],
        "fromNodeId": args.from_node,
        "toNodeId": args.to_node,
        "edgeType": args.edge_type,
    }
    if args.description:
        edge["description"] = args.description
    phase.setdefault("edges", []).append(edge)
    save_graph(graph_path, data)
    write_summary(run_dir, data)
    print(f"Added edge {args.id}")
    return 0


def locate_entity(data: dict, entity_type: str, entity_id: str) -> dict:
    if entity_type == "project":
        proj = project(data)
        if proj.get("id") != entity_id:
            raise SystemExit(f"Project id mismatch: expected {proj.get('id')}, got {entity_id}")
        return proj
    if entity_type == "step":
        return find_step(data, entity_id)
    if entity_type == "phase":
        _, phase = find_phase(data, entity_id)
        return phase
    if entity_type == "node":
        _, _, node = find_node(data, entity_id)
        return node
    raise SystemExit(f"Unsupported entity type: {entity_type}")


def cmd_set_status(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    entity = locate_entity(data, args.entity_type, args.entity_id)
    entity["status"] = ensure_status(args.status)
    save_graph(graph_path, data)
    write_summary(run_dir, data)
    print(f"Set status for {args.entity_type} {args.entity_id} -> {args.status}")
    return 0


def cmd_write_result(args: argparse.Namespace) -> int:
    run_dir, graph_path, data = load_graph(args.path)
    _, phase, node = find_node(data, args.node_id)
    if node.get("nodeType") != "work":
        raise SystemExit("Results can only be written to work nodes")
    artifacts = parse_artifacts(args.artifacts)
    result = append_result(
        node,
        expected=args.expected,
        actual=args.actual,
        status=ensure_status(args.status),
        artifacts=artifacts,
        notes=args.notes,
    )
    save_graph(graph_path, data)
    write_summary(run_dir, data)
    print(f"Recorded result {result['id']} for node {node['id']} in phase {phase['id']}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    _, _, data = load_graph(args.path)
    errors = validate_graph(deepcopy(data))
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALID")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    run_dir, _, data = load_graph(args.path)
    summary_path = write_summary(run_dir, data)
    sys.stdout.write(render_summary(data))
    print(f"Wrote summary to {summary_path}")
    return 0


def cmd_export_obsidian(args: argparse.Namespace) -> int:
    _, _, data = load_graph(args.path)
    output_dir = Path(args.output_dir)
    prepare_obsidian_output_dir(output_dir, force=args.force)
    write_obsidian_export(output_dir, data)
    print(f"Exported Obsidian vault to {output_dir}")
    return 0


def cmd_git_status(args: argparse.Namespace) -> int:
    run_dir, _, data = load_graph(args.path)
    repo_dir, repo_meta = resolve_repo_checkout_dir(run_dir, data)
    sys.stdout.write(render_repo_status(repo_dir, repo_meta))
    return 0


def cmd_git_pull(args: argparse.Namespace) -> int:
    run_dir, _, data = load_graph(args.path)
    repo_dir, repo_meta = resolve_repo_checkout_dir(run_dir, data)
    git_pull_ff_only(repo_dir, repo_meta.get("branch", "main"))
    print(f"Pulled latest changes for {repo_dir}")
    return 0


def cmd_git_push(args: argparse.Namespace) -> int:
    run_dir, _, data = load_graph(args.path)
    repo_dir, repo_meta = resolve_repo_checkout_dir(run_dir, data)
    did_commit = False
    if args.message:
        did_commit = git_commit_all(repo_dir, args.message)
    git_push(repo_dir, repo_meta.get("branch", "main"))
    if did_commit:
        print(f"Committed and pushed changes for {repo_dir}")
    else:
        print(f"Pushed changes for {repo_dir}")
    return 0


def cmd_git_sync(args: argparse.Namespace) -> int:
    run_dir, _, data = load_graph(args.path)
    repo_dir, repo_meta = resolve_repo_checkout_dir(run_dir, data)
    branch = repo_meta.get("branch", "main")
    git_pull_ff_only(repo_dir, branch)
    did_commit = False
    if args.message:
        did_commit = git_commit_all(repo_dir, args.message)
    git_push(repo_dir, branch)
    if did_commit:
        print(f"Pulled, committed, and pushed changes for {repo_dir}")
    else:
        print(f"Pulled and pushed changes for {repo_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal graph-task CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a graph-task run")
    init_parser.add_argument("path")
    init_parser.add_argument("--id", required=True)
    init_parser.add_argument("--title", required=True)
    init_parser.add_argument("--description", required=True)
    init_parser.add_argument("--goal", required=True)
    init_parser.add_argument("--status", default="pending")
    init_parser.add_argument("--repo-url", help="Clone/pull this git repo and create the run under <checkout>/<project-id>/")
    init_parser.add_argument("--repo-branch", default="main")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=cmd_init)

    show_parser = subparsers.add_parser("show", help="Show graph JSON or summary")
    show_parser.add_argument("path")
    show_parser.add_argument("--format", choices=["summary", "json"], default="summary")
    show_parser.set_defaults(func=cmd_show)

    add_step_parser = subparsers.add_parser("add-step", help="Add a step")
    add_step_parser.add_argument("path")
    add_step_parser.add_argument("--id", required=True)
    add_step_parser.add_argument("--step-type", required=True)
    add_step_parser.add_argument("--description", required=True)
    add_step_parser.add_argument("--status", default="pending")
    add_step_parser.set_defaults(func=cmd_add_step)

    add_step_edge_parser = subparsers.add_parser("add-step-edge", help="Add a project-level step edge")
    add_step_edge_parser.add_argument("path")
    add_step_edge_parser.add_argument("--id", required=True)
    add_step_edge_parser.add_argument("--from-step", required=True)
    add_step_edge_parser.add_argument("--to-step", required=True)
    add_step_edge_parser.set_defaults(func=cmd_add_step_edge)

    add_phase_parser = subparsers.add_parser("add-phase", help="Add a phase with an automatic root node")
    add_phase_parser.add_argument("path")
    add_phase_parser.add_argument("--step-id", required=True)
    add_phase_parser.add_argument("--id", required=True)
    add_phase_parser.add_argument("--phase-type", required=True, choices=PHASE_TYPES)
    add_phase_parser.add_argument("--description", required=True)
    add_phase_parser.add_argument("--root-node-id")
    add_phase_parser.add_argument("--root-title")
    add_phase_parser.add_argument("--root-description")
    add_phase_parser.add_argument("--status", default="pending")
    add_phase_parser.set_defaults(func=cmd_add_phase)

    add_phase_edge_parser = subparsers.add_parser("add-phase-edge", help="Add a step-level phase edge")
    add_phase_edge_parser.add_argument("path")
    add_phase_edge_parser.add_argument("--step-id", required=True)
    add_phase_edge_parser.add_argument("--id", required=True)
    add_phase_edge_parser.add_argument("--from-phase", required=True)
    add_phase_edge_parser.add_argument("--to-phase", required=True)
    add_phase_edge_parser.set_defaults(func=cmd_add_phase_edge)

    add_node_parser = subparsers.add_parser("add-node", help="Add a work node to a phase")
    add_node_parser.add_argument("path")
    add_node_parser.add_argument("--phase-id", required=True)
    add_node_parser.add_argument("--id", required=True)
    add_node_parser.add_argument("--title", required=True)
    add_node_parser.add_argument("--description", required=True)
    add_node_parser.add_argument("--status", default="pending")
    add_node_parser.set_defaults(func=cmd_add_node)

    add_edge_parser = subparsers.add_parser("add-edge", help="Add a node edge inside a phase")
    add_edge_parser.add_argument("path")
    add_edge_parser.add_argument("--phase-id", required=True)
    add_edge_parser.add_argument("--id", required=True)
    add_edge_parser.add_argument("--from-node", required=True)
    add_edge_parser.add_argument("--to-node", required=True)
    add_edge_parser.add_argument("--edge-type", required=True, choices=EDGE_TYPES)
    add_edge_parser.add_argument("--description")
    add_edge_parser.set_defaults(func=cmd_add_edge)

    set_status_parser = subparsers.add_parser("set-status", help="Set status on project, step, phase, or node")
    set_status_parser.add_argument("path")
    set_status_parser.add_argument("--entity-type", required=True, choices=["project", "step", "phase", "node"])
    set_status_parser.add_argument("--entity-id", required=True)
    set_status_parser.add_argument("--status", required=True)
    set_status_parser.set_defaults(func=cmd_set_status)

    write_result_parser = subparsers.add_parser("write-result", help="Append a result record to a work node")
    write_result_parser.add_argument("path")
    write_result_parser.add_argument("--node-id", required=True)
    write_result_parser.add_argument("--expected", required=True)
    write_result_parser.add_argument("--actual", required=True)
    write_result_parser.add_argument("--status", required=True)
    write_result_parser.add_argument("--artifacts")
    write_result_parser.add_argument("--notes")
    write_result_parser.set_defaults(func=cmd_write_result)

    validate_parser = subparsers.add_parser("validate", help="Validate graph structure and rules")
    validate_parser.add_argument("path")
    validate_parser.set_defaults(func=cmd_validate)

    summary_parser = subparsers.add_parser("summary", help="Render and write summary.md")
    summary_parser.add_argument("path")
    summary_parser.set_defaults(func=cmd_summary)

    export_obsidian_parser = subparsers.add_parser(
        "export-obsidian",
        help="Export an Obsidian-friendly markdown vault projection",
    )
    export_obsidian_parser.add_argument("path")
    export_obsidian_parser.add_argument("output_dir")
    export_obsidian_parser.add_argument("--force", action="store_true")
    export_obsidian_parser.set_defaults(func=cmd_export_obsidian)

    git_status_parser = subparsers.add_parser("git-status", help="Show git sync state for a repo-backed run")
    git_status_parser.add_argument("path")
    git_status_parser.set_defaults(func=cmd_git_status)

    git_pull_parser = subparsers.add_parser("git-pull", help="Fast-forward pull the backing repo for a repo-backed run")
    git_pull_parser.add_argument("path")
    git_pull_parser.set_defaults(func=cmd_git_pull)

    git_push_parser = subparsers.add_parser("git-push", help="Push the backing repo for a repo-backed run")
    git_push_parser.add_argument("path")
    git_push_parser.add_argument("--message", help="If provided, commit all pending repo changes before pushing")
    git_push_parser.set_defaults(func=cmd_git_push)

    git_sync_parser = subparsers.add_parser("git-sync", help="Pull, optionally commit, and push the backing repo for a repo-backed run")
    git_sync_parser.add_argument("path")
    git_sync_parser.add_argument("--message", help="If provided, commit all pending repo changes after pull and before push")
    git_sync_parser.set_defaults(func=cmd_git_sync)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
