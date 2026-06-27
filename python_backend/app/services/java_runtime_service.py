import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple


class JavaRuntimeService:
    def find_preferred_java_home(self, target_version: Optional[int] = None) -> Optional[Path]:
        candidates = []
        target = target_version if target_version else 21

        for env_name in (f"JAVA{target}_HOME", f"JDK{target}_HOME", "JAVA_HOME"):
            env_value = os.environ.get(env_name)
            if env_value:
                candidates.append(Path(env_value))

        if os.name == "nt":
            search_roots = [
                Path("C:/Program Files/Java"),
                Path("C:/Program Files/Eclipse Adoptium"),
                Path.home() / "AppData" / "Local" / "Programs" / "Eclipse Adoptium",
            ]

            for java_root in search_roots:
                candidates.extend([
                    java_root / f"jdk-{target}",
                    java_root / f"jdk-{target}.0.1",
                    java_root / f"jdk-{target}.0.2",
                    java_root / f"jdk-{target}.0.3",
                    java_root / f"jdk-{target}.0.4",
                    java_root / f"jdk-{target}.0.5",
                    java_root / f"jdk-{target}.0.6",
                    java_root / f"jdk-{target}.0.7",
                    java_root / f"jdk-{target}.0.8",
                    java_root / f"jdk-{target}.0.9",
                    java_root / f"jdk-{target}.0.10",
                    java_root / f"jdk-{target}.0.11",
                ])

                if java_root.exists():
                    candidates.extend(sorted(java_root.glob(f"jdk-{target}*"), reverse=True))

        for candidate in candidates:
            if self._is_valid_java_home(candidate):
                return candidate
        return None

    def prepare_env(self, env: Optional[dict] = None, target_version: Optional[int] = None) -> Tuple[dict, Optional[Path]]:
        prepared = dict(env or os.environ.copy())
        java_home = self.find_preferred_java_home(target_version)
        if not java_home:
            return prepared, None

        java_bin = java_home / "bin"
        prepared["JAVA_HOME"] = str(java_home)
        prepared["PATH"] = f"{java_bin}{os.pathsep}{prepared.get('PATH', '')}"
        prepared["ORG_GRADLE_JAVA_HOME"] = str(java_home)
        gradle_java_home_opt = f"-Dorg.gradle.java.home={java_home}"
        if os.name == "nt":
            for key in ("GRADLE_OPTS", "JAVA_OPTS", "_JAVA_OPTIONS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS"):
                value = prepared.get(key, "")
                if value and ("org.gradle.java.home=" in value or "Program Files\\Eclipse Adoptium" in value):
                    prepared.pop(key, None)
        else:
            gradle_opts = prepared.get("GRADLE_OPTS", "").strip()
            if gradle_java_home_opt not in gradle_opts:
                prepared["GRADLE_OPTS"] = f"{gradle_opts} {gradle_java_home_opt}".strip()

        gradle_user_home = Path(tempfile.gettempdir()) / f"apex-gradle-jdk{target_version or 21}"
        gradle_user_home.mkdir(parents=True, exist_ok=True)
        prepared["GRADLE_USER_HOME"] = str(gradle_user_home)

        return prepared, java_home

    def _is_valid_java_home(self, java_home: Path) -> bool:
        if not java_home or not java_home.exists():
            return False

        java_exe = java_home / "bin" / ("java.exe" if os.name == "nt" else "java")
        javac_exe = java_home / "bin" / ("javac.exe" if os.name == "nt" else "javac")
        return java_exe.exists() and javac_exe.exists()

    def get_installed_java_version(self, target_version: Optional[int] = None) -> int:
        env, java_home = self.prepare_env(target_version=target_version)
        java_cmd = "java"
        if java_home:
            java_cmd = str(java_home / "bin" / ("java.exe" if os.name == "nt" else "java"))
        
        try:
            import subprocess, re
            result = subprocess.run([java_cmd, "-version"], capture_output=True, text=True, env=env)
            output = result.stderr if result.stderr else result.stdout
            
            match = re.search(r'version "([^"]+)"', output)
            if match:
                version_str = match.group(1)
                if version_str.startswith("1."):
                    return int(version_str.split(".")[1])
                return int(version_str.split(".")[0])
        except Exception:
            pass
        return -1

    def get_maven_runtime_version(self, project_dir: Path) -> int:
        env, _ = self.prepare_env()
        is_windows = os.name == 'nt'
        mvn_cmd = "mvn.cmd" if is_windows else "mvn"
        
        from app.config import app_config
        local_maven = app_config.project_root / "apache-maven-3.9.6" / "bin" / mvn_cmd
        if local_maven.exists():
            mvn_cmd = str(local_maven)
            
        wrapper = project_dir / ("mvnw.cmd" if is_windows else "mvnw")
        wrapper_jar = project_dir / ".mvn" / "wrapper" / "maven-wrapper.jar"
        if wrapper.exists() and wrapper_jar.exists():
            mvn_cmd = str(wrapper)
            
        try:
            import subprocess, re
            result = subprocess.run([mvn_cmd, "-version"], cwd=str(project_dir), capture_output=True, text=True, env=env)
            output = result.stdout if result.stdout else result.stderr
            
            match = re.search(r'Java version: ([^\s,]+)', output)
            if match:
                version_str = match.group(1)
                if version_str.startswith("1."):
                    return int(version_str.split(".")[1])
                return int(version_str.split(".")[0])
        except Exception:
            pass
        return -1

java_runtime_service = JavaRuntimeService()
