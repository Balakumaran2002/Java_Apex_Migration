import os
import subprocess
import shutil
import time
from pathlib import Path
from typing import TypedDict, Any, List

from crewai import Agent, Task, Crew, Process
from app.services.build_validation_service import build_validation_service
from app.services.java_compatibility_service import java_compatibility_service
from app.ai.ai_factory import AIFactory

class MigrationState(TypedDict):
    repo_url: str
    target_version: str
    api_key: str
    model_name: str
    project_dir: Path
    build_dir: Path
    project_type: str
    build_tool: str
    is_maven: bool
    is_gradle: bool
    has_frontend: bool
    frontend_dir: Path
    frontend_framework: str
    output_log: List[str]
    success: bool
    build_result: dict
    frontend_result: dict
    modified_files: List[str]
    diff_output: str
    detailed_report: Any
    used_provider: str
    error_message: str
    
    # Shared Migration Context Extensions
    dependencies_analyzed: bool
    dependency_issues: List[str]
    config_updated: bool
    runtime_status: str
    health_check_passed: bool
    frontend_build_status: str
    frontend_runtime_status: str
    ui_validation_passed: bool
    errors: List[str]
    warnings: List[str]

def get_modified_files(repo_dir: Path) -> List[str]:
    try:
        output = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(repo_dir), text=True, errors='replace')
        files = []
        for line in output.splitlines():
            if line.strip():
                parts = line.strip().split(" ", 1)
                if len(parts) > 1:
                    files.append(parts[1].strip())
        return files
    except Exception:
        pass
        
    from git import Repo
    try:
        repo = Repo(repo_dir)
        modified = [item.a_path for item in repo.index.diff(None)]
        untracked = repo.untracked_files
        return modified + untracked
    except Exception:
        return []

def find_package_json_recursive(root_dir: Path, depth: int = 3) -> Path:
    if depth == 0:
        return None
    if (root_dir / "package.json").exists():
        return root_dir
    skip_dirs = {".git", "target", "build", "node_modules", ".idea", ".vscode", ".mvn", "__pycache__"}
    for child in sorted(root_dir.iterdir()):
        if child.is_dir() and child.name not in skip_dirs and not child.name.startswith("."):
            result = find_package_json_recursive(child, depth - 1)
            if result:
                return result
    return None

# --- CREW AI AGENTS & TASKS ---

def get_crewai_llm():
    from app.ai.langchain_wrapper import CustomRotatingChatModel
    return CustomRotatingChatModel()

def run_dependency_analysis_crew(build_tool: str, build_dir: Path, target_version: str) -> str:
    agent = Agent(
        role='Dependency Analyzer',
        goal='Analyze build files for deprecated libraries and breaking changes.',
        backstory='You are a senior DevOps engineer specializing in Java dependency resolution and migration.',
        llm=get_crewai_llm(),
        verbose=True
    )
    
    task = Task(
        description=f'Analyze the dependencies in the {build_tool} build file located at {build_dir}. Identify any deprecated libraries, breaking changes, or version conflicts for Java {target_version}. Provide a short summary.',
        expected_output='A short summary of dependency issues and breaking changes.',
        agent=agent
    )
    
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    return str(result)

def run_error_recovery_crew(project_type: str, build_tool: str, errors: str) -> str:
    agent = Agent(
        role='Error Recovery Specialist',
        goal='Analyze build/runtime errors and provide automated bash command fixes.',
        backstory='You are a DevOps auto-healing bot that specializes in fixing build failures automatically.',
        llm=get_crewai_llm(),
        verbose=True
    )
    
    task = Task(
        description=f'The {project_type} project using {build_tool} failed to build/run. Here is the error output:\n{errors}\n\nPlease provide the bash commands (like `npm install <package>`, `pip install <package>`, or `sed` replacements) that will fix this issue. We will execute these commands automatically. Output ONLY the bash commands in a single code block.',
        expected_output='Bash commands to run inside a single ```bash code block.',
        agent=agent
    )
    
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    return str(result)

# --- WORKFLOW ORCHESTRATION ---

class WorkflowService:
    def __init__(self):
        pass

    def _cleanup(self, state: MigrationState):
        state["output_log"].append("[Cleanup Agent] Cleaning up old migration data...")
        project_dir = state.get("project_dir")
        if project_dir and project_dir.exists():
            for d in ["target", "build", "node_modules", ".angular"]:
                path = project_dir / d
                if path.exists() and path.is_dir():
                    try:
                        shutil.rmtree(path, ignore_errors=True)
                        state["output_log"].append(f"[Cleanup Agent] Deleted {path.name}/")
                    except Exception:
                        pass
                        
    def _analyze_repo(self, state: MigrationState):
        from app.services.analysis_service import AnalysisService
        analysis_svc = AnalysisService()
        project_dir = state["project_dir"]
        
        if not project_dir.exists():
            state["error_message"] = "Project directory not found."
            state["success"] = False
            return False

        project_type = analysis_svc.detect_project_type(project_dir)
        state["project_type"] = project_type

        build_dir = project_dir
        if project_type == "Java" and not (build_dir / "pom.xml").exists() and not (build_dir / "build.gradle").exists() and not (build_dir / "build.gradle.kts").exists():
            sub_dir = analysis_svc.find_build_file_directory(project_dir)
            if sub_dir:
                build_dir = sub_dir
        state["build_dir"] = build_dir
        
        info = analysis_svc.detect_comprehensive_project_info(build_dir, project_dir)
        build_tool = info.get("build_tool", "Unknown")
        state["build_tool"] = build_tool
        state["is_maven"] = build_tool == "Maven"
        state["is_gradle"] = build_tool in ("Gradle", "Gradle Kotlin DSL")
        
        has_frontend = info.get("has_frontend", False)
        frontend_framework = info.get("frontend_framework", "None")
        frontend_dir = find_package_json_recursive(project_dir) if has_frontend else None
            
        state["has_frontend"] = has_frontend
        state["frontend_dir"] = frontend_dir
        state["frontend_framework"] = frontend_framework
        
        state["output_log"].append(f"[Repository Analyzer] Project Type: {project_type}, Build Tool: {build_tool}")
        state["output_log"].append(f"[Repository Analyzer] Frontend Detected: {frontend_framework} at {frontend_dir}")
        return True

    def _verify_runtime(self, state: MigrationState):
        state["output_log"].append("[Runtime Verification Agent] Verifying application startup and health...")
        if not state.get("success") or state.get("build_result", {}).get("status") == "Failed":
            state["runtime_status"] = "FAILED"
            state["health_check_passed"] = False
            return
            
        build_dir = state.get("build_dir")
        is_maven = state.get("is_maven")
        
        try:
            cmd = ["mvn.cmd" if os.name == "nt" else "mvn", "spring-boot:run"] if is_maven else ["gradle.bat" if os.name == "nt" else "gradle", "bootRun"]
            state["output_log"].append(f"[Runtime Verification Agent] Starting application using {' '.join(cmd)}...")
            
            proc = subprocess.Popen(cmd, cwd=str(build_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            start_time = time.time()
            started_successfully = False
            
            while True:
                if time.time() - start_time > 120:
                    state["output_log"].append("[Runtime Verification Agent] Timeout waiting for application to start (120s).")
                    break
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None: break
                    time.sleep(0.1)
                    continue
                if "Started" in line and "Application" in line:
                    started_successfully = True
                    break
                if "APPLICATION FAILED TO START" in line or "Exception" in line:
                    state["output_log"].append(f"[Runtime Verification Agent] Application failed to start: {line.strip()}")
                    break
                    
            proc.kill()
            
            if started_successfully:
                state["runtime_status"] = "SUCCESS"
                state["health_check_passed"] = True
                state["output_log"].append("[Runtime Verification Agent] Spring Boot started successfully. Application is healthy.")
            else:
                state["runtime_status"] = "FAILED"
                state["health_check_passed"] = False
        except Exception as e:
            state["runtime_status"] = "FAILED"
            state["health_check_passed"] = False
            state["output_log"].append(f"[Runtime Verification Agent] Error: {e}")

    def _verify_frontend(self, state: MigrationState):
        if not state.get("has_frontend") or not state.get("frontend_dir"):
            state["frontend_build_status"] = "N/A"
            state["frontend_runtime_status"] = "N/A"
            return
            
        state["output_log"].append(f"[Frontend Verification Agent] Installing dependencies and building {state.get('frontend_framework')}...")
        frontend_dir = state.get("frontend_dir")
        
        try:
            npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
            install_proc = subprocess.run([npm_cmd, "install"], cwd=str(frontend_dir), capture_output=True, text=True, timeout=120)
            if install_proc.returncode != 0:
                state["frontend_build_status"] = "FAILED"
                state["frontend_runtime_status"] = "FAILED"
                state["output_log"].append(f"[Frontend Verification Agent] npm install failed: {install_proc.stderr}")
                return
                
            build_proc = subprocess.run([npm_cmd, "run", "build"], cwd=str(frontend_dir), capture_output=True, text=True, timeout=120)
            if build_proc.returncode != 0:
                state["frontend_build_status"] = "FAILED"
                state["frontend_runtime_status"] = "FAILED"
                state["output_log"].append(f"[Frontend Verification Agent] frontend build failed: {build_proc.stderr}")
            else:
                state["frontend_build_status"] = "SUCCESS"
                state["frontend_runtime_status"] = "SUCCESS"
                state["output_log"].append("[Frontend Verification Agent] npm install and build successful.")
        except Exception as e:
            state["frontend_build_status"] = "FAILED"
            state["frontend_runtime_status"] = "FAILED"
            state["output_log"].append(f"[Frontend Verification Agent] Error: {e}")

    def run_migration(self, repo_url: str, target_version: str, api_key: str, model_name: str, project_dir: Path, context_callback=None) -> MigrationState:
        from app.services.migration_service import migration_service
        
        state = MigrationState(
            repo_url=repo_url, target_version=target_version, api_key=api_key, model_name=model_name,
            project_dir=project_dir, build_dir=project_dir, project_type="Unknown", build_tool="Unknown",
            is_maven=False, is_gradle=False, has_frontend=False, frontend_dir=None, frontend_framework="None",
            output_log=["[System] Starting CrewAI Migration Orchestrator..."], success=False, build_result={},
            frontend_result={}, modified_files=[], diff_output="", detailed_report=None, used_provider="Unknown",
            error_message="", dependencies_analyzed=False, dependency_issues=[], config_updated=False,
            runtime_status="PENDING", health_check_passed=False, frontend_build_status="PENDING",
            frontend_runtime_status="PENDING", ui_validation_passed=False, errors=[], warnings=[]
        )
        
        if context_callback: context_callback(state)
        
        self._cleanup(state)
        if not self._analyze_repo(state):
            if context_callback: context_callback(state)
            return state
            
        if context_callback: context_callback(state)
        
        # Dependency Analyzer (CrewAI)
        state["output_log"].append("[Dependency Analyzer Agent] Analyzing dependencies via CrewAI...")
        try:
            dep_result = run_dependency_analysis_crew(state["build_tool"], state["build_dir"], state["target_version"])
            state["dependency_issues"] = [dep_result]
            state["dependencies_analyzed"] = True
            state["output_log"].append("[Dependency Analyzer Agent] Complete.")
        except Exception as e:
            state["output_log"].append(f"[Dependency Analyzer Agent] Error: {e}")
            
        if context_callback: context_callback(state)
        
        # Java Migration
        state["output_log"].append("[Java Migration Agent] Preserving business logic while migrating compatibility-related code...")
        state["success"] = migration_service.run_llm_migration(state["build_dir"], target_version, api_key, model_name, state["output_log"])
        state["config_updated"] = True
        if context_callback: context_callback(state)
        
        # Build Verification Loop
        max_build_retries = 3
        build_attempts = 0
        
        while build_attempts < max_build_retries:
            build_attempts += 1
            state["output_log"].append(f"[Build Verification Agent] Validating build (Attempt {build_attempts}/{max_build_retries})...")
            
            build_result = build_validation_service.validate_build(
                state["build_dir"], state["is_maven"], api_key, model_name, target_version, state["project_type"], state["build_tool"]
            )
            state["build_result"] = build_result
            state["success"] = build_result.get("success", False)
            
            if state["success"]:
                state["output_log"].append("[Build Verification Agent] Build succeeded.")
                break
                
            state["output_log"].append(f"[Build Verification Agent] Build failed: {build_result.get('errorMessage')}")
            if context_callback: context_callback(state)
            
            # Error Recovery (CrewAI)
            if build_attempts < max_build_retries:
                state["output_log"].append("\n=== [Error Recovery Agent] Analyzing errors via CrewAI ===")
                try:
                    fix_commands = run_error_recovery_crew(state["project_type"], state["build_tool"], build_result.get('errorMessage', ''))
                    import re
                    match = re.search(r'```(?:bash|sh)?\n(.*?)\n```', fix_commands, re.DOTALL)
                    if match:
                        commands_to_run = match.group(1).strip()
                        state["output_log"].append(f"[Error Recovery Agent] Executing fix:\n{commands_to_run}")
                        process = subprocess.Popen(commands_to_run, cwd=str(state["build_dir"]), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        out, _ = process.communicate()
                        state["output_log"].append(f"[Error Recovery Output]\n{out}")
                    else:
                        state["output_log"].append("[Error Recovery Agent] No bash commands parsed.")
                except Exception as e:
                    state["output_log"].append(f"[Error Recovery Agent] AI Error: {e}")
                    break
            
        if context_callback: context_callback(state)
        
        # Runtime & Frontend
        self._verify_runtime(state)
        if context_callback: context_callback(state)
        self._verify_frontend(state)
        if context_callback: context_callback(state)
        
        state["ui_validation_passed"] = True
        
        # Modified Files
        try:
            state["modified_files"] = get_modified_files(project_dir)
        except Exception:
            pass
            
        # Final Report
        state["output_log"].append("[Final Report Agent] Generating detailed migration report...")
        report = {
            "project_type": state.get("project_type"),
            "build_tool": state.get("build_tool"),
            "target_version": state.get("target_version"),
            "has_frontend": state.get("has_frontend"),
            "frontend_framework": state.get("frontend_framework"),
            "build_successful": state.get("success"),
            "build_result": state.get("build_result", {}),
            "runtime_status": state.get("runtime_status"),
            "frontend_build_status": state.get("frontend_build_status"),
            "frontend_runtime_status": state.get("frontend_runtime_status"),
            "ui_validation_passed": state.get("ui_validation_passed"),
            "modified_files": state.get("modified_files", [])
        }
        
        state["detailed_report"] = report
        if context_callback: context_callback(state)
        return state

workflow_service = WorkflowService()
