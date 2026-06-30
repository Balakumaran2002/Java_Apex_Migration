import hashlib
import json
import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import fnmatch

from app.ai.ai_factory import AIFactory
from app.ai.provider_manager import NoAvailableAIKeyError
from app.config import app_config
from app.services.java_compatibility_service import java_compatibility_service
from app.services.llm_runtime_service import llm_runtime_service


class LLMMigrationEngine:
    IGNORE_DIRS = {".git", "target", "build", "node_modules", ".idea", ".vscode", ".mvn", "__pycache__", ".gradle"}
    CONFIG_FILENAMES = {"pom.xml", "build.gradle", "build.gradle.kts", "application.properties", "application.yml", "application.yaml", "bootstrap.properties", "bootstrap.yml", "bootstrap.yaml", "logback-spring.xml"}
    JAVA_HINTS = (
        "@SpringBootApplication",
        "@Configuration",
        "@Bean",
        "@RestController",
        "@Controller",
        "@Service",
        "@Repository",
        "@Component",
        "@ConfigurationProperties",
        "@RequestMapping",
        "@GetMapping",
        "@PostMapping",
        "@PutMapping",
        "@DeleteMapping",
        "WebSecurityConfigurerAdapter",
        "SecurityFilterChain",
        "javax.",
        "jakarta.",
        "RestTemplate",
        "ResponseEntity",
        "JpaRepository",
        "CrudRepository",
        "PageRequest",
        "Optional",
        "CompletableFuture",
        "Stream<",
        "Thread.sleep(",
        "Thread.stop()",
        "Thread.resume()",
        "Thread.suspend()",
    )
    JAKARTA_REPLACEMENTS = {
        "javax.annotation.": "jakarta.annotation.",
        "javax.persistence.": "jakarta.persistence.",
        "javax.validation.": "jakarta.validation.",
        "javax.servlet.": "jakarta.servlet.",
        "javax.transaction.": "jakarta.transaction.",
        "javax.inject.": "jakarta.inject.",
        "javax.ws.rs.": "jakarta.ws.rs.",
        "javax.xml.bind.": "jakarta.xml.bind.",
        "javax.mail.": "jakarta.mail.",
        "javax.faces.": "jakarta.faces.",
        "javax.el.": "jakarta.el.",
        "javax.jms.": "jakarta.jms.",
        "javax.activation.": "jakarta.activation.",
    }

    def __init__(self):
        self.ai_client = AIFactory.get_client()
        self._state_lock = threading.Lock()

    def clean_caches(self, project_dir: Path, output_log: List[str]):
        output_log.append("[Migration Engine] Cleaning build artifacts before migration...")
        for directory_name in ("target", ".gradle"):
            directory_path = project_dir / directory_name
            if directory_path.exists() and directory_path.is_dir():
                try:
                    shutil.rmtree(directory_path)
                except Exception:
                    pass

    def _resume_dir(self) -> Path:
        resume_dir = app_config.workspace_directory / ".migration_resume"
        resume_dir.mkdir(parents=True, exist_ok=True)
        return resume_dir

    def _resume_file(self, project_dir: Path) -> Path:
        return self._resume_dir() / f"{project_dir.name}.json"

    def _load_resume_state(self, project_dir: Path) -> dict:
        resume_file = self._resume_file(project_dir)
        if not resume_file.exists():
            return {"project": project_dir.name, "processed": {}}
        try:
            data = json.loads(resume_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("processed", {})
                data.setdefault("project", project_dir.name)
                return data
        except Exception:
            pass
        return {"project": project_dir.name, "processed": {}}

    def _save_resume_state(self, project_dir: Path, state: dict) -> None:
        resume_file = self._resume_file(project_dir)
        with self._state_lock:
            resume_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _analysis_report_path(self) -> Path:
        return app_config.workspace_directory / "reports" / "last_analysis.json"

    def _load_cached_analysis(self, project_dir: Path, output_log: List[str]) -> dict:
        report_path = self._analysis_report_path()
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                repo_name = project_dir.name
                repo_url = str(report.get("repoUrl", ""))
                if repo_url and repo_url.rstrip("/").split("/")[-1].replace(".git", "") == repo_name:
                    output_log.append("[Migration Engine] Reusing cached repository analysis from the last analysis run.")
                    return report
            except Exception:
                pass

        cache_file = app_config.workspace_directory / "analysis_cache.json"
        if cache_file.exists():
            try:
                cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
                repo_name = project_dir.name
                for entry in cache_data.values():
                    repo_url = str(entry.get("repoUrl", ""))
                    if repo_url.rstrip("/").split("/")[-1].replace(".git", "") == repo_name:
                        output_log.append("[Migration Engine] Reusing cached repository analysis from the analysis cache.")
                        return entry
            except Exception:
                pass

        output_log.append("[Migration Engine] No reusable analysis cache found; using a lightweight local scan.")
        return self._quick_project_metadata(project_dir)

    def _quick_project_metadata(self, project_dir: Path) -> dict:
        build_file = self._find_build_file(project_dir)
        build_tool = "Unknown"
        framework_type = "Plain Java"
        dependencies = []
        framework_versions = {}
        has_frontend = False
        frontend_framework = None

        if build_file:
            content = build_file.read_text(encoding="utf-8", errors="ignore")
            lower_content = content.lower()
            if build_file.name == "pom.xml":
                build_tool = "Maven"
                match = re.search(r"<version>(.*?)</version>", content, flags=re.IGNORECASE | re.DOTALL)
                if match:
                    framework_versions["Spring Boot"] = match.group(1).strip()
            elif build_file.name == "build.gradle.kts":
                build_tool = "Gradle Kotlin DSL"
            elif build_file.name == "build.gradle":
                build_tool = "Gradle"

            if "spring-boot" in lower_content:
                if "thymeleaf" in lower_content:
                    framework_type = "Spring Boot / Thymeleaf"
                elif "jsp" in lower_content or "jstl" in lower_content or "tomcat-embed-jasper" in lower_content:
                    framework_type = "Spring Boot / JSP"
                elif "spring-boot-starter-webflux" in lower_content:
                    framework_type = "Spring Boot / WebFlux (Reactive)"
                elif "spring-boot-starter-web" in lower_content or "spring-webmvc" in lower_content:
                    framework_type = "Spring Boot / Web MVC"
                else:
                    framework_type = "Spring Boot"

        package_json = self._find_frontend_package_json(project_dir)
        if package_json:
            has_frontend = True
            try:
                pkg = json.loads(package_json.read_text(encoding="utf-8", errors="ignore"))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if any(name.startswith("@angular") for name in deps):
                    frontend_framework = "Angular"
                elif "react" in deps or "react-dom" in deps:
                    frontend_framework = "React"
                elif "vue" in deps:
                    frontend_framework = "Vue"
                elif "next" in deps:
                    frontend_framework = "Next.js"
                else:
                    frontend_framework = "Node.js"
            except Exception:
                frontend_framework = "Node.js"

        java_files = [path for path in safe_rglob(project_dir, "*.java") if not self._is_skipped(path)]
        endpoint_count = 0
        for java_file in java_files[:200]:
            try:
                content = java_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            endpoint_count += len(re.findall(r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)', content))

        return {
            "repoUrl": str(project_dir),
            "projectType": "Java",
            "isJava": True,
            "detectedJavaVersion": "21",
            "buildTool": build_tool,
            "frameworkType": framework_type,
            "database": "None",
            "packagingType": "jar",
            "isMultiModule": False,
            "hasFrontend": has_frontend,
            "frontendFramework": frontend_framework,
            "endpointCount": endpoint_count,
            "riskLevel": "Low",
            "dependencies": dependencies,
            "frameworkVersions": framework_versions,
        }

    def _find_build_file(self, project_dir: Path) -> Optional[Path]:
        for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            candidate = project_dir / name
            if candidate.exists():
                return candidate
        for path in safe_rglob(project_dir, "pom.xml"):
            if self._is_skipped(path):
                continue
            return path
        for path in safe_rglob(project_dir, "build.gradle"):
            if self._is_skipped(path):
                continue
            return path
        for path in safe_rglob(project_dir, "build.gradle.kts"):
            if self._is_skipped(path):
                continue
            return path
        return None

    def _find_frontend_package_json(self, project_dir: Path) -> Optional[Path]:
        for package_json in safe_rglob(project_dir, "package.json"):
            if self._is_skipped(package_json):
                continue
            return package_json
        return None

    def _is_skipped(self, path: Path) -> bool:
        return any(part in self.IGNORE_DIRS or part.startswith(".") for part in path.parts)

    def _fingerprint(self, path: Path) -> str:
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception:
            return f"{path.stat().st_size}:{int(path.stat().st_mtime)}"

    def _strip_markdown(self, text: str) -> str:
        text = (text or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return text

    def _remove_openrewrite_blocks(self, content: str) -> str:
        updated = re.sub(
            r"\s*<plugin>.*?<artifactId>\s*rewrite-maven-plugin\s*</artifactId>.*?</plugin>",
            "",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        updated = re.sub(
            r"\s*<dependency>.*?<groupId>\s*org\.openrewrite.*?</dependency>",
            "",
            updated,
            flags=re.IGNORECASE | re.DOTALL,
        )
        updated = re.sub(
            r"\s*id\(['\"]org\.openrewrite\.rewrite['\"]\)\s*version\s*['\"][^'\"]+['\"]",
            "",
            updated,
            flags=re.IGNORECASE,
        )
        updated = re.sub(
            r"\s*rewrite\s*\{.*?\}\s*",
            "",
            updated,
            flags=re.IGNORECASE | re.DOTALL,
        )
        updated = re.sub(r"\n{3,}", "\n\n", updated)
        return updated.strip() + ("\n" if updated.endswith("\n") else "")

    def _fast_java_transform(self, content: str, target_version: str) -> Tuple[str, bool]:
        updated = content
        changed = False
        if int(target_version or "0") >= 17:
            for source, target in self.JAKARTA_REPLACEMENTS.items():
                if source in updated:
                    updated = updated.replace(source, target)
                    changed = True
        updated = updated.replace("org.openrewrite.", "")
        return updated, changed

    def _fast_config_transform(self, content: str, target_version: str) -> Tuple[str, bool]:
        updated = content
        changed = False
        if "openrewrite" in updated.lower():
            updated = self._remove_openrewrite_blocks(updated)
            changed = True
        if int(target_version or "0") >= 17 and "javax." in updated:
            for source, target in self.JAKARTA_REPLACEMENTS.items():
                if source in updated:
                    updated = updated.replace(source, target)
                    changed = True
        return updated, changed

    def _needs_llm(self, content: str) -> bool:
        if len(content) > int(os.getenv("LLM_MIGRATION_MAX_DIRECT_CHARS", "9000")):
            return True
        lower_content = content.lower()
        complex_markers = (
            "@controller",
            "@restcontroller",
            "@configuration",
            "@bean",
            "websecurityconfigureradapter",
            "securityfilterchain",
            "jpapaging",
            "entitymanager",
            "resttemplate",
            "applicationrunner",
            "commandlinerunner",
            "springapplication.run",
            "@transactional",
            "javax.",
            "jakarta.",
            "thread.stop()",
            "thread.resume()",
            "thread.suspend()",
        )
        return any(marker in lower_content for marker in complex_markers)

    def _extract_llm_snippet(self, content: str, max_lines: int = 220) -> str:
        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content

        marker_indexes = [
            index
            for index, line in enumerate(lines)
            if any(marker.lower() in line.lower() for marker in ("import ", "@", "class ", "interface ", "record ", "enum "))
        ]
        if not marker_indexes:
            return "\n".join(lines[:max_lines])

        selected = set()
        for index in marker_indexes[:12]:
            start = max(0, index - 15)
            end = min(len(lines), index + 25)
            selected.update(range(start, end))

        snippet_lines = [lines[index] for index in sorted(selected)]
        if len(snippet_lines) > max_lines:
            return "\n".join(snippet_lines[:max_lines])
        return "\n".join(snippet_lines)

    def _generate_with_timeout(self, prompt: str, system_instruction: str, api_key: str, model_name: str, timeout_seconds: int) -> str:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.ai_client.generate, prompt, system_instruction, api_key, model_name)
        try:
            return future.result(timeout=timeout_seconds)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _rewrite_with_llm(self, file_path: Path, content: str, target_version: str, api_key: str, model_name: str, output_log: List[str]) -> str:
        timeout_seconds = int(os.getenv("LLM_MIGRATION_REQUEST_TIMEOUT_SECONDS", "90"))
        snippet = self._extract_llm_snippet(content)
        prompt = (
            f"You are migrating a Java {target_version} codebase.\n"
            f"Update the following source file only where needed.\n"
            f"Preserve all business logic, endpoints, behavior, and architecture.\n"
            f"Return raw source code only.\n\n"
            f"File: {file_path.name}\n\n{snippet}"
        )
        system_instruction = "You are an automated Java migration engine. Output raw source code only."
        try:
            return self._strip_markdown(self._generate_with_timeout(prompt, system_instruction, api_key, model_name, timeout_seconds))
        except TimeoutError:
            output_log.append(f"[Migration Engine] LLM timeout on {file_path.name}; splitting into smaller chunks.")
            return self._rewrite_in_chunks(file_path, content, target_version, api_key, model_name, output_log)
        except NoAvailableAIKeyError as exc:
            output_log.append(f"[Migration Engine] {exc}. Keeping {file_path.name} unchanged for this pass.")
            return content
        except Exception as exc:
            output_log.append(f"[Migration Engine] LLM skipped for {file_path.name}: {exc}")
            return content

    def _rewrite_in_chunks(self, file_path: Path, content: str, target_version: str, api_key: str, model_name: str, output_log: List[str]) -> str:
        lines = content.splitlines()
        if len(lines) < 80:
            return content

        chunk_count = 2 if len(lines) < 250 else 3
        chunk_size = max(1, len(lines) // chunk_count)
        updated_chunks = []
        for index in range(chunk_count):
            start = index * chunk_size
            end = len(lines) if index == chunk_count - 1 else (index + 1) * chunk_size
            chunk_text = "\n".join(lines[start:end])
            if not chunk_text.strip():
                continue
            prompt = (
                f"Rewrite this chunk of a Java {target_version} file only where needed.\n"
                f"Preserve existing logic and return raw text for this chunk only.\n\n"
                f"File: {file_path.name} chunk {index + 1} of {chunk_count}\n\n{chunk_text}"
            )
            system_instruction = "Return raw source text for the provided chunk only."
            try:
                rewritten = self._strip_markdown(self._generate_with_timeout(prompt, system_instruction, api_key, model_name, int(os.getenv("LLM_MIGRATION_REQUEST_TIMEOUT_SECONDS", "90")) // 2 or 30))
            except NoAvailableAIKeyError as exc:
                output_log.append(f"[Migration Engine] {exc}. Aborting remaining chunks for {file_path.name}.")
                return content
            except Exception:
                rewritten = chunk_text
            updated_chunks.append(rewritten)
        return "\n".join(updated_chunks) if updated_chunks else content

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore")

    def _write_text(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def _apply_build_updates(self, project_dir: Path, target_version: str, output_log: List[str], analysis_meta: dict) -> List[Path]:
        modified_files: List[Path] = []
        build_file = self._find_build_file(project_dir)
        if not build_file:
            return modified_files

        try:
            content = self._read_text(build_file)
        except Exception:
            return modified_files

        selection = java_compatibility_service.analyze_and_select(project_dir, target_version=target_version, build_tool=analysis_meta.get("buildTool", "Unknown"), output_log=output_log)
        changed_files = java_compatibility_service.align_build_configuration(project_dir, analysis_meta.get("buildTool", "Unknown"), selection, output_log)
        if changed_files:
            modified_files.extend(Path(path) for path in changed_files)

        try:
            content = self._read_text(build_file)
        except Exception:
            pass

        updated_content = self._remove_openrewrite_blocks(content)
        if updated_content != content:
            self._write_text(build_file, updated_content)
            if build_file not in modified_files:
                modified_files.append(build_file)
            output_log.append(f"[Migration Engine] Removed OpenRewrite configuration from {build_file.name}.")

        return modified_files

    def _scan_relevant_java_files(self, project_dir: Path) -> List[Path]:
        java_files = [path for path in safe_rglob(project_dir, "*.java") if not self._is_skipped(path)]
        max_workers = max(1, int(os.getenv("MIGRATION_SCAN_THREADS", "4")))
        relevant_files: List[Path] = []

        def is_relevant(path: Path) -> bool:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return False
            file_name = path.name.lower()
            if any(token in file_name for token in ("application", "config", "controller", "security", "entity", "repository", "service")):
                return True
            lower_content = content.lower()
            return any(marker.lower() in lower_content for marker in self.JAVA_HINTS)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(is_relevant, path): path for path in java_files}
            for future in as_completed(future_map):
                path = future_map[future]
                try:
                    if future.result():
                        relevant_files.append(path)
                except Exception:
                    continue

        return sorted(relevant_files)

    def _discover_migration_targets(self, project_dir: Path) -> List[Path]:
        targets: List[Path] = []
        for file_name in self.CONFIG_FILENAMES:
            for candidate in safe_rglob(project_dir, file_name):
                if self._is_skipped(candidate):
                    continue
                targets.append(candidate)
        targets.extend(self._scan_relevant_java_files(project_dir))

        unique_targets = []
        seen = set()
        for path in targets:
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            unique_targets.append(path)
        return unique_targets

    def _process_candidate_file(
        self,
        project_dir: Path,
        file_path: Path,
        target_version: str,
        api_key: str,
        model_name: str,
        output_log: List[str],
        resume_state: dict,
    ) -> dict:
        relative_path = str(file_path.relative_to(project_dir)).replace("\\", "/")
        fingerprint = self._fingerprint(file_path)
        processed_files = resume_state.setdefault("processed", {})
        if processed_files.get(relative_path, {}).get("fingerprint") == fingerprint:
            return {
                "file": file_path,
                "relative_path": relative_path,
                "changed": False,
                "mode": "resume-hit",
                "content": None,
            }

        try:
            original_content = self._read_text(file_path)
        except Exception as exc:
            return {
                "file": file_path,
                "relative_path": relative_path,
                "changed": False,
                "mode": "error",
                "error": str(exc),
                "content": None,
            }

        current_content = original_content
        mode = "deterministic"
        if file_path.name in {"pom.xml", "build.gradle", "build.gradle.kts"}:
            current_content = self._remove_openrewrite_blocks(current_content)
        elif file_path.suffix.lower() in {".properties", ".yml", ".yaml", ".xml"}:
            current_content, _ = self._fast_config_transform(current_content, target_version)
        elif file_path.suffix.lower() == ".java":
            current_content, _ = self._fast_java_transform(current_content, target_version)
            if self._needs_llm(current_content):
                mode = "llm"
                current_content = self._rewrite_with_llm(file_path, current_content, target_version, api_key, model_name, output_log)

        changed = current_content != original_content
        return {
            "file": file_path,
            "relative_path": relative_path,
            "changed": changed,
            "mode": mode,
            "content": current_content if changed else original_content,
        }

    def migrate_repository(self, project_dir: Path, target_version: str, api_key: str, model_name: str, output_log: List[str]) -> bool:
        self.clean_caches(project_dir, output_log)
        output_log.append(f"[Migration Engine] Starting optimized migration to Java {target_version}...")
        llm_runtime_service.update_job_progress(message="Repository Analysis .......... running")

        analysis_meta = self._load_cached_analysis(project_dir, output_log)
        project_type = analysis_meta.get("projectType", "Java")
        build_tool = analysis_meta.get("buildTool", "Unknown")
        output_log.append(f"[Migration Engine] Repository type: {project_type}, build tool: {build_tool}")
        llm_runtime_service.update_job_progress(message="Repository Analysis .......... ✓")

        resume_state = self._load_resume_state(project_dir)
        resume_state["targetVersion"] = target_version
        resume_state["updatedAt"] = time.time()

        llm_runtime_service.update_job_progress(message="Dependency Update .......... running")
        changed_files: List[Path] = []
        changed_files.extend(self._apply_build_updates(project_dir, target_version, output_log, analysis_meta))
        llm_runtime_service.update_job_progress(message="Dependency Update .......... ✓")

        candidate_files = self._discover_migration_targets(project_dir)
        candidate_files = [path for path in candidate_files if path not in changed_files]

        total_candidates = len(candidate_files)
        output_log.append(f"[Migration Engine] Selected {total_candidates} migration-relevant file(s) for processing.")
        llm_runtime_service.update_job_progress(message=f"Java Files (0/{total_candidates})", current_chunk=0, total_chunks=total_candidates)

        if total_candidates == 0 and not changed_files:
            output_log.append("[Migration Engine] No migration-relevant files found.")
            self._save_resume_state(project_dir, resume_state)
            return True

        started_at = time.monotonic()
        completed = 0
        max_workers = max(1, int(os.getenv("MIGRATION_FILE_CONCURRENCY", "2")))
        llm_timeout = int(os.getenv("LLM_MIGRATION_REQUEST_TIMEOUT_SECONDS", "90"))

        def eta_text() -> str:
            if completed == 0:
                return "calculating"
            elapsed = max(0.001, time.monotonic() - started_at)
            speed = completed / elapsed
            remaining = max(0, total_candidates - completed)
            eta = remaining / speed if speed > 0 else 0
            return f"{eta:.1f}s"

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    self._process_candidate_file,
                    project_dir,
                    file_path,
                    target_version,
                    api_key,
                    model_name,
                    output_log,
                    resume_state,
                ): file_path
                for file_path in candidate_files
            }

            for future in as_completed(future_map):
                file_path = future_map[future]
                completed += 1
                try:
                    result = future.result(timeout=llm_timeout)
                except TimeoutError:
                    output_log.append(f"[Migration Engine] Timeout while processing {file_path.name}; leaving the file unchanged for this pass.")
                    continue
                except Exception as exc:
                    output_log.append(f"[Migration Engine] Failed to process {file_path.name}: {exc}")
                    continue

                progress_pct = int((completed / total_candidates) * 100) if total_candidates else 100
                speed = completed / max(0.001, time.monotonic() - started_at)
                llm_runtime_service.update_job_progress(
                    current_chunk=completed,
                    total_chunks=total_candidates,
                    message=f"Java Files ({completed}/{total_candidates}) - {progress_pct}% - ETA {eta_text()} - {speed:.2f} file/s",
                )
                output_log.append(
                    f"[Migration Engine] {file_path.name} ({completed}/{total_candidates}) "
                    f"{progress_pct}% complete | speed={speed:.2f} file/s | ETA={eta_text()}"
                )

                if result.get("changed"):
                    try:
                        self._write_text(file_path, result["content"])
                        changed_files.append(file_path)
                        resume_state.setdefault("processed", {})[result["relative_path"]] = {
                            "fingerprint": self._fingerprint(file_path),
                            "mode": result.get("mode", "deterministic"),
                            "updatedAt": time.time(),
                        }
                        self._save_resume_state(project_dir, resume_state)
                        output_log.append(f"[Migration Engine] Saved migrated file: {result['relative_path']}")
                    except Exception as exc:
                        output_log.append(f"[Migration Engine] Failed to save {file_path.name}: {exc}")
                else:
                    resume_state.setdefault("processed", {})[result["relative_path"]] = {
                        "fingerprint": self._fingerprint(file_path),
                        "mode": result.get("mode", "skipped"),
                        "updatedAt": time.time(),
                    }
                    self._save_resume_state(project_dir, resume_state)

        if changed_files:
            output_log.append(f"[Migration Engine] Migrated {len(changed_files)} file(s) total.")
        else:
            output_log.append("[Migration Engine] No file changes were required after deterministic and AI-assisted passes.")

        llm_runtime_service.update_job_progress(message="Migration Completed Successfully", status="completed")
        return True


llm_migration_engine = LLMMigrationEngine()
