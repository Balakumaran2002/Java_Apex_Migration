import os
import json
import subprocess
from pathlib import Path
from app.config import app_config
from app.ai.ai_factory import AIFactory

class BuildValidationService:
    def validate_build(self, project_dir: Path, is_maven: bool, api_key: str, model_name: str) -> dict:
        is_windows = os.name == 'nt'
        fix_history = []
        max_attempts = 3
        
        if is_maven:
            mvn_cmd = "mvn.cmd" if is_windows else "mvn"
            local_maven = app_config.project_root / "apache-maven-3.9.6" / "bin" / mvn_cmd
            if local_maven.exists():
                mvn_cmd = str(local_maven)
                
            wrapper = project_dir / ("mvnw.cmd" if is_windows else "mvnw")
            wrapper_jar = project_dir / ".mvn" / "wrapper" / "maven-wrapper.jar"
            
            if wrapper.exists() and wrapper_jar.exists():
                mvn_cmd = str(wrapper)
                
            command = [mvn_cmd, "clean", "compile", "-DskipTests=true"]
        else:
            gradle_cmd = "gradle.bat" if is_windows else "gradle"
            wrapper = project_dir / ("gradlew.bat" if is_windows else "gradlew")
            if wrapper.exists():
                gradle_cmd = str(wrapper)
            command = [gradle_cmd, "clean", "compileJava", "-x", "test"]

        env = os.environ.copy()
        if is_windows:
            java21 = Path("C:/Program Files/Java/jdk-21")
            if java21.exists():
                env["JAVA_HOME"] = str(java21)
                env["PATH"] = f"{java21}\\bin;{env.get('PATH', '')}"

        for attempt in range(max_attempts):
            output_log = []
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(project_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors='replace',
                    env=env
                )
                
                for line in iter(process.stdout.readline, ''):
                    output_log.append(line.rstrip())
                process.wait()
                success = (process.returncode == 0)
            except Exception as e:
                output_log.append(f"Cannot run compiler: {str(e)}")
                success = False

            full_log = "\n".join(output_log)
            
            if success:
                return {"success": True, "status": "Build Success", "buildLog": full_log, "suggestedFixes": None, "fixHistory": fix_history}

            if attempt < max_attempts - 1:
                fixes_json_str = self.get_ai_recommendations(full_log, is_maven, api_key, model_name, project_dir)
                applied_fixes = self.apply_fixes(fixes_json_str, project_dir)
                if applied_fixes:
                    fix_history.append({
                        "attempt": attempt + 1,
                        "fixes": applied_fixes
                    })
                else:
                    # Could not automatically apply fixes, maybe due to mismatch.
                    formatted_fixes = self.format_fixes_for_ui(fixes_json_str)
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
            "Each object must have 'file' (relative path from project root), 'search' (exact string to replace), and 'replace' (new string). "
            "Your 'search' string MUST exactly match the contents of the file provided, including whitespace. "
            "ONLY output the JSON array, no markdown or text. Example:\n"
            "[{\"file\": \"pom.xml\", \"search\": \"<java.version>1.8</java.version>\", \"replace\": \"<java.version>21</java.version>\"}]"
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
                
                if file_path.exists() and search_str:
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
                        # Try ignoring leading/trailing whitespaces
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

build_validation_service = BuildValidationService()
