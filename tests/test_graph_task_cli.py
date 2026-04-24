import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "scripts" / "graph_task.py"
PACKAGER = Path("/home/jimmy/.npm-global/lib/node_modules/openclaw/skills/skill-creator/scripts/package_skill.py")


class GraphTaskCliTests(unittest.TestCase):
    maxDiff = None

    def run_cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_end_to_end_cli_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "demo-run"

            self.run_cli(
                "init",
                str(run_dir),
                "--id",
                "demo-project",
                "--title",
                "Demo project",
                "--description",
                "A minimal graph-task smoke test",
                "--goal",
                "Reach a valid inspectable graph",
            )
            self.run_cli(
                "add-step",
                str(run_dir),
                "--id",
                "step-1",
                "--step-type",
                "implementation",
                "--description",
                "Implement simple state handling",
            )
            self.run_cli(
                "add-phase",
                str(run_dir),
                "--step-id",
                "step-1",
                "--id",
                "phase-diverge-1",
                "--phase-type",
                "diverge",
                "--description",
                "Explore state management options",
            )
            self.run_cli(
                "add-node",
                str(run_dir),
                "--phase-id",
                "phase-diverge-1",
                "--id",
                "node-1",
                "--title",
                "Compare candidate libraries",
                "--description",
                "Check Zustand and Redux for current scope",
            )
            self.run_cli(
                "add-edge",
                str(run_dir),
                "--phase-id",
                "phase-diverge-1",
                "--id",
                "edge-1",
                "--from-node",
                "phase-diverge-1-root",
                "--to-node",
                "node-1",
                "--edge-type",
                "flow",
            )
            self.run_cli(
                "add-phase",
                str(run_dir),
                "--step-id",
                "step-1",
                "--id",
                "phase-verify-1",
                "--phase-type",
                "verify",
                "--description",
                "Verify the current choice",
            )
            self.run_cli(
                "add-phase-edge",
                str(run_dir),
                "--step-id",
                "step-1",
                "--id",
                "phase-edge-1",
                "--from-phase",
                "phase-diverge-1",
                "--to-phase",
                "phase-verify-1",
            )
            self.run_cli(
                "write-result",
                str(run_dir),
                "--node-id",
                "node-1",
                "--expected",
                "Choose a candidate state library",
                "--actual",
                "Selected Zustand after comparing complexity and setup cost",
                "--status",
                "done",
                "--notes",
                "Simple enough for the current scope",
            )

            validate = self.run_cli("validate", str(run_dir))
            self.assertIn("VALID", validate.stdout)

            summary = self.run_cli("summary", str(run_dir))
            self.assertIn("Selected Zustand", summary.stdout)
            self.assertTrue((run_dir / "summary.md").exists())

            graph = json.loads((run_dir / "graph.json").read_text(encoding="utf-8"))
            node = graph["project"]["steps"][0]["phases"][0]["nodes"][1]
            self.assertEqual(node["status"], "done")
            self.assertEqual(node["results"][0]["status"], "done")
            self.assertEqual(node["results"][0]["nodeId"], "node-1")

    def test_repeated_diverge_verify_phases_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "repeat-run"

            self.run_cli(
                "init",
                str(run_dir),
                "--id",
                "repeat-project",
                "--title",
                "Repeat project",
                "--description",
                "Ensure repeated phase types remain valid",
                "--goal",
                "Keep history while looping through phases",
            )
            self.run_cli(
                "add-step",
                str(run_dir),
                "--id",
                "step-1",
                "--step-type",
                "analysis",
                "--description",
                "Loop through diverge and verify more than once",
            )

            for phase_id, phase_type, description in [
                ("phase-diverge-1", "diverge", "Explore initial options"),
                ("phase-verify-1", "verify", "Check the first option"),
                ("phase-diverge-2", "diverge", "Re-open exploration after verification"),
                ("phase-verify-2", "verify", "Check the revised option"),
                ("phase-commit-1", "commit", "Lock the chosen path"),
            ]:
                self.run_cli(
                    "add-phase",
                    str(run_dir),
                    "--step-id",
                    "step-1",
                    "--id",
                    phase_id,
                    "--phase-type",
                    phase_type,
                    "--description",
                    description,
                )

            for edge_id, from_phase, to_phase in [
                ("phase-edge-1", "phase-diverge-1", "phase-verify-1"),
                ("phase-edge-2", "phase-verify-1", "phase-diverge-2"),
                ("phase-edge-3", "phase-diverge-2", "phase-verify-2"),
                ("phase-edge-4", "phase-verify-2", "phase-commit-1"),
            ]:
                self.run_cli(
                    "add-phase-edge",
                    str(run_dir),
                    "--step-id",
                    "step-1",
                    "--id",
                    edge_id,
                    "--from-phase",
                    from_phase,
                    "--to-phase",
                    to_phase,
                )

            validate = self.run_cli("validate", str(run_dir))
            self.assertIn("VALID", validate.stdout)

    def test_multiple_commit_phases_fail_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "invalid-commit-run"

            self.run_cli(
                "init",
                str(run_dir),
                "--id",
                "invalid-commit-project",
                "--title",
                "Invalid commit project",
                "--description",
                "Ensure only one commit phase is allowed",
                "--goal",
                "Catch duplicate commit phases",
            )
            self.run_cli(
                "add-step",
                str(run_dir),
                "--id",
                "step-1",
                "--step-type",
                "implementation",
                "--description",
                "Test duplicate commit phase validation",
            )
            self.run_cli(
                "add-phase",
                str(run_dir),
                "--step-id",
                "step-1",
                "--id",
                "phase-commit-1",
                "--phase-type",
                "commit",
                "--description",
                "First commit phase",
            )

            second_commit = self.run_cli(
                "add-phase",
                str(run_dir),
                "--step-id",
                "step-1",
                "--id",
                "phase-commit-2",
                "--phase-type",
                "commit",
                "--description",
                "Second commit phase should fail validation",
                check=False,
            )
            self.assertNotEqual(second_commit.returncode, 0)
            self.assertIn("already has a commit phase", second_commit.stdout + second_commit.stderr)

            validate = self.run_cli("validate", str(run_dir))
            self.assertIn("VALID", validate.stdout)

    def test_skill_packages_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_copy = Path(tmp) / "graph-task"
            shutil.copytree(
                REPO_ROOT,
                skill_copy,
                ignore=shutil.ignore_patterns(".git", "__pycache__", ".dist", "*.pyc"),
            )
            output_dir = Path(tmp) / "dist"
            result = subprocess.run(
                [sys.executable, str(PACKAGER), str(skill_copy), str(output_dir)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            package_path = output_dir / "graph-task.skill"
            self.assertTrue(package_path.exists())

            with zipfile.ZipFile(package_path) as zf:
                names = set(zf.namelist())
            self.assertIn("graph-task/SKILL.md", names)
            self.assertIn("graph-task/scripts/graph_task.py", names)
            self.assertIn("graph-task/references/schema.graph-task.json", names)


if __name__ == "__main__":
    unittest.main()
