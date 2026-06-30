import json
import os
import re
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from app.ai.ai_factory import AIFactory
from app.services.java_compatibility_service import java_compatibility_service
from app.services.java_runtime_service import java_runtime_service
from app.services.llm_runtime_service import llm_runtime_service

class BuildValidationService:
    def validate_build(
        self,
        project_dir: Path,
        is_maven: bool,
        api_key: str,
        model_name: str,
        target_version: str = "",
        project_type: str = "Java",
        build_tool: str = "Unknown",
    ) -> dict:
        fix_history = []
        max_attempts = 4
        llm_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        used_provider = None

        plan = None
        env = os.environ.copy()
        java_home = None
        base_command = []
        mvn_cmd = None
        gradle_cmd = None

        if project_type == "Java":
            plan = java_compatibility_service.analyze_and_select(
                project_dir,
                target_version=target_version,
                build_tool=build_tool,
            )
            if not plan.get("success"):
                return {
                    "success": False,
                    "status": "Java Compatibility Failed",
                    "buildLog": f"[Java Compatibility] {plan['reason']}",
                    "suggestedFixes": plan["reason"],
                    "fixHistory": fix_history,
                    "javaCompatibility": plan,
                    "llmUsage": llm_usage,
                    "usedProvider": used_provider,
                }

            env, java_home = java_runtime_service.prepare_env(project_dir=project_dir, selection=plan)
            java_compatibility_service.align_build_configuration(project_dir, build_tool, plan)

            if is_maven:
                mvn_cmd = java_compatibility_service.resolve_maven_command(project_dir)
                base_command = [mvn_cmd, "clean", "package"]
            else:
                gradle_cmd = java_compatibility_service.resolve_gradle_command(project_dir)
                base_command = [gradle_cmd, "clean", "build"]
        else:
            if build_tool == "npm":
                base_command = ["cmd", "/c", "npm", "install"] if os.name == "nt" else ["npm", "install"]
            elif build_tool == "yarn":
                base_command = ["cmd", "/c", "yarn", "install"] if os.name == "nt" else ["yarn", "install"]
            elif build_tool == "pnpm":
                base_command = ["cmd", "/c", "pnpm", "install"] if os.name == "nt" else ["pnpm", "install"]
            elif build_tool == "bun":
                base_command = ["cmd", "/c", "bun", "install"] if os.name == "nt" else ["bun", "install"]
            elif build_tool == "pip":
                base_command = ["pip", "install", "-r", "requirements.txt"]
            elif build_tool == "Poetry":
                base_command = ["poetry", "install"]
            elif build_tool == "dotnet":
                base_command = ["dotnet", "build"]
            elif build_tool == "cargo":
                base_command = ["cargo", "build"]
            else:
                base_command = ["echo", "No build tool detected"]

        extra_args = []

        def verify_artifact(directory: Path, use_maven: bool) -> Path:
            target_dir = directory / "target" if use_maven else directory / "build" / "libs"
            if not target_dir.exists():
                return None
            for file_path in target_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.suffix not in {".jar", ".war"}:
                    continue
                if file_path.name.endswith(("-plain.jar", "-sources.jar", "-javadoc.jar")):
                    continue
                if file_path.stat().st_size > 0:
                    return file_path
            return None

        def get_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("", 0))
                return sock.getsockname()[1]

        for attempt in range(max_attempts):
            command = base_command + extra_args
            output_log = []
            package_success = False
            artifact_path = None

            if plan:
                output_log.extend(self._java_plan_log_lines(plan, attempt))

            try:
                msg = f"Running Build Phase (Attempt {attempt + 1}/{max_attempts})... This may take a few minutes."
                llm_runtime_service.update_job_progress(message=msg, current_chunk=attempt, total_chunks=max_attempts)
                output_log.append(f"--- Running Build Phase: {' '.join(command)} ---")
                process = subprocess.Popen(
                    command,
                    cwd=str(project_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    env=env,
                )
                for line in iter(process.stdout.readline, ""):
                    output_log.append(line.rstrip())
                process.wait()

                if project_type == "Java":
                    artifact_path = verify_artifact(project_dir, is_maven)
                    if process.returncode == 0 and artifact_path:
                        package_success = True
                        output_log.append(f"[Build Verification] Success: Artifact generated at {artifact_path.name}")
                    elif process.returncode == 0:
                        output_log.append("[Build Verification] Failed: Compilation succeeded but no valid .jar or .war artifact found.")
                else:
                    if process.returncode == 0:
                        package_success = True
                        output_log.append(f"[Build Verification] Success: {build_tool} build/install completed.")
            except Exception as exc:
                output_log.append(f"Cannot run build/install command: {str(exc)}")

            full_log = "\n".join(output_log)

            runtime_success = False
            if package_success:
                port = get_free_port()
                env["PORT"] = str(port)

                if project_type == "Java":
                    java_bin = str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")) if java_home else "java"
                    if artifact_path and artifact_path.suffix == ".jar":
                        runtime_command = [java_bin, "-jar", str(artifact_path), f"--server.port={port}"]
                    else:
                        if is_maven:
                            runtime_command = [mvn_cmd, "spring-boot:run", f"-Dspring-boot.run.arguments=--server.port={port}"]
                        else:
                            runtime_command = [gradle_cmd, "bootRun", f"--args=--server.port={port}"]
                elif project_type == "Node.js (React/Angular)" or project_type == "Node.js":
                    runtime_command = ["npm", "start"]
                elif project_type == "Python":
                    runtime_command = ["python", "main.py"]
                    if not (project_dir / "main.py").exists() and (project_dir / "app.py").exists():
                        runtime_command = ["python", "app.py"]
                elif project_type == ".NET":
                    runtime_command = ["dotnet", "run"]
                elif project_type == "Rust":
                    runtime_command = ["cargo", "run"]
                else:
                    runtime_command = ["echo", "Unknown project type"]

                try:
                    msg = f"Running Runtime Verification (Attempt {attempt + 1}/{max_attempts})... Checking startup."
                    llm_runtime_service.update_job_progress(message=msg, current_chunk=attempt, total_chunks=max_attempts)
                    output_log.append(f"--- Running Runtime Phase: {' '.join(runtime_command)} ---")
                    run_process = subprocess.Popen(
                        runtime_command,
                        cwd=str(project_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        errors="replace",
                        env=env,
                    )

                    import threading
                    import time

                    runtime_log = []

                    def read_logs():
                        for log_line in iter(run_process.stdout.readline, ""):
                            clean = log_line.rstrip()
                            runtime_log.append(clean)
                            output_log.append(clean)

                    log_thread = threading.Thread(target=read_logs, daemon=True)
                    log_thread.start()

                    start_time = time.time()
                    server_started = False
                    output_log.append(f"[Runtime Verification] Polling 127.0.0.1:{port} for up to 45 seconds...")

                    while time.time() - start_time < 45:
                        if run_process.poll() is not None:
                            output_log.append(f"[Runtime Verification] Process exited early with code {run_process.returncode}")
                            break

                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                            sock.settimeout(0.5)
                            if sock.connect_ex(("127.0.0.1", port)) == 0:
                                server_started = True
                                break
                        time.sleep(0.5)

                    if not server_started and run_process.poll() is None:
                        output_log.append("[Runtime Verification] Timed out waiting for port to open.")

                    if server_started:
                        output_log.append(f"[Runtime Verification] Port bound! Attempting physical HTTP verification on port {port}...")
                        http_success = False
                        http_error_reason = ""
                        for url in (
                            f"http://127.0.0.1:{port}/actuator/health",
                            f"http://127.0.0.1:{port}/",
                        ):
                            try:
                                req = urllib.request.Request(url)
                                with urllib.request.urlopen(req, timeout=5) as response:
                                    if response.getcode() == 200:
                                        http_success = True
                                        output_log.append(f"[Runtime Verification] Success: Received HTTP 200 from {url}")
                                        break
                            except urllib.error.HTTPError as err:
                                output_log.append(f"[Runtime Verification] HTTPError on {url}: {err.code} {err.reason}")
                                http_error_reason = f"HTTP {err.code}"
                                if err.code in [401, 403, 404]:
                                    http_success = True
                                    output_log.append(f"[Runtime Verification] Success: Application is running (received {err.code})")
                                    break
                                if err.code == 500:
                                    http_error_reason = "Whitelabel Error / Application Error"
                            except urllib.error.URLError as err:
                                output_log.append(f"[Runtime Verification] URLError on {url}: {err.reason}")
                                http_error_reason = "Connection Failed"
                            except Exception as exc:
                                output_log.append(f"[Runtime Verification] Exception on {url}: {str(exc)}")

                        if http_success:
                            runtime_success = True
                        else:
                            output_log.append(f"[Runtime Verification] Failed: {http_error_reason}. Triggering AI root cause analysis.")

                    run_process.terminate()
                    run_process.wait(timeout=5)
                except Exception as exc:
                    output_log.append(f"Cannot run runtime phase: {str(exc)}")

            full_log = "\n".join(output_log)

            if package_success and runtime_success:
                return {
                    "success": True,
                    "status": "Build & Runtime Success",
                    "buildLog": full_log,
                    "suggestedFixes": None,
                    "fixHistory": fix_history,
                    "test_status": "Success",
                    "runtime_status": "Success",
                    "javaCompatibility": plan,
                    "llmUsage": llm_usage,
                    "usedProvider": used_provider,
                }

            if attempt < max_attempts - 1:
                if project_type != "Java":
                    return {
                        "success": False,
                        "status": "Build Error",
                        "errorMessage": full_log,
                        "buildLog": full_log,
                        "suggestedFixes": None,
                        "fixHistory": fix_history,
                        "llmUsage": llm_usage,
                        "usedProvider": used_provider,
                    }

                if self._apply_java_version_repair(full_log, project_dir, build_tool, plan, output_log):
                    plan["retry_count"] = attempt + 1
                    fix_history.append(
                        {
                            "attempt": attempt + 1,
                            "fixes": [
                                {
                                    "file": "build-configuration",
                                    "action": f"Aligned compiler release with selected Java {plan['effective_release']}",
                                    "search": "",
                                    "replace": "",
                                }
                            ],
                        }
                    )
                    env, java_home = java_runtime_service.prepare_env(project_dir=project_dir, selection=plan)
                    continue

                jaxb_keywords = [
                    "package javax.xml.bind.annotation does not exist",
                    "package jakarta.xml.bind.annotation does not exist",
                    "cannot find symbol XmlRootElement",
                    "javax.xml.bind does not exist",
                    "jakarta.xml.bind does not exist",
                ]
                if any(keyword in full_log for keyword in jaxb_keywords):
                    applied_fixes = self._apply_jaxb_fix(project_dir, is_maven, target_version)
                    if applied_fixes:
                        fix_history.append({"attempt": attempt + 1, "fixes": applied_fixes})
                        continue

                analysis_json, analysis_usage, analysis_provider = self.analyze_build_failure(full_log, is_maven, api_key, model_name)
                llm_usage = self._merge_usage(llm_usage, analysis_usage)
                used_provider = used_provider or analysis_provider
                analysis = self.parse_json_dict(analysis_json)
                is_compilation_error = analysis.get("is_compilation_error", True)

                if is_compilation_error:
                    llm_runtime_service.update_job_progress(message=f"AI generating fixes for build errors (Attempt {attempt + 1}/{max_attempts})...", current_chunk=attempt, total_chunks=max_attempts)
                    fixes_json_str, fixes_usage, fixes_provider = self.get_ai_recommendations(full_log, is_maven, api_key, model_name, project_dir)
                    llm_usage = self._merge_usage(llm_usage, fixes_usage)
                    used_provider = used_provider or fixes_provider
                    applied_fixes = self.apply_fixes(fixes_json_str, project_dir)
                    if applied_fixes:
                        fix_history.append({"attempt": attempt + 1, "fixes": applied_fixes})
                    else:
                        return {
                            "success": False,
                            "status": "Build Error",
                            "errorMessage": full_log,
                            "buildLog": full_log,
                            "suggestedFixes": self.format_fixes_for_ui(fixes_json_str),
                            "fixHistory": fix_history,
                            "javaCompatibility": plan,
                            "llmUsage": llm_usage,
                            "usedProvider": used_provider,
                        }
                else:
                    plugin_name = analysis.get("failing_plugin", "Unknown validation plugin")
                    autofix_goal = analysis.get("suggested_autofix_goal", "")
                    skip_prop = analysis.get("suggested_skip_property", "")
                    resolved = False

                    if autofix_goal and is_maven:
                        autofix_cmd = [mvn_cmd, autofix_goal]
                        try:
                            af_process = subprocess.Popen(
                                autofix_cmd,
                                cwd=str(project_dir),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True,
                                errors="replace",
                                env=env,
                            )
                            af_process.wait()
                            if af_process.returncode == 0:
                                resolved = True
                                fix_history.append(
                                    {
                                        "attempt": attempt + 1,
                                        "fixes": [
                                            {
                                                "file": f"Validation Plugin: {plugin_name}",
                                                "action": f"Executed auto-fix goal ({autofix_goal})",
                                                "search": "",
                                                "replace": "",
                                            }
                                        ],
                                    }
                                )
                        except Exception:
                            pass

                    if not resolved and skip_prop:
                        if skip_prop not in extra_args:
                            extra_args.append(skip_prop)
                        fix_history.append(
                            {
                                "attempt": attempt + 1,
                                "fixes": [
                                    {
                                        "file": f"Validation Plugin: {plugin_name}",
                                        "action": f"Bypassed via {skip_prop}",
                                        "search": "",
                                        "replace": "",
                                    }
                                ],
                            }
                        )
                    elif not resolved and not skip_prop:
                        return {
                            "success": False,
                            "status": "Build Error",
                            "buildLog": full_log,
                            "suggestedFixes": f"Build failed due to plugin: {plugin_name}, but no skip property could be identified.",
                            "fixHistory": fix_history,
                            "javaCompatibility": plan,
                            "llmUsage": llm_usage,
                            "usedProvider": used_provider,
                        }
            else:
                return {
                    "success": False,
                    "status": "Build Error",
                    "buildLog": full_log,
                    "suggestedFixes": "Max self-healing attempts reached.",
                    "fixHistory": fix_history,
                    "javaCompatibility": plan,
                    "llmUsage": llm_usage,
                    "usedProvider": used_provider,
                }

        return {
            "success": False,
            "status": "Build Error",
            "buildLog": "Unknown error",
            "suggestedFixes": None,
            "fixHistory": fix_history,
            "javaCompatibility": plan,
            "llmUsage": llm_usage,
            "usedProvider": used_provider,
        }

    def _java_plan_log_lines(self, plan: dict, attempt: int) -> list:
        selected = plan.get("selected_jdk") or {}
        diagnostics = plan.get("diagnostics", {})
        return [
            f"[Java Compatibility] Retry count: {attempt}",
            f"[Java Compatibility] Detected repository Java version: minimum {plan['repo_analysis']['minimum_version']}, preferred {plan['repo_analysis']['preferred_version']}",
            f"[Java Compatibility] Selected JDK: Java {selected.get('version', 'unknown')} @ {selected.get('java_home', 'unknown')}",
            f"[Java Compatibility] Compiler release: {plan.get('effective_release')}",
            f"[Java Compatibility] Reason for selection: {plan.get('reason')}",
            f"[Java Compatibility] Compatibility validation: java -version={diagnostics.get('java_version', 'n/a')}",
            f"[Java Compatibility] Compatibility validation: javac -version={diagnostics.get('javac_version', 'n/a')}",
            f"[Java Compatibility] Compatibility validation: mvn -version={diagnostics.get('mvn_version', 'n/a')}",
        ]

    def _apply_java_version_repair(self, full_log: str, project_dir: Path, build_tool: str, plan: dict, output_log: list) -> bool:
        version_error_markers = [
            "release version",
            "invalid target release",
            "error: source release",
            "is not supported",
            "unsupported class file major version",
        ]
        if not any(marker in full_log.lower() for marker in version_error_markers):
            return False

        changed = java_compatibility_service.align_build_configuration(project_dir, build_tool, plan, output_log)
        if changed:
            output_log.append(
                f"[Java Compatibility] Repaired compiler configuration after build failure. Retrying with Java {plan['effective_release']}."
            )
            return True
        return False

    def get_ai_recommendations(self, build_log: str, is_maven: bool, api_key: str, model_name: str, project_dir: Path = None) -> tuple[str, dict, str]:
        truncated_log = build_log[-15000:] if len(build_log) > 15000 else build_log
        build_file_content = ""

        if project_dir:
            build_file = project_dir / ("pom.xml" if is_maven else "build.gradle")
            if not build_file.exists() and not is_maven:
                build_file = project_dir / "build.gradle.kts"
            if build_file.exists():
                content = build_file.read_text(encoding="utf-8", errors="ignore")
                build_file_content = f"\n\nCurrent Build File ({build_file.name}):\n```\n{content}\n```\n"

        system_instruction = (
            "You are an expert Java developer. A project failed to compile after an automated migration. "
            "Analyze the build error log below. Identify the root cause. "
            "You MUST output a valid JSON array of objects representing the fixes. "
            "For Java source files (.java), each object must have 'file' (relative path from project root), 'search' (exact string to replace), and 'replace' (new string). Your 'search' string MUST exactly match the contents of the file provided, including whitespace. "
            "For build configuration files (pom.xml, build.gradle, etc.), you MUST rewrite the entire file to avoid formatting mismatch issues. For these files, set 'search' to an empty string \"\" and put the FULL updated file contents in 'replace'. "
            "ONLY output the JSON array, no markdown or text. Example:\n"
            "[{\"file\": \"pom.xml\", \"search\": \"\", \"replace\": \"<project>...full xml...</project>\"}]"
        )
        prompt = f"Build Tool: {'Maven' if is_maven else 'Gradle'}\n\nCompiler Output Log:\n{truncated_log}{build_file_content}\n\nProvide the JSON fixes."

        try:
            ai_client = AIFactory.get_client()
            response = ai_client.generate_with_metadata(prompt, system_instruction, api_key, model_name)
            usage = response.get("usage") or {}
            normalized = self._normalize_usage(usage, prompt, response.get("content", ""))
            return response.get("content", "[]"), normalized, getattr(ai_client, "last_provider_used", None)
        except Exception:
            return "[]", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, None

    def apply_fixes(self, fixes_json_str: str, project_dir: Path) -> list:
        applied = []
        try:
            fixes = self.parse_json_fixes(fixes_json_str)
            for fix in fixes:
                file_path = project_dir / fix.get("file", "")
                search_str = fix.get("search", "")
                replace_str = fix.get("replace", "")

                if not file_path.exists():
                    continue

                if not search_str and replace_str:
                    file_path.write_text(replace_str, encoding="utf-8")
                    applied.append(
                        {
                            "file": fix.get("file"),
                            "action": "Rewrote entire file",
                            "search": "",
                            "replace": "<full_file_content_hidden>",
                        }
                    )
                    continue

                if search_str:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if search_str in content:
                        content = content.replace(search_str, replace_str)
                        file_path.write_text(content, encoding="utf-8")
                        applied.append(
                            {
                                "file": fix.get("file"),
                                "action": "Replaced code",
                                "search": search_str,
                                "replace": replace_str,
                            }
                        )
                    else:
                        tokens = search_str.split()
                        if tokens:
                            pattern_str = r"\s*".join(re.escape(token) for token in tokens)
                            match = re.search(pattern_str, content)
                            if match:
                                content = content[: match.start()] + replace_str + content[match.end() :]
                                file_path.write_text(content, encoding="utf-8")
                                applied.append(
                                    {
                                        "file": fix.get("file"),
                                        "action": "Replaced code (regex fallback)",
                                        "search": search_str,
                                        "replace": replace_str,
                                    }
                                )
                                continue

                        search_stripped = search_str.strip()
                        if search_stripped and search_stripped in content:
                            content = content.replace(search_stripped, replace_str.strip())
                            file_path.write_text(content, encoding="utf-8")
                            applied.append(
                                {
                                    "file": fix.get("file"),
                                    "action": "Replaced code (stripped whitespace)",
                                    "search": search_stripped,
                                    "replace": replace_str,
                                }
                            )
        except Exception:
            pass
        return applied

    def parse_json_fixes(self, json_str: str) -> list:
        try:
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            return json.loads(json_str)
        except Exception:
            return []

    def format_fixes_for_ui(self, json_str: str) -> str:
        fixes = self.parse_json_fixes(json_str)
        if not fixes:
            return json_str

        output = "The AI attempted to provide fixes, but they could not be automatically applied to the source code:\n\n"
        for index, fix in enumerate(fixes):
            output += f"Fix #{index + 1} for file: {fix.get('file', 'Unknown')}\n"
            output += f"Replace:\n  {fix.get('search', '')}\nWith:\n  {fix.get('replace', '')}\n\n"
        return output

    def _apply_jaxb_fix(self, project_dir: Path, is_maven: bool, target_version: str) -> list:
        if not is_maven:
            return []

        pom_file = project_dir / "pom.xml"
        if not pom_file.exists():
            return []

        content = pom_file.read_text(encoding="utf-8", errors="ignore")
        applied = []

        if target_version in ["17", "21", "25"]:
            group_id = "jakarta.xml.bind"
            artifact_id = "jakarta.xml.bind-api"
            version = "4.0.1"
        else:
            group_id = "javax.xml.bind"
            artifact_id = "jaxb-api"
            version = "2.3.1"

        if f"<artifactId>{artifact_id}</artifactId>" in content:
            return []

        dependency_xml = f"""
        <dependency>
            <groupId>{group_id}</groupId>
            <artifactId>{artifact_id}</artifactId>
            <version>{version}</version>
        </dependency>"""

        if "<dependencies>" in content:
            content = content.replace("<dependencies>", f"<dependencies>{dependency_xml}", 1)
        else:
            content = content.replace("</project>", f"    <dependencies>{dependency_xml}\n    </dependencies>\n</project>")

        pom_file.write_text(content, encoding="utf-8")
        applied.append(
            {
                "file": "pom.xml",
                "action": f"Injected missing JAXB dependency ({group_id}:{artifact_id}:{version})",
                "search": "",
                "replace": "<auto_injected>",
            }
        )
        return applied

    def analyze_build_failure(self, build_log: str, is_maven: bool, api_key: str, model_name: str) -> tuple[str, dict, str]:
        truncated_log = build_log[-15000:] if len(build_log) > 15000 else build_log
        system_instruction = (
            "You are an expert Java developer debugging a build or runtime failure. "
            "Analyze the output and determine if this is a genuine Java error "
            "(compilation error, test failure, runtime exception, bean creation failure, etc.) OR a failure caused by a "
            "code-quality/formatting validation plugin (e.g., checkstyle, spotless). "
            "If it is a validation plugin failure, identify the plugin name and the suggested skip property. "
            "Do NOT suppress genuine Java errors (is_compilation_error must be true for compiler, test, or runtime errors). "
            "You MUST output ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "failure_type": "<Brief description>",\n'
            '  "is_compilation_error": <true/false>,\n'
            '  "failing_plugin": "<groupId:artifactId> or empty",\n'
            '  "suggested_skip_property": "<-Dprop=true> or empty",\n'
            '  "suggested_autofix_goal": "<plugin:goal> or empty"\n'
            "}"
        )
        prompt = f"Build Tool: {'Maven' if is_maven else 'Gradle'}\n\nCompiler Output Log:\n{truncated_log}\n\nProvide the JSON analysis."

        try:
            ai_client = AIFactory.get_client()
            response = ai_client.generate_with_metadata(prompt, system_instruction, api_key, model_name)
            usage = response.get("usage") or {}
            normalized = self._normalize_usage(usage, prompt, response.get("content", ""))
            return response.get("content", "{}"), normalized, getattr(ai_client, "last_provider_used", None)
        except Exception:
            return "{}", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, None

    def _normalize_usage(self, usage_obj, prompt: str, content: str) -> dict:
        def get_value(*names):
            for name in names:
                value = getattr(usage_obj, name, None) if not isinstance(usage_obj, dict) else usage_obj.get(name)
                if value is not None:
                    return int(value)
            return 0

        input_tokens = get_value("prompt_tokens", "input_tokens", "prompt_token_count")
        if not input_tokens:
            input_tokens = len(prompt) // 4
        output_tokens = get_value("completion_tokens", "output_tokens", "candidates_token_count")
        if not output_tokens:
            output_tokens = len(content) // 4
        total_tokens = get_value("total_tokens", "total_token_count")
        if not total_tokens:
            total_tokens = input_tokens + output_tokens
        return {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens}

    def _merge_usage(self, left: dict, right: dict) -> dict:
        return {
            "input_tokens": left.get("input_tokens", 0) + right.get("input_tokens", 0),
            "output_tokens": left.get("output_tokens", 0) + right.get("output_tokens", 0),
            "total_tokens": left.get("total_tokens", 0) + right.get("total_tokens", 0),
        }

    def parse_json_dict(self, json_str: str) -> dict:
        try:
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            result = json.loads(json_str)
            if isinstance(result, dict):
                return result
            if isinstance(result, list) and result:
                return result[0]
            return {}
        except Exception:
            return {}


build_validation_service = BuildValidationService()
