import os
import subprocess
from pathlib import Path
from typing import TypedDict, Any, List
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, END
from app.services.build_validation_service import build_validation_service
from app.ai.ai_factory import AIFactory

class MigrationState(TypedDict):
    repo_url: str
    target_version: str
    api_key: str
    model_name: str
    project_dir: Path
    build_dir: Path
    is_maven: bool
    is_gradle: bool
    output_log: List[str]
    success: bool
    build_result: dict
    modified_files: List[str]
    diff_output: str
    detailed_report: Any
    used_provider: str
    error_message: str

def get_modified_files(repo_dir: Path) -> List[str]:
    from git import Repo
    try:
        repo = Repo(repo_dir)
        modified = [item.a_path for item in repo.index.diff(None)]
        untracked = repo.untracked_files
        return modified + untracked
    except Exception:
        return []

def find_build_file_recursive(root_dir: Path, depth: int = 3) -> Path:
    """Search for a build file (pom.xml or build.gradle) up to `depth` levels deep."""
    if depth == 0:
        return None
    # Check current level first
    if (root_dir / "pom.xml").exists() or (root_dir / "build.gradle").exists() or (root_dir / "build.gradle.kts").exists():
        return root_dir
    # Then recurse into subdirectories (skip hidden and well-known non-source dirs)
    skip_dirs = {".git", "target", "build", "node_modules", ".idea", ".vscode", ".mvn", "__pycache__"}
    for child in sorted(root_dir.iterdir()):
        if child.is_dir() and child.name not in skip_dirs and not child.name.startswith("."):
            result = find_build_file_recursive(child, depth - 1)
            if result:
                return result
    return None

def repository_analysis_node(state: MigrationState):
    # Already analyzed and path provided, just resolving build_dir
    project_dir = state["project_dir"]
    output_log = state.get("output_log", [])

    if not project_dir.exists():
        state["error_message"] = "Project directory not found. Run analysis first."
        state["success"] = False
        return state

    output_log.append(f"[Analysis] Searching for build file in: {project_dir}")
    found_dir = find_build_file_recursive(project_dir)

    if found_dir is None:
        output_log.append(f"[Analysis] ERROR: No pom.xml or build.gradle found under {project_dir}")
        state["error_message"] = f"No supported build tool found. Searched under: {project_dir}"
        state["success"] = False
        state["output_log"] = output_log
        return state

    output_log.append(f"[Analysis] Found build file in: {found_dir}")
    state["build_dir"] = found_dir
    state["output_log"] = output_log
    state["is_maven"] = (found_dir / "pom.xml").exists()
    state["is_gradle"] = (found_dir / "build.gradle").exists() or (found_dir / "build.gradle.kts").exists()

    return state


def migration_node(state: MigrationState):
    from app.services.migration_service import migration_service
    build_dir = state["build_dir"]
    target_version = state["target_version"]
    output_log = state.get("output_log", [])
    
    if state["is_maven"]:
        success = migration_service.run_maven_migration(build_dir, target_version, output_log)
    else:
        success = migration_service.run_gradle_migration(build_dir, target_version, output_log)
        
    state["success"] = success
    state["output_log"] = output_log
    return state

def build_validation_node(state: MigrationState):
    build_dir = state["build_dir"]
    is_maven = state["is_maven"]
    api_key = state["api_key"]
    model_name = state["model_name"]
    
    build_result = build_validation_service.validate_build(build_dir, is_maven, api_key, model_name)
    state["build_result"] = build_result
    return state

def compilation_fix_node(state: MigrationState):
    from app.services.migration_service import migration_service
    output_log = state.get("output_log", [])
    output_log.append("\n=== Auto-Healing triggered! Retrying OpenRewrite after AI build fixes ===")
    
    build_dir = state["build_dir"]
    target_version = state["target_version"]
    
    if state["is_maven"]:
        success = migration_service.run_maven_migration(build_dir, target_version, output_log)
    else:
        success = migration_service.run_gradle_migration(build_dir, target_version, output_log)
        
    state["success"] = success
    state["output_log"] = output_log
    return state

def git_diff_node(state: MigrationState):
    project_dir = state["project_dir"]
    state["modified_files"] = get_modified_files(project_dir)
    
    diff_output = ""
    if len(state["modified_files"]) > 0:
        try:
            diff_output = subprocess.check_output(["git", "diff"], cwd=str(project_dir), text=True, errors='replace')
        except Exception:
            pass
    state["diff_output"] = diff_output
    return state

def report_generation_node(state: MigrationState):
    diff_output = state["diff_output"]
    if diff_output and diff_output.strip():
        diff_text = diff_output[:15000]
        prompt = f"""Generate a detailed migration report for the following git diff.
You MUST return your answer STRICTLY as a valid, parsable JSON object. Do not include markdown formatting like ```json or anything outside the curly braces.

The JSON object must have the following schema:
{{
  "accuracy": 99,
  "percentage_migrated": 100,
  "files": [
    {{
      "filename": "string",
      "before_code": "string",
      "after_code": "string",
      "explanation": "string"
    }}
  ],
  "dependencies": [
    {{
      "name": "string",
      "old_version": "string",
      "new_version": "string",
      "reason": "string"
    }}
  ]
}}

Here is the diff:
```diff
{diff_text}
```"""
        try:
            ai_client = AIFactory.get_client()
            detailed_report = ai_client.generate(prompt, api_key=state["api_key"], model_name=state["model_name"])
            state["detailed_report"] = detailed_report
            state["used_provider"] = getattr(ai_client, "last_provider_used", None)
        except Exception as e:
            state["detailed_report"] = f"Failed to generate detailed report: {e}"
    else:
        state["detailed_report"] = None
    return state

def route_after_analysis(state: MigrationState):
    if state.get("error_message"):
        return END
    return "migration"

def route_after_build(state: MigrationState):
    build_result = state.get("build_result", {})
    success = state.get("success", False)
    # If migration failed but AI successfully fixed it and there is fix history -> retry migration
    if not success and build_result.get("success") and len(build_result.get("fixHistory", [])) > 0:
        # Check if we already retried to prevent infinite loop. The simplest way is to check 
        # if "Auto-Healing triggered!" is in output_log.
        output_log = "".join(state.get("output_log", []))
        if "Auto-Healing triggered!" not in output_log:
            return "compilation_fix"
    return "git_diff"

def create_migration_workflow():
    workflow = StateGraph(MigrationState)

    workflow.add_node("repository_analysis", repository_analysis_node)
    workflow.add_node("migration", migration_node)
    workflow.add_node("build_validation", build_validation_node)
    workflow.add_node("compilation_fix", compilation_fix_node)
    workflow.add_node("git_diff", git_diff_node)
    workflow.add_node("report_generation", report_generation_node)

    workflow.set_entry_point("repository_analysis")
    
    workflow.add_conditional_edges(
        "repository_analysis",
        route_after_analysis,
        {
            "migration": "migration",
            END: END
        }
    )

    workflow.add_edge("migration", "build_validation")

    workflow.add_conditional_edges(
        "build_validation",
        route_after_build,
        {
            "compilation_fix": "compilation_fix",
            "git_diff": "git_diff"
        }
    )

    workflow.add_edge("compilation_fix", "build_validation")
    workflow.add_edge("git_diff", "report_generation")
    workflow.add_edge("report_generation", END)

    return workflow.compile()

migration_workflow = create_migration_workflow()
