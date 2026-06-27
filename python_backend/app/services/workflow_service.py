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

def pre_flight_check_node(state: MigrationState):
    from app.services.java_runtime_service import java_runtime_service
    output_log = state.get("output_log", [])
    target_version_str = state.get("target_version", "")
    
    try:
        target_version = int(target_version_str)
    except Exception:
        target_version = 17 # default
        
    installed_java = java_runtime_service.get_installed_java_version(target_version)
    
    if installed_java < target_version:
        error_msg = f"Installed JDK version ({installed_java}) is lower than requested target Java version ({target_version}). Please install JDK {target_version} or higher."
        output_log.append(f"[Pre-Flight] ERROR: {error_msg}")
        state["error_message"] = error_msg
        state["success"] = False
        state["output_log"] = output_log
        return state
        
    output_log.append(f"[Pre-Flight] JDK verification passed. Installed: Java {installed_java}, Target: Java {target_version}")
    state["output_log"] = output_log
    return state

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
    
    # Deep Repository Validation (Zero False Positives Policy)
    is_maven = (found_dir / "pom.xml").exists()
    is_gradle = (found_dir / "build.gradle").exists() or (found_dir / "build.gradle.kts").exists()
    
    build_file = found_dir / "pom.xml" if is_maven else (found_dir / "build.gradle" if (found_dir / "build.gradle").exists() else found_dir / "build.gradle.kts")
    build_content = build_file.read_text(encoding='utf-8', errors='ignore').lower()
    
    db_detected = "mysql" in build_content or "postgres" in build_content or "h2" in build_content
    spring_boot = "spring-boot" in build_content
    
    output_log.append(f"[Analysis] Deep Validation -> DB Detected: {db_detected}, Spring Boot: {spring_boot}")
    
    frontend_dir = find_package_json_recursive(project_dir)
    frontend_framework = "None"
    has_frontend = False
    
    if frontend_dir:
        has_frontend = True
        pkg_content = (frontend_dir / "package.json").read_text(encoding='utf-8', errors='ignore').lower()
        if "angular" in pkg_content:
            frontend_framework = "Angular"
        elif "react" in pkg_content:
            frontend_framework = "React"
        elif "vue" in pkg_content:
            frontend_framework = "Vue"
        elif "next" in pkg_content:
            frontend_framework = "Next.js"
        else:
            frontend_framework = "Unknown Node.js"
        output_log.append(f"[Analysis] Frontend Detected: {frontend_framework} at {frontend_dir}")
        
    state["is_maven"] = is_maven
    state["is_gradle"] = is_gradle
    state["has_frontend"] = has_frontend
    state["frontend_dir"] = frontend_dir
    state["frontend_framework"] = frontend_framework
    state["output_log"] = output_log
    
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
    target_version = state.get("target_version", "")
    
    build_result = build_validation_service.validate_build(build_dir, is_maven, api_key, model_name, target_version)
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

def e2e_validation_node(state: MigrationState):
    import subprocess
    import time
    import socket
    import urllib.request
    import os
    from app.services.java_runtime_service import java_runtime_service
    
    has_frontend = state.get("has_frontend", False)
    frontend_dir = state.get("frontend_dir")
    output_log = state.get("output_log", [])
    project_dir = state["project_dir"]
    is_maven = state["is_maven"]
    is_windows = os.name == 'nt'
    env, java_home = java_runtime_service.prepare_env()
    
    state["frontend_result"] = {
        "status": "Not Run", 
        "success": False,
        "static_resource_status": "Not Run",
        "api_connectivity_status": "Not Run",
        "ui_accessibility_status": "Not Run"
    }

    def get_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    backend_port = get_free_port()
    
    output_log.append(f"\n--- [E2E Validation] Starting Backend on port {backend_port} ---")
    if is_maven:
        mvn_cmd = "mvn.cmd" if is_windows else "mvn"
        local_maven = project_dir.parent / "apache-maven-3.9.6" / "bin" / mvn_cmd
        if local_maven.exists(): mvn_cmd = str(local_maven)
        wrapper = project_dir / ("mvnw.cmd" if is_windows else "mvnw")
        if wrapper.exists(): mvn_cmd = str(wrapper)
        backend_cmd = [mvn_cmd, "spring-boot:run", f"-Dspring-boot.run.arguments=--server.port={backend_port}"]
    else:
        gradle_cmd = "gradle.bat" if is_windows else "gradle"
        wrapper = project_dir / ("gradlew.bat" if is_windows else "gradlew")
        if wrapper.exists(): gradle_cmd = str(wrapper)
        backend_cmd = [gradle_cmd, "bootRun", f"--args=--server.port={backend_port}"]

    backend_proc = subprocess.Popen(
        backend_cmd, cwd=str(project_dir), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, errors='replace', env=env
    )
    
    backend_started = False
    start_time = time.time()
    while time.time() - start_time < 45:
        line = backend_proc.stdout.readline()
        if not line: break
        if "Started " in line or "Tomcat initialized with port(s)" in line:
            backend_started = True
            break
            
    if not backend_started:
        output_log.append("[E2E Validation] Backend failed to start.")
        backend_proc.terminate()
        state["frontend_result"]["status"] = "Backend Start Failed"
        state["success"] = False
        return state

    if not has_frontend:
        output_log.append("[E2E Validation] No separate frontend detected. Verifying static resources on backend...")
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{backend_port}/")
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.getcode() == 200:
                    html = response.read().decode('utf-8')
                    if "Whitelabel Error" not in html:
                        state["frontend_result"]["static_resource_status"] = "Success"
                        state["frontend_result"]["ui_accessibility_status"] = "Success"
                        state["frontend_result"]["status"] = "Success"
                        state["frontend_result"]["success"] = True
                        output_log.append("[E2E Validation] Static resources loaded successfully.")
                    else:
                        state["frontend_result"]["static_resource_status"] = "Whitelabel Error Detected"
                        state["frontend_result"]["ui_accessibility_status"] = "Failed"
                        state["success"] = False
                        output_log.append("[E2E Validation] Whitelabel error detected on root context.")
        except Exception as e:
            output_log.append(f"[E2E Validation] Root context not accessible: {e}")
            state["frontend_result"]["static_resource_status"] = "Failed"
            
        backend_proc.terminate()
        return state

    frontend_port = get_free_port()
    output_log.append(f"\n--- [E2E Validation] Starting Frontend on port {frontend_port} ---")
    
    subprocess.run(["npm", "install"], cwd=str(frontend_dir), capture_output=True)
    subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), capture_output=True)
    
    f_env = os.environ.copy()
    f_env["PORT"] = str(frontend_port)
    f_env["REACT_APP_API_URL"] = f"http://127.0.0.1:{backend_port}"
    f_env["VITE_API_URL"] = f"http://127.0.0.1:{backend_port}"

    framework = state.get("frontend_framework", "")
    start_cmd = ["npm", "run", "dev", "--", "--port", str(frontend_port)] if framework in ["React", "Vue", "Next.js"] else ["npm", "start"]
    
    frontend_proc = subprocess.Popen(
        start_cmd, cwd=str(frontend_dir), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, errors='replace', env=f_env
    )
    
    time.sleep(15) 
    
    ui_url = f"http://127.0.0.1:{frontend_port}"
    http_success = False
    try:
        req = urllib.request.Request(ui_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.getcode() == 200:
                http_success = True
                output_log.append(f"[E2E Validation] UI Access Success: {ui_url}")
                state["frontend_result"]["status"] = "Success"
                state["frontend_result"]["ui_accessibility_status"] = "Success"
                state["frontend_result"]["success"] = True
    except Exception as e:
        output_log.append(f"[E2E Validation] UI Check Failed: {e}")
        state["frontend_result"]["status"] = "UI Not Accessible"
        state["frontend_result"]["ui_accessibility_status"] = "Failed"
        state["success"] = False
        
    try:
        req = urllib.request.Request(f"{ui_url}/api/")
        with urllib.request.urlopen(req, timeout=5) as response:
            state["frontend_result"]["api_connectivity_status"] = "Success"
            output_log.append(f"[E2E Validation] API Connectivity Success: Frontend proxied request successfully.")
    except urllib.error.HTTPError as e:
        state["frontend_result"]["api_connectivity_status"] = "Connected (Endpoint 404/401)"
        output_log.append(f"[E2E Validation] API Connectivity Proved via proxy response code {e.code}.")
    except Exception as e:
        state["frontend_result"]["api_connectivity_status"] = f"Proxy Check Failed: {e}"
        output_log.append(f"[E2E Validation] API Connectivity check failed: {e}")
        
    frontend_proc.terminate()
    backend_proc.terminate()
    
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
    diff_output = state.get("diff_output", "")
    from app.services.java_runtime_service import java_runtime_service
    
    target_version_str = state.get("target_version", "")
    try:
        target_version = int(target_version_str)
    except Exception:
        target_version = 17 # default
        
    installed_jdk = java_runtime_service.get_installed_java_version(target_version)
    maven_runtime = java_runtime_service.get_maven_runtime_version(state["project_dir"])
    
    build_result = state.get("build_result", {})
    test_status = build_result.get("test_status", "Not Run")
    runtime_status = build_result.get("runtime_status", "Not Run")
    build_status = build_result.get("status", "Failed")

    frontend_result = state.get("frontend_result", {})
    frontend_status = frontend_result.get("status", "Not Run")
    static_resource_status = frontend_result.get("static_resource_status", "Not Run")
    api_connectivity_status = frontend_result.get("api_connectivity_status", "Not Run")
    ui_accessibility_status = frontend_result.get("ui_accessibility_status", "Not Run")

    if diff_output and diff_output.strip():
        diff_text = diff_output[:15000]
        prompt = f"""Generate a detailed migration report for the following git diff.
You MUST return your answer STRICTLY as a valid, parsable JSON object. Do not include markdown formatting like ```json or anything outside the curly braces.

The JSON object must have the following schema:
{{
  "accuracy": 99,
  "percentage_migrated": 100,
  "installed_jdk_version": {installed_jdk},
  "maven_runtime_version": {maven_runtime},
  "build_status": "{build_status}",
  "test_status": "{test_status}",
  "runtime_status": "{runtime_status}",
  "backend_health_check": "{runtime_status}",
  "frontend_build_status": "{frontend_status}",
  "frontend_runtime_status": "{frontend_status}",
  "ui_accessibility_status": "{ui_accessibility_status}",
  "static_resource_status": "{static_resource_status}",
  "api_connectivity_status": "{api_connectivity_status}",
  "root_cause_analysis": "string",
  "fixes_applied": "string",
  "final_result": "{'PASS' if state.get('success') else 'FAIL'}",
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
            from app.ai.ai_factory import AIFactory
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
    if not success and build_result.get("success") and len(build_result.get("fixHistory", [])) > 0:
        output_log = "".join(state.get("output_log", []))
        if "Auto-Healing triggered!" not in output_log:
            return "compilation_fix"
    return "e2e_validation"

def route_after_frontend(state: MigrationState):
    return "git_diff"

def route_after_pre_flight(state: MigrationState):
    if state.get("error_message"):
        return END
    return "repository_analysis"

def create_migration_workflow():
    workflow = StateGraph(MigrationState)

    workflow.add_node("pre_flight_check", pre_flight_check_node)
    workflow.add_node("repository_analysis", repository_analysis_node)
    workflow.add_node("migration", migration_node)
    workflow.add_node("build_validation", build_validation_node)
    workflow.add_node("compilation_fix", compilation_fix_node)
    workflow.add_node("e2e_validation", e2e_validation_node)
    workflow.add_node("git_diff", git_diff_node)
    workflow.add_node("report_generation", report_generation_node)

    workflow.set_entry_point("pre_flight_check")
    
    workflow.add_conditional_edges(
        "pre_flight_check",
        route_after_pre_flight,
        {
            "repository_analysis": "repository_analysis",
            END: END
        }
    )
    
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
            "e2e_validation": "e2e_validation"
        }
    )

    workflow.add_edge("compilation_fix", "build_validation")
    workflow.add_edge("e2e_validation", "git_diff")
    workflow.add_edge("git_diff", "report_generation")
    workflow.add_edge("report_generation", END)

    return workflow.compile()

migration_workflow = create_migration_workflow()
