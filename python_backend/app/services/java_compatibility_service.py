import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional


class JavaCompatibilityService:
    FEATURE_VERSION_HINTS = {
        r"\brecord\b": 16,
        r"\bsealed\b": 17,
        r"\bpermits\b": 17,
        r'"""': 15,
        r"switch\s*\(.*?\)\s*->": 14,
        r"\bnon-sealed\b": 17,
        r"\bvar\b": 10,
        r"\bStringTemplate\b": 21,
    }

    def normalize_version(self, raw_value: Optional[str]) -> Optional[int]:
        if raw_value is None:
            return None
        value = str(raw_value).strip()
        if not value:
            return None
        if value.startswith("${") and value.endswith("}"):
            return None
        if value.startswith("1."):
            value = value[2:]
        value = value.replace("VERSION_", "")
        match = re.search(r"(\d+)", value)
        if not match:
            return None
        return int(match.group(1))

    def analyze_and_select(
        self,
        project_dir: Path,
        target_version: Optional[str] = None,
        build_tool: str = "Unknown",
        output_log: Optional[List[str]] = None,
    ) -> Dict:
        log = output_log if output_log is not None else []
        requested_target = self.normalize_version(target_version)
        repo_analysis = self.detect_repository_requirements(project_dir, requested_target, build_tool)
        installed_jdks = self.detect_installed_jdks(project_dir)
        selection = self.select_compatible_jdk(installed_jdks, repo_analysis, requested_target)
        diagnostics = self.collect_command_diagnostics(project_dir, selection.get("java_home"))

        log.append(
            f"[Java Compatibility] Repository minimum Java: {repo_analysis['minimum_version']}, "
            f"preferred Java: {repo_analysis['preferred_version']}"
        )
        if repo_analysis["sources"]:
            log.append(
                "[Java Compatibility] Repository signals: "
                + "; ".join(
                    f"{item['source']}={item['value']}"
                    + (f" ({item['reason']})" if item.get("reason") else "")
                    for item in repo_analysis["sources"]
                )
            )

        if installed_jdks:
            installed_text = ", ".join(
                f"Java {jdk['version']} [{jdk['source']}] @ {jdk['java_home']}"
                for jdk in installed_jdks
            )
            log.append(f"[Java Compatibility] Installed JDKs: {installed_text}")
        else:
            log.append("[Java Compatibility] Installed JDKs: none detected")

        if diagnostics.get("java_version"):
            log.append(f"[Java Compatibility] java -version => {diagnostics['java_version']}")
        if diagnostics.get("javac_version"):
            log.append(f"[Java Compatibility] javac -version => {diagnostics['javac_version']}")
        if diagnostics.get("mvn_version"):
            log.append(f"[Java Compatibility] mvn -version => {diagnostics['mvn_version']}")

        selected_jdk = selection.get("selected_jdk")
        if selected_jdk:
            log.append(
                f"[Java Compatibility] Selected JDK: Java {selected_jdk['version']} @ "
                f"{selected_jdk['java_home']}"
            )
            log.append(
                f"[Java Compatibility] Compiler release: {selection['effective_release']} "
                f"(reason: {selection['reason']})"
            )
            log.append(
                f"[Java Compatibility] Compatibility validation: "
                f"selected JDK supports releases up to {selected_jdk['max_supported_release']}"
            )
        else:
            log.append(
                f"[Java Compatibility] Compatibility validation failed: {selection['reason']}"
            )

        selection["repo_analysis"] = repo_analysis
        selection["installed_jdks"] = installed_jdks
        selection["diagnostics"] = diagnostics
        return selection

    def detect_repository_requirements(
        self, project_dir: Path, requested_target: Optional[int], build_tool: str
    ) -> Dict:
        sources: List[Dict] = []
        versions: List[int] = []

        pom_file = project_dir / "pom.xml"
        gradle_file = project_dir / "build.gradle"
        gradle_kts_file = project_dir / "build.gradle.kts"

        if pom_file.exists():
            pom_content = pom_file.read_text(encoding="utf-8", errors="ignore")
            pom_props = self._extract_maven_versions(pom_content)
            sources.extend(pom_props)
            versions.extend(item["version"] for item in pom_props if item.get("version"))

            spring_boot = self._extract_spring_boot_version(pom_content)
            if spring_boot:
                boot_version = self._minimum_java_for_spring_boot(spring_boot)
                if boot_version:
                    sources.append(
                        {
                            "source": "spring-boot",
                            "value": spring_boot,
                            "version": boot_version,
                            "reason": f"Spring Boot {spring_boot} baseline",
                        }
                    )
                    versions.append(boot_version)



        gradle_file_to_use = gradle_file if gradle_file.exists() else gradle_kts_file
        if gradle_file_to_use and gradle_file_to_use.exists():
            gradle_content = gradle_file_to_use.read_text(encoding="utf-8", errors="ignore")
            gradle_versions = self._extract_gradle_versions(gradle_content)
            sources.extend(gradle_versions)
            versions.extend(item["version"] for item in gradle_versions if item.get("version"))

            spring_boot = self._extract_gradle_spring_boot_version(gradle_content)
            if spring_boot:
                boot_version = self._minimum_java_for_spring_boot(spring_boot)
                if boot_version:
                    sources.append(
                        {
                            "source": "spring-boot",
                            "value": spring_boot,
                            "version": boot_version,
                            "reason": f"Spring Boot {spring_boot} baseline",
                        }
                    )
                    versions.append(boot_version)



        for toolchains_file in self._candidate_toolchains_files(project_dir):
            if not toolchains_file.exists():
                continue
            try:
                content = toolchains_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            extracted = self._extract_toolchain_versions_from_xml(content, f"toolchains:{toolchains_file.name}")
            sources.extend(extracted)
            versions.extend(item["version"] for item in extracted if item.get("version"))

        feature_version = self._detect_java_feature_requirement(project_dir)
        if feature_version:
            sources.append(
                {
                    "source": "language-features",
                    "value": str(feature_version),
                    "version": feature_version,
                    "reason": "Detected Java language syntax requiring this baseline",
                }
            )
            versions.append(feature_version)

        minimum_version = max(versions) if versions else 8
        preferred_version = requested_target or minimum_version
        if preferred_version < minimum_version:
            preferred_version = minimum_version



        return {
            "minimum_version": minimum_version,
            "preferred_version": preferred_version,
            "requested_target": requested_target,
            "sources": sources,
            "build_tool": build_tool,
        }

    def detect_installed_jdks(self, project_dir: Path) -> List[Dict]:
        candidates: List[Dict] = []
        seen = set()

        def add_candidate(path_value: Optional[Path], source: str):
            if not path_value:
                return
            java_home = self._normalize_java_home(path_value)
            if not java_home:
                return
            key = str(java_home).lower()
            if key in seen:
                return
            seen.add(key)
            jdk_info = self._probe_jdk(java_home, source)
            if jdk_info:
                candidates.append(jdk_info)

        for env_name in (
            "JAVA_HOME",
            "JDK_HOME",
            "JAVA17_HOME",
            "JAVA21_HOME",
            "JAVA25_HOME",
            "JDK17_HOME",
            "JDK21_HOME",
            "JDK25_HOME",
        ):
            env_value = os.environ.get(env_name)
            if env_value:
                add_candidate(Path(env_value), f"env:{env_name}")

        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            if not path_dir:
                continue
            add_candidate(Path(path_dir), "path")

        sdkman_root = Path(os.environ.get("SDKMAN_CANDIDATES_DIR", Path.home() / ".sdkman" / "candidates"))
        for java_dir in (sdkman_root / "java", Path.home() / ".sdkman" / "candidates" / "java"):
            if java_dir.exists():
                for child in java_dir.iterdir():
                    add_candidate(child, "sdkman")

        if os.name == "nt":
            for root in (
                Path("C:/Program Files/Java"),
                Path("C:/Program Files/Eclipse Adoptium"),
                Path("C:/Program Files/Microsoft"),
                Path("C:/Program Files/Amazon Corretto"),
                Path("C:/Program Files/RedHat"),
                Path.home() / ".jdks",
                Path.home() / "scoop" / "apps",
            ):
                if root.exists():
                    for child in root.iterdir():
                        add_candidate(child, f"common-dir:{root}")
            for registry_home in self._detect_jdks_from_windows_registry():
                add_candidate(registry_home, "windows-registry")
        else:
            for root in (
                Path("/usr/lib/jvm"),
                Path("/Library/Java/JavaVirtualMachines"),
                Path.home() / ".jdks",
            ):
                if root.exists():
                    for child in root.iterdir():
                        add_candidate(child, f"common-dir:{root}")

        for toolchain_home in self._detect_toolchain_jdk_homes(project_dir):
            add_candidate(toolchain_home, "toolchain")

        for gradle_home in self._detect_gradle_installation_paths(project_dir):
            add_candidate(gradle_home, "gradle-toolchain")

        candidates.sort(key=lambda item: (item["version"], str(item["java_home"])), reverse=False)
        return candidates

    def select_compatible_jdk(
        self, installed_jdks: List[Dict], repo_analysis: Dict, requested_target: Optional[int]
    ) -> Dict:
        minimum_version = repo_analysis["minimum_version"]
        preferred_version = repo_analysis["preferred_version"]
        highest_installed = installed_jdks[-1] if installed_jdks else None

        compatible = [jdk for jdk in installed_jdks if jdk["max_supported_release"] >= minimum_version]
        preferred_compatible = [jdk for jdk in compatible if jdk["max_supported_release"] >= preferred_version]

        if preferred_compatible:
            selected = preferred_compatible[0]
            effective_release = preferred_version
            return {
                "success": True,
                "selected_jdk": selected,
                "java_home": selected["java_home"],
                "effective_release": effective_release,
                "requested_release": requested_target or preferred_version,
                "reason": f"Using the lowest installed JDK that satisfies preferred Java {preferred_version}",
                "retry_count": 0,
            }

        if compatible:
            selected = compatible[-1]
            effective_release = min(selected["max_supported_release"], selected["version"])
            return {
                "success": True,
                "selected_jdk": selected,
                "java_home": selected["java_home"],
                "effective_release": effective_release,
                "requested_release": requested_target or preferred_version,
                "reason": (
                    f"Java {preferred_version} is unavailable. Falling back to installed Java {selected['version']} "
                    f"because the repository minimum is Java {minimum_version}"
                ),
                "retry_count": 0,
                "downgraded": True,
            }

        if highest_installed:
            return {
                "success": False,
                "selected_jdk": None,
                "java_home": None,
                "effective_release": highest_installed["max_supported_release"],
                "requested_release": requested_target or preferred_version,
                "reason": (
                    f"Repository requires Java {minimum_version}, but the highest installed JDK is "
                    f"Java {highest_installed['version']}"
                ),
                "retry_count": 0,
            }

        return {
            "success": False,
            "selected_jdk": None,
            "java_home": None,
            "effective_release": None,
            "requested_release": requested_target or preferred_version,
            "reason": "No JDK installation was detected from environment variables, PATH, SDKMAN, registry, toolchains, or common directories",
            "retry_count": 0,
        }

    def prepare_env(self, selection: Dict, env: Optional[dict] = None) -> Dict:
        prepared = dict(env or os.environ.copy())
        java_home = selection.get("java_home")
        if not java_home:
            return prepared

        java_bin = Path(java_home) / "bin"
        prepared["JAVA_HOME"] = str(java_home)
        prepared["ORG_GRADLE_JAVA_HOME"] = str(java_home)
        prepared["PATH"] = f"{java_bin}{os.pathsep}{prepared.get('PATH', '')}"
        prepared["JDK_JAVA_OPTIONS"] = self._strip_java_home_overrides(prepared.get("JDK_JAVA_OPTIONS", ""))
        prepared["JAVA_TOOL_OPTIONS"] = self._strip_java_home_overrides(prepared.get("JAVA_TOOL_OPTIONS", ""))
        prepared["JAVA_OPTS"] = self._strip_java_home_overrides(prepared.get("JAVA_OPTS", ""))
        prepared["GRADLE_OPTS"] = self._strip_java_home_overrides(prepared.get("GRADLE_OPTS", ""))
        return prepared

    def collect_command_diagnostics(self, project_dir: Path, java_home: Optional[Path]) -> Dict[str, str]:
        env = os.environ.copy()
        if java_home:
            env["JAVA_HOME"] = str(java_home)
            env["PATH"] = f"{java_home / 'bin'}{os.pathsep}{env.get('PATH', '')}"

        mvn_cmd = self.resolve_maven_command(project_dir)
        return {
            "java_version": self._run_and_capture([self._java_executable(java_home), "-version"], env, project_dir),
            "javac_version": self._run_and_capture([self._javac_executable(java_home), "-version"], env, project_dir),
            "mvn_version": self._run_and_capture([mvn_cmd, "-version"], env, project_dir),
        }

    def resolve_maven_command(self, project_dir: Path) -> str:
        from app.config import app_config

        is_windows = os.name == "nt"
        mvn_cmd = "mvn.cmd" if is_windows else "mvn"
        local_maven = app_config.project_root / "apache-maven-3.9.6" / "bin" / mvn_cmd
        if local_maven.exists():
            mvn_cmd = str(local_maven)

        wrapper = project_dir / ("mvnw.cmd" if is_windows else "mvnw")
        wrapper_jar = project_dir / ".mvn" / "wrapper" / "maven-wrapper.jar"
        if wrapper.exists() and wrapper_jar.exists():
            mvn_cmd = str(wrapper)
        return mvn_cmd

    def resolve_gradle_command(self, project_dir: Path) -> str:
        is_windows = os.name == "nt"
        gradle_cmd = "gradle.bat" if is_windows else "gradle"
        wrapper = project_dir / ("gradlew.bat" if is_windows else "gradlew")
        if wrapper.exists():
            gradle_cmd = str(wrapper)
        return gradle_cmd

    def align_build_configuration(
        self, project_dir: Path, build_tool: str, selection: Dict, output_log: Optional[List[str]] = None
    ) -> List[str]:
        log = output_log if output_log is not None else []
        effective_release = selection.get("effective_release")
        selected_jdk = selection.get("selected_jdk")
        if not effective_release or not selected_jdk:
            return []

        modified_files: List[str] = []
        if build_tool == "Maven":
            pom_file = project_dir / "pom.xml"
            if pom_file.exists():
                updated = self._downgrade_maven_release_values(pom_file, effective_release)
                if updated:
                    modified_files.append(str(pom_file))
                    log.append(
                        f"[Java Compatibility] Updated pom.xml compiler settings to Java {effective_release} "
                        f"after validating selected JDK support"
                    )

        if build_tool in {"Gradle", "Gradle Kotlin DSL"}:
            build_file = project_dir / "build.gradle"
            if not build_file.exists():
                build_file = project_dir / "build.gradle.kts"
            if build_file.exists():
                updated = self._downgrade_gradle_release_values(build_file, effective_release)
                if updated:
                    modified_files.append(str(build_file))
                    log.append(
                        f"[Java Compatibility] Updated {build_file.name} toolchain/compiler settings to Java {effective_release}"
                    )
        return modified_files

    def _downgrade_maven_release_values(self, pom_file: Path, effective_release: int) -> bool:
        content = pom_file.read_text(encoding="utf-8", errors="ignore")
        updated = content

        def replace_if_needed(pattern: str, tag_name: str, text: str) -> str:
            def repl(match):
                existing = self.normalize_version(match.group(1))
                if existing and existing > effective_release:
                    return f"<{tag_name}>{text}</{tag_name}>"
                return match.group(0)

            return re.sub(pattern, repl, text, flags=re.IGNORECASE)

        updated = replace_if_needed(r"<java\.version>(.*?)</java\.version>", "java.version", updated)
        updated = replace_if_needed(r"<maven\.compiler\.release>(.*?)</maven\.compiler\.release>", "maven.compiler.release", updated)
        updated = replace_if_needed(r"<maven\.compiler\.source>(.*?)</maven\.compiler\.source>", "maven.compiler.source", updated)
        updated = replace_if_needed(r"<maven\.compiler\.target>(.*?)</maven\.compiler\.target>", "maven.compiler.target", updated)
        updated = replace_if_needed(r"<release>(.*?)</release>", "release", updated)
        updated = replace_if_needed(r"<source>(.*?)</source>", "source", updated)
        updated = replace_if_needed(r"<target>(.*?)</target>", "target", updated)

        if updated != content:
            pom_file.write_text(updated, encoding="utf-8")
            return True
        return False

    def _downgrade_gradle_release_values(self, build_file: Path, effective_release: int) -> bool:
        content = build_file.read_text(encoding="utf-8", errors="ignore")
        updated = content

        def replace_numeric(match):
            existing = self.normalize_version(match.group(2))
            if existing and existing > effective_release:
                return f"{match.group(1)}{effective_release}"
            return match.group(0)

        updated = re.sub(r"(JavaLanguageVersion\.of\()\s*(\d+)\s*(\))", lambda m: f"{m.group(1)}{effective_release}{m.group(3)}" if int(m.group(2)) > effective_release else m.group(0), updated)
        updated = re.sub(r"(options\.release\s*=\s*)(\d+)", replace_numeric, updated)
        updated = re.sub(r"(sourceCompatibility\s*=\s*JavaVersion\.VERSION_)(\d+)", replace_numeric, updated)
        updated = re.sub(r"(targetCompatibility\s*=\s*JavaVersion\.VERSION_)(\d+)", replace_numeric, updated)
        updated = re.sub(r"(sourceCompatibility\s*=\s*[\"']?)(\d+)([\"']?)", lambda m: f"{m.group(1)}{effective_release}{m.group(3)}" if int(m.group(2)) > effective_release else m.group(0), updated)
        updated = re.sub(r"(targetCompatibility\s*=\s*[\"']?)(\d+)([\"']?)", lambda m: f"{m.group(1)}{effective_release}{m.group(3)}" if int(m.group(2)) > effective_release else m.group(0), updated)

        if updated != content:
            build_file.write_text(updated, encoding="utf-8")
            return True
        return False

    def _extract_maven_versions(self, pom_content: str) -> List[Dict]:
        results = []
        patterns = {
            "java.version": r"<java\.version>(.*?)</java\.version>",
            "maven.compiler.release": r"<maven\.compiler\.release>(.*?)</maven\.compiler\.release>",
            "maven.compiler.source": r"<maven\.compiler\.source>(.*?)</maven\.compiler\.source>",
            "maven.compiler.target": r"<maven\.compiler\.target>(.*?)</maven\.compiler\.target>",
            "compiler-plugin-release": r"<artifactId>\s*maven-compiler-plugin\s*</artifactId>.*?<release>(.*?)</release>",
            "compiler-plugin-source": r"<artifactId>\s*maven-compiler-plugin\s*</artifactId>.*?<source>(.*?)</source>",
            "compiler-plugin-target": r"<artifactId>\s*maven-compiler-plugin\s*</artifactId>.*?<target>(.*?)</target>",
        }
        for source, pattern in patterns.items():
            match = re.search(pattern, pom_content, re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            value = match.group(1).strip()
            version = self.normalize_version(value)
            results.append({"source": source, "value": value, "version": version})
        return results

    def _extract_gradle_versions(self, gradle_content: str) -> List[Dict]:
        results = []
        patterns = {
            "sourceCompatibility": r"sourceCompatibility\s*=\s*(?:JavaVersion\.VERSION_)?[\"']?([0-9.]+)[\"']?",
            "targetCompatibility": r"targetCompatibility\s*=\s*(?:JavaVersion\.VERSION_)?[\"']?([0-9.]+)[\"']?",
            "toolchain-languageVersion": r"JavaLanguageVersion\.of\((\d+)\)",
            "options.release": r"options\.release\s*=\s*(\d+)",
        }
        for source, pattern in patterns.items():
            match = re.search(pattern, gradle_content, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip()
            version = self.normalize_version(value)
            results.append({"source": source, "value": value, "version": version})
        return results



    def _extract_spring_boot_version(self, pom_content: str) -> Optional[str]:
        patterns = [
            r"<parent>\s*<groupId>org\.springframework\.boot</groupId>\s*<artifactId>spring-boot-starter-parent</artifactId>\s*<version>(.*?)</version>",
            r"<spring-boot\.version>(.*?)</spring-boot\.version>",
        ]
        for pattern in patterns:
            match = re.search(pattern, pom_content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        return None

    def _extract_gradle_spring_boot_version(self, gradle_content: str) -> Optional[str]:
        match = re.search(r"org\.springframework\.boot['\"]\s*version\s*['\"]([^'\"]+)['\"]", gradle_content)
        if match:
            return match.group(1).strip()
        return None

    def _minimum_java_for_spring_boot(self, version: str) -> Optional[int]:
        parsed = self.normalize_version(version)
        if parsed is None:
            return None
        if parsed >= 3:
            return 17
        return 8

    def _extract_toolchain_versions_from_xml(self, xml_content: str, source_name: str) -> List[Dict]:
        results = []
        try:
            root = ET.fromstring(xml_content)
        except Exception:
            return results

        for toolchain in root.findall(".//toolchain"):
            toolchain_type = ""
            type_node = toolchain.find("./type")
            if type_node is not None and type_node.text:
                toolchain_type = type_node.text.strip().lower()
            if toolchain_type and toolchain_type != "jdk":
                continue

            for node in toolchain.findall(".//provides/version"):
                if not node.text:
                    continue
                value = node.text.strip()
                version = self.normalize_version(value)
                if version:
                    results.append(
                        {
                            "source": source_name,
                            "value": value,
                            "version": version,
                            "reason": "Toolchain JDK version",
                        }
                    )
        return results

    def _candidate_toolchains_files(self, project_dir: Path) -> List[Path]:
        files = [
            project_dir / ".mvn" / "toolchains.xml",
            project_dir / "toolchains.xml",
            Path.home() / ".m2" / "toolchains.xml",
        ]
        return files

    def _detect_java_feature_requirement(self, project_dir: Path) -> Optional[int]:
        highest = None
        scanned = 0
        for java_file in project_dir.rglob("*.java"):
            if any(part in {"target", "build", ".git", "node_modules"} for part in java_file.parts):
                continue
            try:
                content = java_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            scanned += 1
            for pattern, version in self.FEATURE_VERSION_HINTS.items():
                if re.search(pattern, content, re.MULTILINE | re.DOTALL):
                    highest = max(highest or version, version)
            if scanned >= 200:
                break
        return highest

    def _detect_toolchain_jdk_homes(self, project_dir: Path) -> List[Path]:
        homes: List[Path] = []
        for toolchains_file in self._candidate_toolchains_files(project_dir):
            if not toolchains_file.exists():
                continue
            try:
                root = ET.fromstring(toolchains_file.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for node in root.iter():
                if node.text and "jdkHome" in node.tag:
                    homes.append(Path(node.text.strip()))
        return homes

    def _detect_gradle_installation_paths(self, project_dir: Path) -> List[Path]:
        paths: List[Path] = []
        candidates = [
            project_dir / "gradle.properties",
            Path.home() / ".gradle" / "gradle.properties",
        ]
        for candidate in candidates:
            if not candidate.exists():
                continue
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            match = re.search(r"org\.gradle\.java\.installations\.paths\s*=\s*(.+)", content)
            if not match:
                continue
            for item in match.group(1).split(","):
                value = item.strip()
                if value:
                    paths.append(Path(value))
        return paths

    def _detect_jdks_from_windows_registry(self) -> List[Path]:
        homes: List[Path] = []
        for key in (
            r"HKLM\SOFTWARE\JavaSoft\JDK",
            r"HKLM\SOFTWARE\JavaSoft\Java Development Kit",
            r"HKLM\SOFTWARE\Eclipse Adoptium\JDK",
            r"HKLM\SOFTWARE\Microsoft\JDK",
        ):
            try:
                result = subprocess.run(
                    ["reg", "query", key, "/s"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            except Exception:
                continue
            output = result.stdout or ""
            for match in re.finditer(r"JavaHome\s+REG_SZ\s+([^\r\n]+)", output):
                homes.append(Path(match.group(1).strip()))
        return homes

    def _normalize_java_home(self, path_value: Path) -> Optional[Path]:
        path = Path(path_value)
        if not path.exists():
            return None
        if path.is_file():
            if path.name.lower() in {"java", "java.exe", "javac", "javac.exe"}:
                return path.parent.parent
            return None
        if (path / "bin" / ("java.exe" if os.name == "nt" else "java")).exists():
            return path
        if path.name == "bin" and (path / ("java.exe" if os.name == "nt" else "java")).exists():
            return path.parent
        for child in path.iterdir():
            if child.is_dir() and (child / "bin" / ("java.exe" if os.name == "nt" else "java")).exists():
                return child
        return None

    def _probe_jdk(self, java_home: Path, source: str) -> Optional[Dict]:
        java_output = self._run_and_capture([self._java_executable(java_home), "-version"], os.environ.copy(), java_home)
        javac_output = self._run_and_capture([self._javac_executable(java_home), "-version"], os.environ.copy(), java_home)
        combined = f"{java_output}\n{javac_output}"
        version = self._parse_java_version_text(combined)
        if version is None:
            return None

        supported_releases = self._detect_supported_releases(java_home)
        max_supported_release = max(supported_releases) if supported_releases else version
        return {
            "java_home": java_home,
            "version": version,
            "source": source,
            "supported_releases": supported_releases,
            "max_supported_release": max_supported_release,
            "java_version_output": java_output,
            "javac_version_output": javac_output,
        }

    def _detect_supported_releases(self, java_home: Path) -> List[int]:
        help_text = self._run_and_capture(
            [self._javac_executable(java_home), "--help"],
            os.environ.copy(),
            java_home,
            compact=False,
        )
        lines = help_text.splitlines()
        capture = False
        captured_tokens: List[str] = []

        for line in lines:
            if "Supported releases:" in line:
                capture = True
                after_label = line.split("Supported releases:", 1)[1]
                captured_tokens.extend(re.findall(r"\d+", after_label))
                continue
            if capture:
                stripped = line.strip()
                if not stripped or not re.match(r"^[0-9,\s]+$", stripped):
                    break
                captured_tokens.extend(re.findall(r"\d+", stripped))

        releases = sorted({int(token) for token in captured_tokens})
        if releases:
            return releases

        version = self._parse_java_version_text(help_text)
        return [version] if version else []

    def _parse_java_version_text(self, text: str) -> Optional[int]:
        patterns = [
            r'version "([^"]+)"',
            r"javac\s+([^\s]+)",
            r"openjdk\s+([^\s]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self.normalize_version(match.group(1))
        return None

    def _run_and_capture(self, command: List[str], env: dict, cwd: Path, compact: bool = True) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                env=env,
            )
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            if compact:
                return " ".join(output.split())
            return output
        except Exception as exc:
            return f"unavailable ({exc})"

    def _java_executable(self, java_home: Optional[Path]) -> str:
        if java_home:
            return str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java"))
        return "java"

    def _javac_executable(self, java_home: Optional[Path]) -> str:
        if java_home:
            return str(Path(java_home) / "bin" / ("javac.exe" if os.name == "nt" else "javac"))
        return "javac"

    def _strip_java_home_overrides(self, value: str) -> str:
        if not value:
            return ""
        cleaned = re.sub(r"-Dorg\.gradle\.java\.home=\S+", "", value)
        cleaned = re.sub(r"-Djava\.home=\S+", "", cleaned)
        return " ".join(cleaned.split())


java_compatibility_service = JavaCompatibilityService()
