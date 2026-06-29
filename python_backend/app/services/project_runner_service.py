import os
import re
import socket
import asyncio
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import app_config
from app.services.java_runtime_service import java_runtime_service

class ProjectRunnerService:
    WEB_DEPENDENCY_MARKERS = (
        "spring-boot-starter-web",
        "spring-boot-starter-webflux",
        "spring-webmvc",
        "spring-webflux",
        "tomcat-embed-jasper",
        "jstl",
        "jakarta.servlet",
        "javax.servlet",
    )
    WEB_SOURCE_MARKERS = (
        "@restcontroller",
        "@controller",
        "@requestmapping",
        "@getmapping",
        "@postmapping",
        "@putmapping",
        "@deletemapping",
        "extends httpservlet",
        "implements servlet",
    )
    CLI_SOURCE_MARKERS = (
        "commandlinerunner",
        "applicationrunner",
    )

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

        if (run_dir / "requirements.txt").exists() or (run_dir / "pyproject.toml").exists():
            return "Python"
        
        if list(run_dir.glob("*.csproj")):
            return ".NET"
            
        if (run_dir / "Cargo.toml").exists():
            return "Rust"

        return "Unknown"

    def detect_java_preview_mode(self, run_dir: Path, project_type: str) -> str:
        """Classify Java/Spring Boot apps as web, cli, rest-api, or unknown."""
        if not project_type.startswith("Spring Boot"):
            return "unknown"

        if project_type in {"Spring Boot / Thymeleaf", "Spring Boot / JSP"}:
            return "web"

        build_content = self._read_build_content(run_dir)
        build_lower = build_content.lower()

        if any(marker in build_lower for marker in self.WEB_DEPENDENCY_MARKERS):
            # Check for Thymeleaf/JSP even in Maven build file
            if "thymeleaf" in build_lower:
                return "web"
            if "tomcat-embed-jasper" in build_lower or "jstl" in build_lower:
                return "web"
            # Has web dependency — check if it also has MVC controllers (HTML UI)
            # vs pure REST (no HTML templates)
            has_templates = (
                (run_dir / "src" / "main" / "resources" / "templates").exists()
                or (run_dir / "src" / "main" / "webapp").exists()
                or (run_dir / "src" / "main" / "resources" / "static" / "index.html").exists()
            )
            if has_templates:
                return "web"
            # Check Java sources for @Controller (MVC) vs @RestController
            source_markers = self.scan_java_source_markers(run_dir)
            if source_markers.get("mvc_controller"):
                return "web"
            return "rest-api"

        if "<packaging>war</packaging>" in build_lower:
            return "web"
        if re.search(r'(^|\s)id\s*[("\']war[)"\']', build_lower) or "apply plugin: 'war'" in build_lower or 'apply plugin: "war"' in build_lower:
            return "web"

        source_markers = self.scan_java_source_markers(run_dir)
        if source_markers["web"]:
            return "web"

        if source_markers["cli_runner"] and not source_markers["web"]:
            return "cli"

        if source_markers["main"] and not source_markers["web"] and not any(marker in build_lower for marker in self.WEB_DEPENDENCY_MARKERS):
            return "cli"

        return "unknown"

    def _read_build_content(self, run_dir: Path) -> str:
        for build_file in (run_dir / "pom.xml", run_dir / "build.gradle", run_dir / "build.gradle.kts"):
            if build_file.exists():
                try:
                    return build_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    return ""
        return ""

    def scan_java_source_markers(self, run_dir: Path) -> Dict[str, bool]:
        markers = {
            "web": False,
            "mvc_controller": False,  # @Controller (HTML MVC) specifically
            "cli_runner": False,
            "main": False,
        }
        scanned = 0
        for path in run_dir.rglob("*"):
            if path.suffix.lower() not in {".java", ".kt", ".groovy"}:
                continue
            if any(part in {"target", "build", ".git", "node_modules"} for part in path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
            except Exception:
                continue

            scanned += 1
            if any(marker in content for marker in self.WEB_SOURCE_MARKERS):
                markers["web"] = True
            # Detect @Controller without @RestController for MVC UI detection
            if "@controller" in content and "@restcontroller" not in content:
                markers["mvc_controller"] = True
            if any(marker in content for marker in self.CLI_SOURCE_MARKERS):
                markers["cli_runner"] = True
            if "static void main(" in content or "fun main(" in content:
                markers["main"] = True

            if markers["web"]:
                return markers
            if scanned >= 200:
                break

        return markers

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

    def detect_swagger_url(self, run_dir: Path, port: int) -> Optional[str]:
        """Check if the project has Swagger/OpenAPI and return the likely URL."""
        build_content = self._read_build_content(run_dir).lower()
        if "springdoc-openapi" in build_content:
            return f"http://127.0.0.1:{port}/swagger-ui.html"
        if "springfox" in build_content or "swagger" in build_content:
            return f"http://127.0.0.1:{port}/swagger-ui/index.html"
        return None

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

    def detect_preferred_preview_path(self, run_dir: Path, project_type: str) -> Optional[str]:
        """Pick a better initial preview path for MVC apps when root is not mapped."""
        if project_type not in {"Spring Boot / Thymeleaf", "Spring Boot / JSP", "Spring Boot / Maven", "Spring Boot / Gradle"}:
            return None

        candidates = []
        for path in run_dir.rglob("*.java"):
            if any(part in {"target", "build", ".git", "node_modules"} for part in path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lower_content = content.lower()
            if "@controller" not in lower_content or "@restcontroller" in lower_content:
                continue

            class_mapping = ""
            class_match = re.search(
                r'@RequestMapping\s*\(\s*(?:value|path)\s*=\s*["\']([^"\']+)["\']\s*\)',
                content,
                flags=re.IGNORECASE,
            )
            if not class_match:
                class_match = re.search(
                    r'@RequestMapping\s*\(\s*["\']([^"\']+)["\']\s*\)',
                    content,
                    flags=re.IGNORECASE,
                )
            if class_match:
                class_mapping = class_match.group(1)

            pattern = re.compile(
                r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)\s*\((.*?)\)\s*'
                r'(?:public|private|protected)?\s*[\w<>\[\], ?]+\s+\w+\s*\(',
                re.IGNORECASE | re.DOTALL,
            )

            for match in pattern.finditer(content):
                annotation_type = match.group(1).lower()
                annotation_body = match.group(2)
                path_match = re.search(
                    r'(?:value|path)\s*=\s*["\']([^"\']+)["\']|["\']([^"\']+)["\']',
                    annotation_body,
                    flags=re.IGNORECASE,
                )
                if not path_match:
                    if annotation_type == "requestmapping":
                        candidates.append("/")
                    continue

                path_value = path_match.group(1) or path_match.group(2) or ""
                full_path = "/" + (class_mapping.strip("/") + "/" + path_value.strip("/")).strip("/")
                full_path = full_path if full_path != "" else "/"

                if annotation_type == "requestmapping":
                    method_match = re.search(r'RequestMethod\.(GET|POST|PUT|DELETE)', annotation_body, flags=re.IGNORECASE)
                    if method_match and method_match.group(1).upper() != "GET":
                        continue

                if annotation_type in {"getmapping", "requestmapping"}:
                    candidates.append(full_path or "/")

        if not candidates:
            return None

        normalized = []
        seen = set()
        for candidate in candidates:
            cleaned = candidate if candidate.startswith("/") else f"/{candidate}"
            cleaned = re.sub(r"/{2,}", "/", cleaned)
            if cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)

        if "/" in seen:
            return "/"

        for candidate in normalized:
            if (
                candidate != "/"
                and not candidate.startswith("/api")
                and "{" not in candidate
                and "*" not in candidate
            ):
                return candidate

        return normalized[0]

    def sanitize_yaml_credentials(self, resources_dir: Path, repo_name: str):
        """Quote masked credential placeholders so SnakeYAML can parse them."""
        for filename in ("application.yaml", "application.yml"):
            yaml_path = resources_dir / filename
            if not yaml_path.exists():
                continue
            try:
                content = yaml_path.read_text(encoding="utf-8", errors="ignore")
                updated = re.sub(
                    r'(^\s*password:\s*)(\*{3,}.*)$',
                    lambda match: f'{match.group(1)}"{match.group(2).strip()}"',
                    content,
                    flags=re.MULTILINE,
                )
                if updated != content:
                    yaml_path.write_text(updated, encoding="utf-8")
                    self.add_log(repo_name, f"[DB Config] Sanitized masked password in {filename}.")
            except Exception as e:
                self.add_log(repo_name, f"[DB Config Warning] Could not sanitize {filename}: {e}")

    def _runtime_overlay_dir(self, repo_name: str) -> Path:
        return app_config.workspace_directory / ".runtime_overrides" / repo_name

    def _ensure_backup(self, repo_name: str, original_path: Path, run_dir: Path) -> Optional[Path]:
        run = self.runs.get(repo_name)
        if not run or not original_path.exists():
            return None

        try:
            relative_path = original_path.relative_to(run_dir)
        except Exception:
            relative_path = Path(original_path.name)

        backup_root = self._runtime_overlay_dir(repo_name) / "backups"
        backup_path = backup_root / relative_path
        if backup_path.exists():
            return backup_path

        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original_path, backup_path)
        run.setdefault("runtime_backups", []).append({
            "original": str(original_path),
            "backup": str(backup_path)
        })
        return backup_path

    def _restore_runtime_overrides(self, repo_name: str):
        run = self.runs.get(repo_name)
        if not run:
            return

        for entry in reversed(run.get("runtime_backups", [])):
            original = Path(entry["original"])
            backup = Path(entry["backup"])
            try:
                if backup.exists():
                    original.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, original)
            except Exception as e:
                self.add_log(repo_name, f"[DB Config Warning] Could not restore {original.name}: {e}")

        for injected in run.get("injected_files", []):
            try:
                p = Path(injected)
                if p.exists():
                    p.unlink()
            except Exception:
                pass

        overlay_dir = run.get("runtime_overlay_dir")
        if overlay_dir:
            try:
                shutil.rmtree(Path(overlay_dir), ignore_errors=True)
            except Exception:
                pass

        run["runtime_backups"] = []
        run["injected_files"] = []
        run["runtime_overlay_dir"] = None

    def _detect_external_db_config(self, run_dir: Path) -> bool:
        db_markers = ("mysql", "postgres", "postgresql", "jdbc:mysql", "jdbc:postgresql")
        candidate_files = [
            run_dir / "pom.xml",
            run_dir / "build.gradle",
            run_dir / "build.gradle.kts",
        ]

        resources_dir = run_dir / "src" / "main" / "resources"
        if resources_dir.exists():
            for filename in ("application.properties", "application.yml", "application.yaml"):
                candidate_files.append(resources_dir / filename)

        for candidate in candidate_files:
            if not candidate.exists():
                continue
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore").lower()
                if any(marker in content for marker in db_markers):
                    return True
            except Exception:
                continue
        return False

    def _find_spring_boot_main_class(self, run_dir: Path) -> Optional[Path]:
        for path in run_dir.rglob("*.java"):
            if any(part in {"target", "build", ".git", "node_modules"} for part in path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if "@SpringBootApplication" in content:
                    return path
            except Exception:
                continue
        return None

    def _find_main_class_name(self, run_dir: Path) -> Optional[str]:
        """Find the fully-qualified name of the main entry class for exec:java."""
        # First try @SpringBootApplication
        for path in run_dir.rglob("*.java"):
            if any(part in {"target", "build", ".git", "node_modules"} for part in path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                has_main = "@SpringBootApplication" in content or (
                    "public static void main" in content and ("SpringApplication" in content or "@SpringBootApplication" in content)
                )
                if not has_main:
                    continue
                pkg_match = re.search(r'package\s+([\w\.]+);', content)
                cls_match = re.search(r'public\s+class\s+(\w+)', content)
                if cls_match:
                    package = pkg_match.group(1) + "." if pkg_match else ""
                    return package + cls_match.group(1)
            except Exception:
                continue

        # Fallback: any class with public static void main(String[] args)
        for path in run_dir.rglob("*.java"):
            if any(part in {"target", "build", ".git", "node_modules"} for part in path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if "public static void main" not in content:
                    continue
                pkg_match = re.search(r'package\s+([\w\.]+);', content)
                cls_match = re.search(r'public\s+class\s+(\w+)', content)
                if cls_match:
                    package = pkg_match.group(1) + "." if pkg_match else ""
                    return package + cls_match.group(1)
            except Exception:
                continue
        return None



    def _inject_spring_boot_plugin(self, build_file: Path, repo_name: str, run_dir: Path) -> bool:
        if build_file.name != "pom.xml":
            return False
            
        try:
            content = build_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return False

        if "spring-boot-maven-plugin" in content.lower():
            return False

        self._ensure_backup(repo_name, build_file, run_dir)
        self.add_log(repo_name, f"[Build Config] Temporarily adding spring-boot-maven-plugin to {build_file.name} for preview run...")

        # Quick fix for missing maven-war-plugin version which breaks Java 21 builds
        if "<artifactId>maven-war-plugin</artifactId>" in content and "<version>" not in content.split("<artifactId>maven-war-plugin</artifactId>")[1].split("</plugin>")[0]:
            content = content.replace(
                "<artifactId>maven-war-plugin</artifactId>", 
                "<artifactId>maven-war-plugin</artifactId>\n                <version>3.4.0</version>"
            )

        plugin_block = (
            "            <plugin>\n"
            "                <groupId>org.springframework.boot</groupId>\n"
            "                <artifactId>spring-boot-maven-plugin</artifactId>\n"
            "                <version>3.2.5</version>\n"
            "            </plugin>\n"
        )
        
        if "<plugins>" in content:
            content = content.replace("<plugins>", f"<plugins>\n{plugin_block}", 1)
        elif "<build>" in content:
            content = content.replace("<build>", f"<build>\n        <plugins>\n{plugin_block}        </plugins>\n", 1)
        elif "</project>" in content:
            content = content.replace(
                "</project>",
                f"    <build>\n        <plugins>\n{plugin_block}        </plugins>\n    </build>\n</project>",
                1
            )
        else:
            return False

        build_file.write_text(content, encoding="utf-8")
        return True

    def _inject_h2_dependency(self, build_file: Path, repo_name: str, run_dir: Path) -> bool:
        try:
            content = build_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            self.add_log(repo_name, f"[DB Config Warning] Could not read {build_file.name}: {e}")
            return False

        if "com.h2database" in content.lower():
            return False

        self._ensure_backup(repo_name, build_file, run_dir)
        self.add_log(repo_name, f"[DB Config] Temporarily adding H2 dependency to {build_file.name} for preview run...")

        if build_file.name == "pom.xml":
            dependency_block = (
                "    <dependency>\n"
                "        <groupId>com.h2database</groupId>\n"
                "        <artifactId>h2</artifactId>\n"
                "        <scope>runtime</scope>\n"
                "    </dependency>\n"
            )
            if "</dependencies>" in content:
                content = content.replace("</dependencies>", f"{dependency_block}</dependencies>", 1)
            elif "</project>" in content:
                content = content.replace(
                    "</project>",
                    f"  <dependencies>\n{dependency_block}  </dependencies>\n</project>",
                    1
                )
            else:
                content += f"\n<dependencies>\n{dependency_block}</dependencies>\n"
        elif build_file.name == "build.gradle.kts":
            dependency_snippet = "\n    runtimeOnly(\"com.h2database:h2\")\n"
            if "dependencies {" in content:
                content = content.replace("dependencies {", f"dependencies {{{dependency_snippet}", 1)
            else:
                content += f"\ndependencies {{{dependency_snippet}}}\n"
        else:
            dependency_snippet = "\n    runtimeOnly 'com.h2database:h2'\n"
            if "dependencies {" in content:
                content = content.replace("dependencies {", f"dependencies {{{dependency_snippet}", 1)
            else:
                content += f"\ndependencies {{{dependency_snippet}}}\n"

        build_file.write_text(content, encoding="utf-8")
        return True

    def _prepare_h2_runtime_overlay(self, repo_name: str, run_dir: Path, port: int, db_detected: bool, env: dict):
        overlay_dir = self._runtime_overlay_dir(repo_name)
        overlay_dir.mkdir(parents=True, exist_ok=True)
        self.runs[repo_name]["runtime_overlay_dir"] = str(overlay_dir)

        props_path = overlay_dir / "application-migration.properties"
        props_content = [
            f"server.port={port}",
        ]
        if db_detected:
            props_content.extend([
                "spring.datasource.url=jdbc:h2:mem:testdb",
                "spring.datasource.driverClassName=org.h2.Driver",
                "spring.datasource.username=sa",
                "spring.datasource.password=",
                "spring.jpa.hibernate.ddl-auto=update",
                "spring.h2.console.enabled=true",
            ])

        props_path.write_text("\n".join(props_content) + "\n", encoding="utf-8")

        overlay_uri = overlay_dir.resolve().as_uri()
        existing = env.get("SPRING_CONFIG_ADDITIONAL_LOCATION")
        env["SPRING_CONFIG_ADDITIONAL_LOCATION"] = f"{existing},{overlay_uri}/" if existing else f"{overlay_uri}/"
        env["SPRING_PROFILES_ACTIVE"] = "migration"
        if db_detected:
            env["SPRING_DATASOURCE_URL"] = "jdbc:h2:mem:testdb"
            env["SPRING_DATASOURCE_DRIVERCLASSNAME"] = "org.h2.Driver"
            env["SPRING_DATASOURCE_USERNAME"] = "sa"
            env["SPRING_DATASOURCE_PASSWORD"] = ""
            env["SPRING_JPA_HIBERNATE_DDL_AUTO"] = "update"
            env["SPRING_H2_CONSOLE_ENABLED"] = "true"

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
            "preview_mode": "unknown",
            "preferred_preview_path": None,
            "preview_url": None,
            "endpoints": [],
            "error_reason": None,
            "process": None,
            "runtime_backups": [],
            "runtime_overlay_dir": None
        }

        # Run startup task in background
        asyncio.create_task(self._run_lifecycle(repo_name, run_dir, project_type, port))

    async def _run_lifecycle(self, repo_name: str, run_dir: Path, project_type: str, port: int):
        self.add_log(repo_name, f"=== RUN PROJECT LOGS FOR '{repo_name}' ===")
        self.add_log(repo_name, f"Detected Project Type: {project_type}")
        self.add_log(repo_name, f"Allocated Local Port: {port}")
        self.add_log(repo_name, f"WorkingDirectory: {run_dir}\n")

        is_windows = os.name == 'nt'
        env, java_home = java_runtime_service.prepare_env(project_dir=run_dir)
        
        # Polyglot Auto-Environment Injection
        env_file = run_dir / ".env"
        env_example = run_dir / ".env.example"
        if env_example.exists() and not env_file.exists():
            import shutil
            shutil.copy2(env_example, env_file)
            self.add_log(repo_name, f"[Env Config] Auto-copied .env.example to .env to prevent missing variable crashes.")
        
        preview_mode = self.detect_java_preview_mode(run_dir, project_type)
        preferred_preview_path = self.detect_preferred_preview_path(run_dir, project_type)
        self.runs[repo_name]["preview_mode"] = preview_mode
        self.runs[repo_name]["preferred_preview_path"] = preferred_preview_path

        if project_type.startswith("Spring Boot"):
            self.add_log(repo_name, f"Detected Preview Mode: {preview_mode}")
            if preferred_preview_path:
                self.add_log(repo_name, f"Detected Initial Preview Path: {preferred_preview_path}")
            if java_home:
                self.add_log(repo_name, f"[Java Runtime] Using selected JDK at: {java_home}")

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
        

        # Database Handling: Add safe H2 fallback profile if DB detected
        db_detected = False
        try:
            if project_type.startswith("Spring Boot"):
                db_detected = self._detect_external_db_config(run_dir)
                if db_detected:
                    self.add_log(repo_name, "[DB Config] External DB detected. Using preview-only H2 runtime overlay.")

                for build_file in [run_dir / "pom.xml", run_dir / "build.gradle", run_dir / "build.gradle.kts"]:
                    if build_file.exists():
                        try:
                            content = build_file.read_text(encoding='utf-8', errors='ignore').lower()
                            if "com.h2database" not in content and db_detected:
                                self._inject_h2_dependency(build_file, repo_name, run_dir)
                            
                            if build_file.name == "pom.xml":
                                self._inject_spring_boot_plugin(build_file, repo_name, run_dir)
                        except Exception:
                            pass
                        break

                self._prepare_h2_runtime_overlay(repo_name, run_dir, port, db_detected, env)
        except Exception as e:
            self.add_log(repo_name, f"[DB Config Warning] Could not inject H2 profile: {e}")

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
            
            # Determine if this is a true Spring Boot project (has spring-boot-starter-parent)
            # If not, spring-boot:run will fail even with plugin injection -> use exec:java instead
            pom_content = ""
            pom_file = run_dir / "pom.xml"
            if pom_file.exists():
                try:
                    pom_content = pom_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass
            
            has_boot_parent = "spring-boot-starter-parent" in pom_content
            has_boot_plugin = "spring-boot-maven-plugin" in pom_content.lower()
            
            if has_boot_parent or has_boot_plugin:
                # Genuine Spring Boot project - use spring-boot:run
                run_cmd = f'"{mvn_cmd}" spring-boot:run -Dspring-boot.run.profiles=migration'
            else:
                # Not a Spring Boot parent project - find main class and use exec:java
                self.add_log(repo_name, "[Run Strategy] No spring-boot-starter-parent found. Using exec:java strategy.")
                main_class = self._find_main_class_name(run_dir)
                if main_class:
                    self.add_log(repo_name, f"[Run Strategy] Detected main class: {main_class}")
                    run_cmd = (
                        f'"{mvn_cmd}" compile exec:java '
                        f'-Dexec.mainClass="{main_class}" '
                        f'-Dexec.args="--server.port={port} --spring.profiles.active=migration" '
                        f'-DskipTests=true'
                    )
                else:
                    # Last resort: try spring-boot:run anyway (plugin was injected)
                    self.add_log(repo_name, "[Run Strategy] Could not detect main class. Attempting spring-boot:run anyway.")
                    run_cmd = f'"{mvn_cmd}" spring-boot:run -Dspring-boot.run.profiles=migration'

        elif project_type == "Spring Boot / Gradle":
            gradle_cmd = "gradlew.bat" if is_windows else "./gradlew"
            wrapper = run_dir / ("gradlew.bat" if is_windows else "gradlew")
            if not wrapper.exists():
                gradle_cmd = "gradle.bat" if is_windows else "gradle"
            else:
                gradle_cmd = str(wrapper)
            
            # Use args for Gradle profile activation
            run_cmd = f'{gradle_cmd} bootRun --args="--spring.profiles.active=migration"'

        elif project_type == "React / Vite":
            # Vite handles port through double dash or port argument
            run_cmd = f"npx vite --port {port} --host 127.0.0.1"

        elif project_type == "Angular":
            run_cmd = f"npx ng serve --port {port} --host 127.0.0.1"

        elif project_type == "Node.js frontend":
            env["PORT"] = str(port)
            run_cmd = "npm start"
            
        elif project_type == "Python":
            env["PORT"] = str(port)
            if (run_dir / "main.py").exists():
                run_cmd = f"python main.py"
            elif (run_dir / "app.py").exists():
                run_cmd = f"python app.py"
            else:
                run_cmd = "uvicorn main:app --port " + str(port)
                
        elif project_type == ".NET":
            env["ASPNETCORE_URLS"] = f"http://localhost:{port}"
            run_cmd = "dotnet run"
            
        elif project_type == "Rust":
            env["PORT"] = str(port)
            run_cmd = "cargo run"

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

            # Stream logs line by line
            async def stream_logs():
                async for line in process.stdout:
                    self.add_log(repo_name, line.decode('utf-8', errors='replace'))
            
            log_task = asyncio.create_task(stream_logs())

            if preview_mode == "cli":
                await process.wait()
                await log_task

                if process.returncode == 0:
                    self.runs[repo_name]["status"] = "STOPPED"
                    self.runs[repo_name]["error_reason"] = None
                    self.runs[repo_name]["preview_url"] = None
                    self.add_log(repo_name, "\n>>> Non-web CLI application completed successfully. <<<")
                else:
                    self.runs[repo_name]["status"] = "FAILED"
                    self.runs[repo_name]["error_reason"] = f"CLI application exited with return code {process.returncode}."
                    self.add_log(repo_name, f"\nError: Process terminated with exit code {process.returncode}")

            elif preview_mode == "rest-api":
                # REST-only app: wait for port, then mark RUNNING_JAVA (no iframe preview)
                port_task = asyncio.create_task(self.monitor_port(repo_name, port))
                while not port_task.done() and not log_task.done():
                    await asyncio.sleep(0.5)

                if port_task.done() and port_task.result():
                    self.runs[repo_name]["status"] = "RUNNING_API"
                    swagger_url = self.detect_swagger_url(run_dir, port)
                    self.runs[repo_name]["swagger_url"] = swagger_url
                    endpoints = self.extract_java_endpoints(run_dir)
                    self.runs[repo_name]["endpoints"] = endpoints
                    self.runs[repo_name]["no_ui_message"] = (
                        "This project does not contain a web user interface. "
                        f"It is a REST API application running on port {port}. "
                        f"Found {len(endpoints)} API endpoint(s)."
                        + (f" Swagger UI available at: {swagger_url}" if swagger_url else "")
                    )
                    self.add_log(repo_name, f"\n>>> REST API is LIVE on port {port} (No HTML UI) <<<")
                    if swagger_url:
                        self.add_log(repo_name, f">>> Swagger UI: {swagger_url} <<<")
                else:
                    if not port_task.done():
                        port_task.cancel()
                    self.runs[repo_name]["status"] = "FAILED"
                    self.runs[repo_name]["error_reason"] = "REST API server failed to start within 60 seconds."
                    self.add_log(repo_name, "\nError: Server port activation timeout reached.")
                await log_task

            else:
                # Preserve the existing port-waiting behavior when detection is web or uncertain.
                port_task = asyncio.create_task(self.monitor_port(repo_name, port))

                # Wait for either port to activate or process to end
                while not port_task.done() and not log_task.done():
                    await asyncio.sleep(0.5)

                if port_task.done() and port_task.result():
                    # Server is up and running!
                    self.runs[repo_name]["status"] = "RUNNING"
                    
                    # Expose the preview through the backend proxy route so the iframe
                    # always loads through the Migration Accelerator host.
                    if preferred_preview_path and preferred_preview_path != "/":
                        preview_url = f"/api/run/preview/{repo_name}/{preferred_preview_path.lstrip('/')}"
                    else:
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
        finally:
            if self.runs.get(repo_name, {}).get("status") == "FAILED":
                self._restore_runtime_overrides(repo_name)
            
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

        self._restore_runtime_overrides(repo_name)
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
                "errorReason": None,
                "noUiMessage": None,
                "swaggerUrl": None,
            }
        return {
            "repoName": repo_name,
            "status": run["status"],
            "port": run["port"],
            "projectType": run["type"],
            "previewUrl": run["preview_url"],
            "endpoints": run["endpoints"],
            "errorReason": run["error_reason"],
            "noUiMessage": run.get("no_ui_message"),
            "swaggerUrl": run.get("swagger_url"),
        }

    def get_logs(self, repo_name: str) -> str:
        """Returns all accumulated console logs."""
        run = self.runs.get(repo_name)
        if not run:
            return ""
        return "".join(run["logs"])

project_runner_service = ProjectRunnerService()
