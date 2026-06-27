import os
import json
import subprocess
from pathlib import Path
from app.config import app_config
from app.ai.ai_factory import AIFactory
from app.services.java_runtime_service import java_runtime_service

class BuildValidationService:
    def validate_build(self, project_dir: Path, is_maven: bool, api_key: str, model_name: str, target_version: str = "") -> dict:
        is_windows = os.name == 'nt'
        fix_history = []
        max_attempts = 4  
        
        if is_maven:
            mvn_cmd = "mvn.cmd" if is_windows else "mvn"
            local_maven = app_config.project_root / "apache-maven-3.9.6" / "bin" / mvn_cmd
            if local_maven.exists():
                mvn_cmd = str(local_maven)
                
            wrapper = project_dir / ("mvnw.cmd" if is_windows else "mvnw")
            wrapper_jar = project_dir / ".mvn" / "wrapper" / "maven-wrapper.jar"
            
            if wrapper.exists() and wrapper_jar.exists():
                mvn_cmd = str(wrapper)
                
            base_command = [mvn_cmd, "clean", "package"]
        else:
            gradle_cmd = "gradle.bat" if is_windows else "gradle"
            wrapper = project_dir / ("gradlew.bat" if is_windows else "gradlew")
            if wrapper.exists():
                gradle_cmd = str(wrapper)
            base_command = [gradle_cmd, "clean", "build"]

        env, java_home = java_runtime_service.prepare_env()
        extra_args = []

        import time
        import socket
        import urllib.request
        import urllib.error

        def verify_artifact(directory: Path, is_maven: bool) -> bool:
            # Check for JAR or WAR file with size > 0
            target_dir = directory / "target" if is_maven else directory / "build" / "libs"
            if not target_dir.exists():
                return False
            for file_path in target_dir.rglob("*"):
                if file_path.is_file() and (file_path.suffix == ".jar" or file_path.suffix == ".war"):
                    if not file_path.name.endswith("-plain.jar") and not file_path.name.endswith("-sources.jar") and not file_path.name.endswith("-javadoc.jar"):
                        if file_path.stat().st_size > 0:
                            return True
            return False

        def get_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                return s.getsockname()[1]

        for attempt in range(max_attempts):
            command = base_command + extra_args
            output_log = []
            package_success = False
            
            try:
                output_log.append(f"--- Running Build Phase: {' '.join(command)} ---")
                process = subprocess.Popen(
                    command, cwd=str(project_dir), stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, errors='replace', env=env
                )
                for line in iter(process.stdout.readline, ''):
                    output_log.append(line.rstrip())
                process.wait()
                
                # Zero False Positives Policy: Actually verify the artifact
                has_artifact = verify_artifact(project_dir, is_maven)
                if process.returncode == 0 and has_artifact:
                    package_success = True
                    output_log.append("[Build Verification] Success: Artifact generated with size > 0.")
                elif process.returncode == 0 and not has_artifact:
                    package_success = False
                    output_log.append("[Build Verification] Failed: Compilation succeeded but no valid .jar or .war artifact found.")
                else:
                    package_success = False
            except Exception as e:
                output_log.append(f"Cannot run compiler/packager: {str(e)}")
                package_success = False
                
            full_log = "\n".join(output_log)
            
            runtime_success = False
            if package_success:
                # Proceed to Runtime Validation Phase
                runtime_log = []
                port = get_free_port()
                
                if is_maven:
                    runtime_command = [mvn_cmd, "spring-boot:run", f"-Dspring-boot.run.arguments=--server.port={port}"]
                else:
                    runtime_command = [gradle_cmd, "bootRun", f"--args=--server.port={port}"]
                
                try:
                    output_log.append(f"--- Running Runtime Phase: {' '.join(runtime_command)} ---")
                    run_process = subprocess.Popen(
                        runtime_command, cwd=str(project_dir), stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, errors='replace', env=env
                    )
                    
                    start_time = time.time()
                    server_started = False
                    
                    while True:
                        if time.time() - start_time > 45:
                            runtime_log.append("Runtime validation timed out after 45 seconds.")
                            break
                            
                        line = run_process.stdout.readline()
                        if line:
                            clean_line = line.rstrip()
                            runtime_log.append(clean_line)
                            output_log.append(clean_line)
                            
                            if "Started " in clean_line and " seconds" in clean_line:
                                server_started = True
                                break
                            if "Tomcat initialized with port(s)" in clean_line:
                                server_started = True
                                break
                            if "Application run failed" in clean_line or "BUILD FAILURE" in clean_line:
                                break
                        elif run_process.poll() is not None:
                            break
                            
                    # Zero False Positives Policy: Physically verify via HTTP
                    if server_started:
                        output_log.append(f"[Runtime Verification] Server process started. Attempting physical HTTP verification on port {port}...")
                        endpoints_to_try = [
                            f"http://127.0.0.1:{port}/actuator/health",
                            f"http://127.0.0.1:{port}/"
                        ]
                        
                        http_success = False
                        http_error_reason = ""
                        
                        for url in endpoints_to_try:
                            try:
                                req = urllib.request.Request(url)
                                with urllib.request.urlopen(req, timeout=5) as response:
                                    if response.getcode() == 200:
                                        http_success = True
                                        output_log.append(f"[Runtime Verification] Success: Received HTTP 200 from {url}")
                                        break
                            except urllib.error.HTTPError as e:
                                output_log.append(f"[Runtime Verification] HTTPError on {url}: {e.code} {e.reason}")
                                http_error_reason = f"HTTP {e.code}"
                                if e.code in [404, 500]:
                                    http_error_reason = "Whitelabel Error / Application Error"
                            except urllib.error.URLError as e:
                                output_log.append(f"[Runtime Verification] URLError on {url}: {e.reason}")
                                http_error_reason = f"Connection Failed"
                            except Exception as e:
                                output_log.append(f"[Runtime Verification] Exception on {url}: {str(e)}")
                                
                        if http_success:
                            runtime_success = True
                        else:
                            runtime_success = False
                            full_log = "\n".join(output_log)
                            output_log.append(f"[Runtime Verification] Failed: {http_error_reason}. Triggering AI root cause analysis.")
                            # Send this runtime failure for AI fix
                            full_log = "\n".join(output_log)
                            is_runtime_error = True
                            
                    run_process.terminate()
                    run_process.wait(timeout=5)
                except Exception as e:
                    output_log.append(f"Cannot run spring-boot:run: {str(e)}")
                    runtime_success = False
                    
            full_log = "\n".join(output_log)

            if package_success and runtime_success:
                return {"success": True, "status": "Build & Runtime Success", "buildLog": full_log, "suggestedFixes": None, "fixHistory": fix_history, "test_status": "Success", "runtime_status": "Success"}
            
            if attempt < max_attempts - 1:
                # 0. Deterministic JAXB check
                jaxb_keywords = [
                    "package javax.xml.bind.annotation does not exist",
                    "package jakarta.xml.bind.annotation does not exist",
                    "cannot find symbol XmlRootElement",
                    "javax.xml.bind does not exist",
                    "jakarta.xml.bind does not exist"
                ]
                if any(kw in full_log for kw in jaxb_keywords):
                    applied_fixes = self._apply_jaxb_fix(project_dir, is_maven, target_version)
                    if applied_fixes:
                        fix_history.append({
                            "attempt": attempt + 1,
                            "fixes": applied_fixes
                        })
                        continue

                # 1. Analyze failure with AI (handles both compilation and runtime/Whitelabel errors)
                analysis_json = self.analyze_build_failure(full_log, is_maven, api_key, model_name)
                analysis = self.parse_json_dict(analysis_json)
                is_compilation_error = analysis.get("is_compilation_error", True)
                
                if is_compilation_error:
                    # 2A. Genuine Java compilation error or Runtime Error -> Self-healing code rewrite
                    fixes_json_str = self.get_ai_recommendations(full_log, is_maven, api_key, model_name, project_dir)
                    applied_fixes = self.apply_fixes(fixes_json_str, project_dir)
                    if applied_fixes:
                        fix_history.append({
                            "attempt": attempt + 1,
                            "fixes": applied_fixes
                        })
                    else:
                        formatted_fixes = self.format_fixes_for_ui(fixes_json_str)
                        return {"success": False, "status": "Build Error", "buildLog": full_log, "suggestedFixes": formatted_fixes, "fixHistory": fix_history}
                else:
                    # 2B. Validation/Formatting Plugin Failure -> Try autofix or bypass
                    plugin_name = analysis.get("failing_plugin", "Unknown validation plugin")
                    autofix_goal = analysis.get("suggested_autofix_goal", "")
                    skip_prop = analysis.get("suggested_skip_property", "")
                    
                    resolved = False
                    if autofix_goal and is_maven:
                        autofix_cmd = [mvn_cmd, autofix_goal]
                        try:
                            af_process = subprocess.Popen(autofix_cmd, cwd=str(project_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', env=env)
                            af_process.wait()
                            if af_process.returncode == 0:
                                resolved = True
                                fix_history.append({
                                    "attempt": attempt + 1,
                                    "fixes": [{
                                        "file": f"Validation Plugin: {plugin_name}",
                                        "action": f"Executed auto-fix goal ({autofix_goal})",
                                        "search": "",
                                        "replace": ""
                                    }]
                                })
                        except Exception:
                            pass
                    
                    if not resolved and skip_prop:
                        if skip_prop not in extra_args:
                            extra_args.append(skip_prop)
                        fix_history.append({
                            "attempt": attempt + 1,
                            "fixes": [{
                                "file": f"Validation Plugin: {plugin_name}",
                                "action": f"Bypassed via {skip_prop}",
                                "search": "",
                                "replace": ""
                            }]
                        })
                    elif not resolved and not skip_prop:
                        formatted_fixes = f"Build failed due to plugin: {plugin_name}, but no skip property could be identified."
                        return {"success": False, "status": "Build Error", "buildLog": full_log, "suggestedFixes": formatted_fixes, "fixHistory": fix_history}
            else:
                return {"success": False, "status": "Build Error", "buildLog": full_log, "suggestedFixes": "Max self-healing attempts reached.", "fixHistory": fix_history}
                
        return {"success": False, "status": "Build Error", "buildLog": "Unknown error", "suggestedFixes": None, "fixHistory": fix_history}

    def get_ai_recommendations(self, build_log: str, is_maven: bool, api_key: str, model_name: str, project_dir: Path = None) -> str:
        # Extract the last 15000 characters to prevent token limits
        truncated_log = build_log[-15000:] if len(build_log) > 15000 else build_log
        
        build_file_content = ""
        if project_dir:
            build_file = project_dir / ("pom.xml" if is_maven else "build.gradle")
            if not build_file.exists() and not is_maven:
                build_file = project_dir / "build.gradle.kts"
            
            if build_file.exists():
                content = build_file.read_text(encoding='utf-8', errors='ignore')
                build_file_content = f"\n\nCurrent Build File ({build_file.name}):\n```\n{content}\n```\n"

        system_instruction = (
            "You are an expert Java developer. A project failed to compile after being upgraded by OpenRewrite. "
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
            return ai_client.generate(prompt, system_instruction, api_key, model_name)
        except Exception as e:
            return f"[]"

    def apply_fixes(self, fixes_json_str: str, project_dir: Path) -> list:
        applied = []
        try:
            fixes = self.parse_json_fixes(fixes_json_str)
            for fix in fixes:
                file_path = project_dir / fix.get("file", "")
                search_str = fix.get("search", "")
                replace_str = fix.get("replace", "")
                
                if file_path.exists():
                    if not search_str and replace_str:
                        # Full file replacement
                        file_path.write_text(replace_str, encoding='utf-8')
                        applied.append({
                            "file": fix.get("file"),
                            "action": "Rewrote entire file",
                            "search": "",
                            "replace": "<full_file_content_hidden>"
                        })
                        continue

                    if search_str:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        if search_str in content:
                            content = content.replace(search_str, replace_str)
                            file_path.write_text(content, encoding='utf-8')
                            applied.append({
                                "file": fix.get("file"),
                                "action": "Replaced code",
                                "search": search_str,
                                "replace": replace_str
                            })
                        else:
                            # Try robust whitespace-ignoring regex replacement
                            import re
                            tokens = search_str.split()
                            if tokens:
                                pattern_str = r'\s*'.join(re.escape(token) for token in tokens)
                                try:
                                    match = re.search(pattern_str, content)
                                    if match:
                                        content = content[:match.start()] + replace_str + content[match.end():]
                                        file_path.write_text(content, encoding='utf-8')
                                        applied.append({
                                            "file": fix.get("file"),
                                            "action": "Replaced code (regex fallback)",
                                            "search": search_str,
                                            "replace": replace_str
                                        })
                                        continue
                                except Exception:
                                    pass
                                    
                            # Fallback to stripping leading/trailing if regex fails
                            search_stripped = search_str.strip()
                            if search_stripped and search_stripped in content:
                                content = content.replace(search_stripped, replace_str.strip())
                                file_path.write_text(content, encoding='utf-8')
                                applied.append({
                                    "file": fix.get("file"),
                                    "action": "Replaced code (stripped whitespace)",
                                    "search": search_stripped,
                                    "replace": replace_str
                                })
        except Exception as e:
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
            return json_str  # Return raw if we can't parse it
        
        output = "The AI attempted to provide fixes, but they could not be automatically applied to the source code:\n\n"
        for i, fix in enumerate(fixes):
            output += f"Fix #{i+1} for file: {fix.get('file', 'Unknown')}\n"
            output += f"Replace:\n  {fix.get('search', '')}\nWith:\n  {fix.get('replace', '')}\n\n"
        return output

    def _apply_jaxb_fix(self, project_dir: Path, is_maven: bool, target_version: str) -> list:
        if not is_maven:
            return []
            
        pom_file = project_dir / "pom.xml"
        if not pom_file.exists():
            return []
            
        content = pom_file.read_text(encoding='utf-8', errors='ignore')
        applied = []
        
        # Determine dependency based on target version
        if target_version in ["17", "21", "25"]:
            group_id = "jakarta.xml.bind"
            artifact_id = "jakarta.xml.bind-api"
            version = "4.0.1"
        else:
            group_id = "javax.xml.bind"
            artifact_id = "jaxb-api"
            version = "2.3.1"
            
        # Prevent infinite loop if dependency is already there
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
            
        pom_file.write_text(content, encoding='utf-8')
        
        applied.append({
            "file": "pom.xml",
            "action": f"Injected missing JAXB dependency ({group_id}:{artifact_id}:{version})",
            "search": "",
            "replace": "<auto_injected>"
        })
        
        return applied

    def analyze_build_failure(self, build_log: str, is_maven: bool, api_key: str, model_name: str) -> str:
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
            "  \"failure_type\": \"<Brief description>\",\n"
            "  \"is_compilation_error\": <true/false>,\n"
            "  \"failing_plugin\": \"<groupId:artifactId> or empty\",\n"
            "  \"suggested_skip_property\": \"<-Dprop=true> or empty\",\n"
            "  \"suggested_autofix_goal\": \"<plugin:goal> or empty\"\n"
            "}"
        )
        
        prompt = f"Build Tool: {'Maven' if is_maven else 'Gradle'}\n\nCompiler Output Log:\n{truncated_log}\n\nProvide the JSON analysis."
        
        try:
            ai_client = AIFactory.get_client()
            return ai_client.generate(prompt, system_instruction, api_key, model_name)
        except Exception as e:
            return "{}"

    def parse_json_dict(self, json_str: str) -> dict:
        try:
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            result = json.loads(json_str)
            if isinstance(result, dict):
                return result
            elif isinstance(result, list) and len(result) > 0:
                return result[0]
            return {}
        except Exception:
            return {}

build_validation_service = BuildValidationService()
