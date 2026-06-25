import os
import re
import socket
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import app_config

class ProjectRunnerService:
    def __init__(self):
        # Maps repo_name -> dict with details: process, port, status, logs, type, preview_url, endpoints, error_reason, etc.
        self.runs: Dict[str, Dict[str, Any]] = {}
        # Maps repo_name -> list of asyncio.Queue for streaming logs to websockets
        self.log_queues: Dict[str, List[asyncio.Queue]] = {}

    def get_run_dir(self, repo_name: str) -> Path:
        project_dir = app_config.workspace_directory / repo_name
        return self.find_run_directory(project_dir)

    def find_run_directory(self, project_dir: Path) -> Path:
        """Locate the directory containing build/package configuration files recursively."""
        if not project_dir.exists():
            return project_dir

        for child in project_dir.rglob("pom.xml"):
            if 'target' not in child.parts and 'node_modules' not in child.parts:
                return child.parent
        for child in project_dir.rglob("build.gradle"):
            if 'build' not in child.parts and 'node_modules' not in child.parts:
                return child.parent
        for child in project_dir.rglob("build.gradle.kts"):
            if 'build' not in child.parts and 'node_modules' not in child.parts:
                return child.parent
        for child in project_dir.rglob("package.json"):
            if 'node_modules' not in child.parts:
                return child.parent
        return project_dir

    def detect_project_type(self, run_dir: Path) -> str:
        """Detect the framework and language setup of the project."""
        package_json = run_dir / "package.json"
        if package_json.exists():
            try:
                import json
                data = json.loads(package_json.read_text(encoding='utf-8', errors='ignore'))
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                scripts = data.get("scripts", {})
                
                if "vite" in dev_deps or "vite" in deps or any("vite" in s for s in scripts.values()):
                    return "React / Vite"
                if any("@angular" in k for k in deps.keys()) or "ng" in scripts:
                    return "Angular"
                return "Node.js frontend"
            except Exception:
                return "Node.js frontend"

        pom_xml = run_dir / "pom.xml"
        if pom_xml.exists():
            try:
                content = pom_xml.read_text(encoding='utf-8', errors='ignore')
                if "thymeleaf" in content:
                    return "Spring Boot / Thymeleaf"
                if "jsp" in content or "jstl" in content or "tomcat-embed-jasper" in content:
                    return "Spring Boot / JSP"
                return "Spring Boot / Maven"
            except Exception:
                return "Spring Boot / Maven"

        build_gradle = run_dir / "build.gradle"
        build_gradle_kts = run_dir / "build.gradle.kts"
        if build_gradle.exists() or build_gradle_kts.exists():
            try:
                target_file = build_gradle if build_gradle.exists() else build_gradle_kts
                content = target_file.read_text(encoding='utf-8', errors='ignore')
                if "thymeleaf" in content:
                    return "Spring Boot / Thymeleaf"
                if "jsp" in content or "jasper" in content:
                    return "Spring Boot / JSP"
                return "Spring Boot / Gradle"
            except Exception:
                return "Spring Boot / Gradle"

        return "Unknown"

    def find_available_port(self, start_port: int = 8081) -> int:
        """Finds an open port starting from start_port."""
        port = start_port
        while port < 65535:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except socket.error:
                    port += 1
        return 8080

    def extract_java_endpoints(self, run_dir: Path) -> List[Dict[str, str]]:
        """Parses Java controller files to discover REST endpoints (HTTP Method, Route Path, Controller Name)."""
        endpoints = []
        for path in run_dir.rglob("*.java"):
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
                if "@RestController" in content or "@Controller" in content:
                    # Parse class-level @RequestMapping mapping path
                    class_mapping = ""
                    # Match @RequestMapping("/path") or @RequestMapping(value="/path")
                    class_match = re.search(r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']\s*\)', content)
                    if class_match:
                        class_mapping = class_match.group(1)

                    # Scan for method mappings
                    # Pattern catches @GetMapping("/xxx") or @PostMapping(value="/xxx")
                    method_matches = re.finditer(
                        r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']', 
                        content
                    )
                    for match in method_matches:
                        mapping_type = match.group(1)
                        method_type = mapping_type.replace("Mapping", "").upper()
                        if method_type == "REQUEST":
                            method_type = "ALL"
                        path_val = match.group(2)
                        
                        full_path = "/" + (class_mapping.strip("/") + "/" + path_val.strip("/")).strip("/")
                        endpoints.append({
                            "method": method_type,
                            "path": full_path,
                            "file": path.name
                        })
            except Exception:
                pass
        return endpoints

    def add_log(self, repo_name: str, message: str):
        """Append a log line to history and dispatch to active websocket queues."""
        if repo_name not in self.runs:
            return
        cleaned_msg = message.rstrip() + "\n"
        self.runs[repo_name]["logs"].append(cleaned_msg)
        
        # Broadcast to queues
        if repo_name in self.log_queues:
            for q in self.log_queues[repo_name]:
                q.put_nowait(cleaned_msg)

    async def monitor_port(self, repo_name: str, port: int, timeout: int = 60) -> bool:
        """Poll the port until it is open, confirming the server started successfully."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if repo_name not in self.runs or self.runs[repo_name]["status"] != "STARTING":
                return False
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                result = s.connect_ex(("127.0.0.1", port))
                if result == 0:
                    return True
            await asyncio.sleep(1)
        return False

    async def start_project(self, repo_name: str):
        """Starts the project lifecycle asynchronously in the background."""
        # 1. Stop any currently running instance
        if repo_name in self.runs and self.runs[repo_name]["status"] in ["STARTING", "RUNNING"]:
            await self.stop_project(repo_name)

        run_dir = self.get_run_dir(repo_name)
        if not run_dir.exists():
            self.runs[repo_name] = {
                "status": "FAILED",
                "logs": ["Error: Workspace path not found.\n"],
                "port": None,
                "type": "Unknown",
                "preview_url": None,
                "endpoints": [],
                "error_reason": f"Workspace directory '{run_dir}' does not exist. Ensure repository has been migrated and analyzed."
            }
            return

        project_type = self.detect_project_type(run_dir)
        port = self.find_available_port()
        
        self.runs[repo_name] = {
            "status": "STARTING",
            "logs": [],
            "port": port,
            "type": project_type,
            "preview_url": None,
            "endpoints": [],
            "error_reason": None,
            "process": None
        }

        # Run startup task in background
        asyncio.create_task(self._run_lifecycle(repo_name, run_dir, project_type, port))

    async def _run_lifecycle(self, repo_name: str, run_dir: Path, project_type: str, port: int):
        self.add_log(repo_name, f"=== RUN PROJECT LOGS FOR '{repo_name}' ===")
        self.add_log(repo_name, f"Detected Project Type: {project_type}")
        self.add_log(repo_name, f"Allocated Local Port: {port}")
        self.add_log(repo_name, f"WorkingDirectory: {run_dir}\n")

        is_windows = os.name == 'nt'
        env = os.environ.copy()
        
        # Configure Java environment for Spring Boot if JDK 21 is available
        if is_windows:
            java21 = Path("C:/Program Files/Java/jdk-21")
            if java21.exists():
                env["JAVA_HOME"] = str(java21)
                env["PATH"] = f"{java21}\\bin;{env.get('PATH', '')}"

        # 1. Install dependencies if needed
        is_node_project = "React" in project_type or "Angular" in project_type or "Node" in project_type
        if is_node_project:
            self.add_log(repo_name, ">>> [Phase 1/2] Installing npm dependencies...")
            install_cmd = "npm install"
            try:
                process = await asyncio.create_subprocess_shell(
                    install_cmd,
                    cwd=str(run_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    env=env
                )
                
                # Stream npm install output
                async def read_stdout():
                    async for line in process.stdout:
                        self.add_log(repo_name, line.decode('utf-8', errors='replace'))
                
                await asyncio.gather(read_stdout(), process.wait())
                
                if process.returncode != 0:
                    self.runs[repo_name]["status"] = "FAILED"
                    self.runs[repo_name]["error_reason"] = "Failed to install npm dependencies. Check log console."
                    self.add_log(repo_name, f"\nError: npm install failed with exit code {process.returncode}")
                    return
                self.add_log(repo_name, ">>> [Phase 1/2] Dependency installation complete!\n")
            except Exception as e:
                self.runs[repo_name]["status"] = "FAILED"
                self.runs[repo_name]["error_reason"] = f"Dependency installation error: {str(e)}"
                self.add_log(repo_name, f"\nDependency installation error: {str(e)}")
                return

        # 2. Build and start running command
        self.add_log(repo_name, ">>> [Phase 2/2] Launching application server...")
        
        # Configure run command based on project type
        run_cmd = ""
        if project_type == "Spring Boot / Maven" or project_type == "Spring Boot / Thymeleaf" or project_type == "Spring Boot / JSP":
            mvn_cmd = "mvn.cmd" if is_windows else "mvn"
            local_maven = app_config.project_root / "apache-maven-3.9.6" / "bin" / mvn_cmd
            if local_maven.exists():
                mvn_cmd = str(local_maven)
            
            wrapper = run_dir / ("mvnw.cmd" if is_windows else "mvnw")
            wrapper_jar = run_dir / ".mvn" / "wrapper" / "maven-wrapper.jar"
            if wrapper.exists() and wrapper_jar.exists():
                mvn_cmd = str(wrapper)
            
            # Run with server port argument
            run_cmd = f'"{mvn_cmd}" spring-boot:run -Dspring-boot.run.arguments=--server.port={port}'

        elif project_type == "Spring Boot / Gradle":
            gradle_cmd = "gradlew.bat" if is_windows else "./gradlew"
            wrapper = run_dir / ("gradlew.bat" if is_windows else "gradlew")
            if not wrapper.exists():
                gradle_cmd = "gradle.bat" if is_windows else "gradle"
            else:
                gradle_cmd = str(wrapper)
            
            run_cmd = f"{gradle_cmd} bootRun --args='--server.port={port}'"

        elif project_type == "React / Vite":
            # Vite handles port through double dash or port argument
            run_cmd = f"npx vite --port {port} --host 127.0.0.1"

        elif project_type == "Angular":
            run_cmd = f"npx ng serve --port {port} --host 127.0.0.1"

        elif project_type == "Node.js frontend":
            env["PORT"] = str(port)
            run_cmd = "npm start"

        else:
            # Catch all fallback
            self.runs[repo_name]["status"] = "FAILED"
            self.runs[repo_name]["error_reason"] = f"Unsupported or unknown project type '{project_type}'."
            self.add_log(repo_name, f"Error: Cannot determine run scripts for type '{project_type}'.")
            return

        self.add_log(repo_name, f"Executing: {run_cmd}\n")

        try:
            # Run command in subshell to cleanly execute scripts/batch files
            process = await asyncio.create_subprocess_shell(
                run_cmd,
                cwd=str(run_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env
            )
            self.runs[repo_name]["process"] = process

            # Monitor the port in the background
            port_task = asyncio.create_task(self.monitor_port(repo_name, port))

            # Stream logs line by line
            async def stream_logs():
                async for line in process.stdout:
                    self.add_log(repo_name, line.decode('utf-8', errors='replace'))
            
            log_task = asyncio.create_task(stream_logs())

            # Wait for either port to activate or process to end
            while not port_task.done() and not log_task.done():
                await asyncio.sleep(0.5)

            if port_task.done() and port_task.result():
                # Server is up and running!
                self.runs[repo_name]["status"] = "RUNNING"
                
                # Expose the preview through the backend proxy route so the iframe
                # always loads through the Migration Accelerator host.
                preview_url = f"/api/run/preview/{repo_name}"
                self.runs[repo_name]["preview_url"] = preview_url
                self.add_log(repo_name, f"\n>>> SERVER IS LIVE AND RUNNING AT: {preview_url} (Proxied) <<<")

                # If Spring Boot, parse available RestController endpoints
                if "Spring Boot" in project_type:
                    endpoints = self.extract_java_endpoints(run_dir)
                    self.runs[repo_name]["endpoints"] = endpoints
                    self.add_log(repo_name, f"Parsed {len(endpoints)} Java REST Endpoint mappings.")
            else:
                # Process exited or port connection timed out
                if not port_task.done():
                    port_task.cancel()
                
                if process.returncode is not None:
                    self.runs[repo_name]["status"] = "FAILED"
                    self.runs[repo_name]["error_reason"] = f"Application server exited unexpectedly with return code {process.returncode}."
                    self.add_log(repo_name, f"\nError: Process terminated with exit code {process.returncode}")
                else:
                    self.runs[repo_name]["status"] = "FAILED"
                    self.runs[repo_name]["error_reason"] = "Server port activation timeout (60 seconds). Server failed to start."
                    self.add_log(repo_name, "\nError: Server port activation timeout reached.")

            # Keep reading logs until EOF in background if it's running
            await log_task

        except Exception as e:
            self.runs[repo_name]["status"] = "FAILED"
            self.runs[repo_name]["error_reason"] = f"Execution error: {str(e)}"
            self.add_log(repo_name, f"\nExecution exception occurred: {str(e)}")
            
    async def stop_project(self, repo_name: str):
        """Kills the active project run and frees the ports."""
        run = self.runs.get(repo_name)
        if not run:
            return

        process = run.get("process")
        if process:
            try:
                import os
                if os.name == 'nt':
                    # Windows process tree kill to prevent orphan command processors and server processes
                    subprocess.run(
                        f"taskkill /F /T /PID {process.pid}", 
                        shell=True, 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )
                else:
                    process.terminate()
                    await process.wait()
            except Exception as e:
                self.add_log(repo_name, f"Error terminating process tree: {str(e)}")
                
        proxy_process = run.get("proxy_process")
        if proxy_process:
            try:
                import os
                if os.name == 'nt':
                    subprocess.run(
                        f"taskkill /F /T /PID {proxy_process.pid}", 
                        shell=True, 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )
                else:
                    proxy_process.terminate()
                    await proxy_process.wait()
            except Exception as e:
                self.add_log(repo_name, f"Error terminating proxy process tree: {str(e)}")

        run["status"] = "STOPPED"
        run["process"] = None
        run["proxy_process"] = None
        run["preview_url"] = None
        self.add_log(repo_name, ">>> Application server stopped. <<<")
        
        # Send EOF to websockets
        if repo_name in self.log_queues:
            for q in self.log_queues[repo_name]:
                q.put_nowait(None)

    def get_status(self, repo_name: str) -> Dict[str, Any]:
        """Gets current execution metadata of a repository."""
        run = self.runs.get(repo_name)
        if not run:
            return {
                "repoName": repo_name,
                "status": "IDLE",
                "port": None,
                "projectType": None,
                "previewUrl": None,
                "endpoints": [],
                "errorReason": None
            }
        return {
            "repoName": repo_name,
            "status": run["status"],
            "port": run["port"],
            "projectType": run["type"],
            "previewUrl": run["preview_url"],
            "endpoints": run["endpoints"],
            "errorReason": run["error_reason"]
        }

    def get_logs(self, repo_name: str) -> str:
        """Returns all accumulated console logs."""
        run = self.runs.get(repo_name)
        if not run:
            return ""
        return "".join(run["logs"])

project_runner_service = ProjectRunnerService()
