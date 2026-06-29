import os
import re
import shutil
from pathlib import Path
from git import Repo
from app.config import app_config
from app.models import AnalysisResponse
from app.ai.ai_factory import AIFactory
from app.services.rag_service import rag_service

class AnalysisService:
    SKIP_DIRS = {".git", "target", "build", "node_modules", ".idea", ".vscode", ".mvn", "__pycache__", "test", "tests"}
    CONFIG_EXTENSIONS = {".xml", ".gradle", ".kts", ".properties", ".yml", ".yaml"}
    MAX_CONTEXT_CHARS = 10000
    MAX_CONFIG_FILE_BYTES = 3000
    MAX_JAVA_SCAN_BYTES = 3000
    MAX_FILES_PER_CATEGORY = 40
    BATCH_SIZE = 12
    MAX_IMPORTS = 100
    MAX_JAVA_FILES = 200
    
    def analyze_repository(self, repo_url: str, api_key: str, model_name: str) -> AnalysisResponse:
        try:
            clone_dir = self.clone_repository(repo_url)
            commit_hash = "unknown"
            try:
                commit_hash = Repo(clone_dir).head.commit.hexsha
            except Exception:
                pass
                
            cache_file = app_config.workspace_directory / "analysis_cache.json"
            cache_key = f"{repo_url}_{commit_hash}_analyze"
            if cache_file.exists():
                try:
                    import json
                    cache = json.loads(cache_file.read_text())
                    if cache_key in cache:
                        return AnalysisResponse(**cache[cache_key])
                except Exception:
                    pass

            project_type = self.detect_project_type(clone_dir)
            is_java = project_type.lower() == "java"
            
            build_dir = clone_dir
            if is_java and not (build_dir / "pom.xml").exists() and not (build_dir / "build.gradle").exists() and not (build_dir / "build.gradle.kts").exists():
                sub_dir = self.find_build_file_directory(clone_dir)
                if sub_dir:
                    build_dir = sub_dir
            
            current_java_version = self.detect_java_version(build_dir)
            dependencies = []
            framework_versions = {}
            self.parse_dependencies_and_frameworks(build_dir, dependencies, framework_versions)

            # Comprehensive detection
            project_info = self.detect_comprehensive_project_info(build_dir, clone_dir)
            deprecated_apis = self.detect_deprecated_apis(build_dir)
            
            context_notes = []
            context_parts = []
            self.collect_project_context(build_dir, clone_dir, context_parts, context_notes)
            project_context = "".join(context_parts)
            
            # Rule-based migration recommendation
            if is_java:
                version_int = 8
                try:
                    version_int = int(current_java_version)
                except:
                    pass
                    
                if version_int >= 21:
                    recommendation = "This project is already using the latest Java version. No migration is required."
                elif version_int >= 17:
                    recommendation = "Migrate to Java 21"
                else:
                    recommendation = "Migrate to Java 17"
                
                risk_level = self._calculate_risk_level(version_int, deprecated_apis, project_info)
                query = f"Migrating Java project. Current version: {current_java_version}. Frameworks: {framework_versions}. Framework type: {project_info.get('framework_type')}."
                system_instruction = (
                    "You are an expert Java architect advising on migration paths. "
                    "Provide a concise explanation and code fix suggestions for the migration."
                    "Do not repeat the recommendation itself, just provide the detailed reasoning based on the files you read, and step-by-step guidance."
                )
            else:
                recommendation = f"Ensure {project_type} project builds, installs dependencies, and runs properly."
                risk_level = "Low"
                query = f"Analyzing {project_type} project. Build tool: {project_info.get('build_tool')}. Framework: {project_info.get('framework_type')}."
                system_instruction = (
                    f"You are an expert {project_type} architect advising on project setup, execution, and potential local environment fixes. "
                    "Provide a concise explanation of what is required to build and run this project, "
                    "identifying any missing environment variables or complex setup steps."
                )

            retrieved_docs = rag_service.search(query)
            
            rag_context = "Relevant Knowledge:\n"
            for doc in retrieved_docs:
                rag_context += f"- From {doc['source']}:\n{doc['content']}\n\n"

            processing_summary = ""
            if context_notes:
                processing_summary = "Repository Processing Summary:\n" + "\n".join(f"- {note}" for note in context_notes) + "\n\n"
            
            # Build a rich facts section so LLM generates grounded analysis
            detected_facts = (
                f"=== Detected Repository Facts ===\n"
                f"- Build Tool: {project_info.get('build_tool', 'Unknown')}\n"
                f"- Framework Type: {project_info.get('framework_type', 'Unknown')}\n"
                f"- Database: {project_info.get('database', 'None')}\n"
                f"- Packaging: {project_info.get('packaging_type', 'jar')}\n"
                f"- Multi-module: {project_info.get('is_multi_module', False)}\n"
                f"- Has Separate Frontend: {project_info.get('has_frontend', False)} ({project_info.get('frontend_framework', 'None')})\n"
                f"- REST Endpoints Detected: {project_info.get('endpoint_count', 0)}\n"
                f"- Risk Level: {risk_level}\n"
                f"- Deprecated APIs Found: {', '.join(deprecated_apis[:10]) if deprecated_apis else 'None'}\n"
                f"- Spring Boot Version: {framework_versions.get('Spring Boot', 'Not detected')}\n"
                f"- Current Java Version: {current_java_version}\n"
                f"- Planned Migration Target: {recommendation}\n"
            )

            user_prompt = (
                f"{rag_context}\n\n"
                f"{processing_summary}"
                f"{detected_facts}\n"
                f"Raw Project Files Context:\n{project_context}\n\n"
                "Based on the facts above (not generic advice), provide detailed migration reasoning and step-by-step guidance."
            )
            
            ai_client = AIFactory.get_client()
            ai_result = ai_client.generate(user_prompt, system_instruction, api_key, model_name)
                
            reasoning = ai_result
            if processing_summary:
                reasoning = processing_summary + ai_result

            response = AnalysisResponse(
                repoUrl=repo_url,
                projectType=project_type,
                isJava=is_java,
                detectedJavaVersion=current_java_version if is_java else None,
                buildTool=project_info.get("build_tool"),
                frameworkType=project_info.get("framework_type"),
                database=project_info.get("database"),
                packagingType=project_info.get("packaging_type"),
                isMultiModule=project_info.get("is_multi_module", False),
                hasFrontend=project_info.get("has_frontend", False),
                frontendFramework=project_info.get("frontend_framework"),
                endpointCount=project_info.get("endpoint_count", 0),
                riskLevel=risk_level,
                deprecatedApis=deprecated_apis,
                dependencies=dependencies,
                frameworkVersions=framework_versions,
                migrationRecommendation=recommendation,
                reasoning=reasoning,
                errorMessage=None,
                usedProvider=getattr(ai_client, "last_provider_used", None)
            )
            
            # Save to cache
            try:
                import json
                cache_data = {}
                if cache_file.exists():
                    cache_data = json.loads(cache_file.read_text())
                cache_data[cache_key] = response.model_dump()
                cache_file.write_text(json.dumps(cache_data))
            except Exception:
                pass
                
            return response
            
        except Exception as e:
            return AnalysisResponse(
                repoUrl=repo_url,
                projectType="Unknown",
                isJava=False,
                errorMessage=str(e)
            )

    def collect_project_context(self, build_dir: Path, clone_dir: Path, context_parts: list, notes: list):
        total_chars = 0

        def append_context(title: str, content: str):
            nonlocal total_chars
            if total_chars >= self.MAX_CONTEXT_CHARS:
                return False
            remaining = self.MAX_CONTEXT_CHARS - total_chars
            if len(content) > remaining:
                content = content[:remaining] + "\n...[TRUNCATED]"
            segment = f"\n\n--- {title} ---\n{content}"
            context_parts.append(segment)
            total_chars += len(segment)
            return total_chars < self.MAX_CONTEXT_CHARS

        def is_skipped(path: Path) -> bool:
            return any(part in self.SKIP_DIRS or part.startswith(".") for part in path.parts[:-1]) or any(skip in path.parts for skip in self.SKIP_DIRS)

        def is_binary(path: Path) -> bool:
            try:
                with open(path, "rb") as f:
                    sample = f.read(4096)
                return b"\x00" in sample
            except Exception:
                return True

        def read_text_limited(path: Path, limit: int) -> tuple[str, bool]:
            try:
                if path.stat().st_size > limit:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        chunks = []
                        remaining = limit
                        while remaining > 0:
                            piece = f.read(min(8192, remaining))
                            if not piece:
                                break
                            chunks.append(piece)
                            remaining -= len(piece)
                        content = "".join(chunks)
                        return content, True
                return path.read_text(encoding="utf-8", errors="ignore"), False
            except Exception:
                return "", False

        def iter_project_files():
            for root, dirs, files in os.walk(build_dir):
                dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS and not d.startswith(".")]
                for filename in files:
                    yield Path(root) / filename

        config_seen = 0
        config_processed = 0
        config_skipped_large = 0
        config_skipped_binary = 0

        batch = []
        stop_scanning = False
        for path in iter_project_files():
            if path.suffix.lower() not in self.CONFIG_EXTENSIONS:
                continue
            if config_seen >= self.MAX_FILES_PER_CATEGORY:
                config_skipped_large += 1
                continue
            config_seen += 1
            batch.append(path)
            if len(batch) >= self.BATCH_SIZE:
                processed, stop_scanning = self._process_context_batch(batch, clone_dir, append_context, notes, read_text_limited, is_binary)
                config_processed += processed
                batch = []
                if stop_scanning:
                    break
        if batch:
            processed, stop_scanning = self._process_context_batch(batch, clone_dir, append_context, notes, read_text_limited, is_binary)
            config_processed += processed

        if config_seen > 0:
            notes.append(f"Processed {config_processed} configuration files in batches of up to {self.BATCH_SIZE}.")
        if config_skipped_large > 0:
            notes.append(f"Skipped {config_skipped_large} additional configuration files after the safe limit of {self.MAX_FILES_PER_CATEGORY}.")
        if config_skipped_binary > 0:
            notes.append(f"Skipped {config_skipped_binary} binary or unreadable configuration files.")

        if stop_scanning:
            return

        java_imports = set()
        java_seen = 0
        java_skipped_large = 0
        java_skipped_binary = 0
        java_batch = []
        for path in iter_project_files():
            if path.suffix.lower() != ".java":
                continue
            if java_seen >= self.MAX_JAVA_FILES:
                java_skipped_large += 1
                continue
            java_seen += 1
            java_batch.append(path)
            if len(java_batch) >= self.BATCH_SIZE:
                if self._process_java_batch(java_batch, java_imports, notes, read_text_limited, is_binary):
                    break
                java_batch = []
        if java_batch:
            self._process_java_batch(java_batch, java_imports, notes, read_text_limited, is_binary)

        if java_seen > 0:
            notes.append(f"Scanned {min(java_seen, self.MAX_JAVA_FILES)} Java files for import usage in batches of up to {self.BATCH_SIZE}.")
        if java_skipped_large > 0:
            notes.append(f"Skipped {java_skipped_large} additional Java files after the safe limit of {self.MAX_JAVA_FILES}.")
        if java_imports:
            imports_block = "\n".join(sorted(list(java_imports))[: self.MAX_IMPORTS])
            append_context("Unique Java Imports Across Project", imports_block)
            if len(java_imports) > self.MAX_IMPORTS:
                notes.append(f"Trimmed Java imports to the first {self.MAX_IMPORTS} unique entries to stay within prompt limits.")

    def _process_context_batch(self, batch: list, clone_dir: Path, append_context, notes: list, read_text_limited, is_binary) -> tuple[int, bool]:
        processed = 0
        for file_path in batch:
            if is_binary(file_path):
                notes.append(f"Skipped binary file: {file_path.relative_to(clone_dir)}")
                continue
            content, was_truncated = read_text_limited(file_path, self.MAX_CONFIG_FILE_BYTES)
            if not content:
                notes.append(f"Skipped unreadable file: {file_path.relative_to(clone_dir)}")
                continue
            title = f"File: {file_path.relative_to(clone_dir)}"
            if was_truncated:
                notes.append(f"Truncated large file: {file_path.relative_to(clone_dir)}")
            if not append_context(title, content):
                notes.append("Stopped adding file context because the safe prompt size limit was reached.")
                return processed + 1, True
            processed += 1
        return processed, False

    def _process_java_batch(self, batch: list, java_imports: set, notes: list, read_text_limited, is_binary) -> bool:
        for file_path in batch:
            if is_binary(file_path):
                notes.append(f"Skipped binary Java file: {file_path.name}")
                continue
            content, _ = read_text_limited(file_path, self.MAX_JAVA_SCAN_BYTES)
            if not content:
                notes.append(f"Skipped unreadable Java file: {file_path.name}")
                continue
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("import "):
                    java_imports.add(stripped)
                if len(java_imports) >= self.MAX_IMPORTS:
                    return True
        return False

    def clone_repository(self, repo_url: str) -> Path:
        repo_name = repo_url.split('/')[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
            
        clone_dir = app_config.workspace_directory / repo_name
        
        if clone_dir.exists():
            try:
                repo = Repo(clone_dir)
                repo.git.reset('--hard')
                repo.git.clean('-fd')
                repo.remotes.origin.pull()
                return clone_dir
            except Exception:
                shutil.rmtree(clone_dir, ignore_errors=True)
                if clone_dir.exists():
                    import subprocess
                    subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(clone_dir)], shell=True)
                
        if not clone_dir.exists() or not list(clone_dir.iterdir()):
            Repo.clone_from(repo_url, clone_dir, depth=1)
        return clone_dir

    def detect_project_type(self, repo_dir: Path) -> str:
        ext_counts = {}
        self.count_file_extensions(repo_dir, ext_counts)
        
        if (repo_dir / "pom.xml").exists() or (repo_dir / "build.gradle").exists() or ext_counts.get("java", 0) > 0:
            return "Java"
        if (repo_dir / "package.json").exists():
            return "Node.js"
        if (repo_dir / "requirements.txt").exists() or (repo_dir / "pyproject.toml").exists() or ext_counts.get("py", 0) > 0:
            return "Python"
        if list(repo_dir.glob("*.csproj")) or list(repo_dir.glob("*.sln")):
            return ".NET"
        if (repo_dir / "Cargo.toml").exists():
            return "Rust"
        if ext_counts.get("ts", 0) > 0 or ext_counts.get("tsx", 0) > 0:
            return "TypeScript"
        if ext_counts.get("js", 0) > 0 or ext_counts.get("jsx", 0) > 0:
            return "JavaScript"
        if ext_counts.get("c", 0) > 0 or ext_counts.get("cpp", 0) > 0 or ext_counts.get("h", 0) > 0:
            return "C/C++"
        return "Unknown"

    def count_file_extensions(self, directory: Path, ext_counts: dict):
        try:
            for path in directory.iterdir():
                try:
                    if path.is_dir():
                        if not path.name.startswith("."):
                            self.count_file_extensions(path, ext_counts)
                    else:
                        ext = path.suffix.lower()[1:]
                        if ext:
                            ext_counts[ext] = ext_counts.get(ext, 0) + 1
                except OSError:
                    # Ignore path length issues (WinError 3) or access denied on specific files
                    continue
        except OSError:
            # Ignore path length issues when iterating directory
            pass

    def detect_java_version(self, repo_dir: Path) -> str:
        pom = repo_dir / "pom.xml"
        if pom.exists():
            content = pom.read_text(encoding='utf-8', errors='ignore')
            patterns = [
                r"<java\.version>(.*?)</java\.version>",
                r"<maven\.compiler\.source>(.*?)</maven\.compiler\.source>",
                r"<maven\.compiler\.target>(.*?)</maven\.compiler\.target>",
                r"<maven\.compiler\.release>(.*?)</maven\.compiler\.release>"
            ]
            for p in patterns:
                match = re.search(p, content)
                if match:
                    return self.normalize_java_version(match.group(1).strip())

        gradle = repo_dir / "build.gradle"
        if not gradle.exists():
            gradle = repo_dir / "build.gradle.kts"
            
        if gradle.exists():
            content = gradle.read_text(encoding='utf-8', errors='ignore')
            patterns = [
                r"sourceCompatibility\s*=\s*['\"]?(1\.[0-8]|[0-9]+)['\"]?",
                r"targetCompatibility\s*=\s*['\"]?(1\.[0-8]|[0-9]+)['\"]?",
                r"languageVersion\s*=\s*JavaLanguageVersion\.of\((.*?)\)"
            ]
            for p in patterns:
                match = re.search(p, content)
                if match:
                    return self.normalize_java_version(match.group(1).strip())
                    
        return "8"

    def normalize_java_version(self, version: str) -> str:
        if version.startswith("1."):
            return version[2:]
        return version

    def parse_dependencies_and_frameworks(self, repo_dir: Path, dependencies: list, framework_versions: dict):
        pom = repo_dir / "pom.xml"
        if pom.exists():
            content = pom.read_text(encoding='utf-8', errors='ignore')
            sb_match = re.search(r"<parent>\s*<groupId>org\.springframework\.boot</groupId>\s*<artifactId>spring-boot-starter-parent</artifactId>\s*<version>(.*?)</version>", content)
            if sb_match:
                framework_versions["Spring Boot"] = sb_match.group(1).strip()
                
            dep_matches = re.finditer(r"<artifactId>(spring-boot-starter-.*?|hibernate-.*?|jackson-.*?|lombok)</artifactId>", content)
            dep_set = {m.group(1) for m in dep_matches}
            dependencies.extend(list(dep_set))

        gradle = repo_dir / "build.gradle"
        if not gradle.exists():
            gradle = repo_dir / "build.gradle.kts"
            
        if gradle.exists():
            content = gradle.read_text(encoding='utf-8', errors='ignore')
            sb_match = re.search(r"id\s*['\"]org\.springframework\.boot['\"]\s*version\s*['\"](.*?)['\"]", content)
            if sb_match:
                framework_versions["Spring Boot"] = sb_match.group(1).strip()
                
            dep_matches = re.finditer(r"['\"]org\.springframework\.boot:(spring-boot-starter-.*?):.*?['\"]", content)
            dep_set = {m.group(1) for m in dep_matches}
            dependencies.extend(list(dep_set))

    def detect_comprehensive_project_info(self, build_dir: Path, clone_dir: Path) -> dict:
        """Detect build tool, framework type, database, packaging, multi-module, frontend, endpoint count."""
        info = {
            "build_tool": "Unknown",
            "framework_type": "Plain Java",
            "database": "None",
            "packaging_type": "jar",
            "is_multi_module": False,
            "has_frontend": False,
            "frontend_framework": None,
            "endpoint_count": 0,
        }

        # Build tool & Package Manager
        if (build_dir / "pom.xml").exists():
            info["build_tool"] = "Maven"
        elif (build_dir / "build.gradle.kts").exists():
            info["build_tool"] = "Gradle Kotlin DSL"
        elif (build_dir / "build.gradle").exists():
            info["build_tool"] = "Gradle"
        elif (build_dir / "package.json").exists():
            if (build_dir / "pnpm-lock.yaml").exists():
                info["build_tool"] = "pnpm"
            elif (build_dir / "yarn.lock").exists():
                info["build_tool"] = "yarn"
            elif (build_dir / "bun.lockb").exists():
                info["build_tool"] = "bun"
            else:
                info["build_tool"] = "npm"
            info["framework_type"] = "Node.js"
        elif (build_dir / "pyproject.toml").exists():
            content = (build_dir / "pyproject.toml").read_text(errors='ignore')
            if "poetry" in content:
                info["build_tool"] = "Poetry"
            elif "uv" in content:
                info["build_tool"] = "uv"
            else:
                info["build_tool"] = "pip (pyproject.toml)"
            info["framework_type"] = "Python"
        elif (build_dir / "requirements.txt").exists():
            info["build_tool"] = "pip"
            info["framework_type"] = "Python"
        elif list(build_dir.glob("*.csproj")):
            info["build_tool"] = "dotnet"
            info["framework_type"] = ".NET"
        elif (build_dir / "Cargo.toml").exists():
            info["build_tool"] = "cargo"
            info["framework_type"] = "Rust"

        # Read build file for detailed detection
        build_content = ""
        for bf in [build_dir / "pom.xml", build_dir / "build.gradle", build_dir / "build.gradle.kts"]:
            if bf.exists():
                try:
                    build_content = bf.read_text(encoding="utf-8", errors="ignore").lower()
                except Exception:
                    pass
                break

        if build_content:
            # Framework type
            if "spring-boot" in build_content:
                if "thymeleaf" in build_content:
                    info["framework_type"] = "Spring Boot / Thymeleaf"
                elif "jsp" in build_content or "jstl" in build_content or "tomcat-embed-jasper" in build_content:
                    info["framework_type"] = "Spring Boot / JSP"
                elif "spring-boot-starter-web" in build_content or "spring-webmvc" in build_content:
                    info["framework_type"] = "Spring Boot / Web MVC"
                elif "spring-boot-starter-webflux" in build_content:
                    info["framework_type"] = "Spring Boot / WebFlux (Reactive)"
                elif "spring-boot-starter-data" in build_content:
                    info["framework_type"] = "Spring Boot / Data Only"
                else:
                    info["framework_type"] = "Spring Boot"
            elif "spring-webmvc" in build_content or "spring-web" in build_content:
                info["framework_type"] = "Spring MVC (Non-Boot)"
            elif "javax.servlet" in build_content or "jakarta.servlet" in build_content or "servlet-api" in build_content:
                info["framework_type"] = "JSP/Servlet"
            elif "javafx" in build_content:
                info["framework_type"] = "JavaFX"

            # Database detection
            if "mysql-connector" in build_content or "com.mysql" in build_content:
                info["database"] = "MySQL"
            elif "postgresql" in build_content or "org.postgresql" in build_content:
                info["database"] = "PostgreSQL"
            elif "mssql" in build_content or "sqlserver" in build_content:
                info["database"] = "SQL Server"
            elif "oracle" in build_content and "jdbc" in build_content:
                info["database"] = "Oracle"
            elif "mongodb" in build_content or "spring-data-mongodb" in build_content:
                info["database"] = "MongoDB"
            elif "com.h2database" in build_content or "h2" in build_content:
                info["database"] = "H2 (Embedded)"

            # Packaging type
            if "<packaging>war</packaging>" in build_content or "apply plugin: 'war'" in build_content or 'id "war"' in build_content:
                info["packaging_type"] = "war"

            # Multi-module detection (Maven parent pom with <modules>)
            if "<modules>" in build_content or "subprojects" in build_content or "include(" in build_content:
                info["is_multi_module"] = True

        # Frontend detection from the broader clone directory
        for package_json in clone_dir.rglob("package.json"):
            if any(skip in package_json.parts for skip in ("node_modules", "target", "build", ".git")):
                continue
            try:
                import json
                pkg = json.loads(package_json.read_text(encoding="utf-8", errors="ignore"))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if any(k.startswith("@angular") for k in deps):
                    info["has_frontend"] = True
                    info["frontend_framework"] = "Angular"
                elif "react" in deps or "react-dom" in deps:
                    info["has_frontend"] = True
                    info["frontend_framework"] = "React"
                elif "vue" in deps:
                    info["has_frontend"] = True
                    info["frontend_framework"] = "Vue"
                else:
                    info["has_frontend"] = True
                    info["frontend_framework"] = "Node.js"
                break
            except Exception:
                pass

        # Frontend via template directories (Thymeleaf/JSP)
        if not info["has_frontend"]:
            for pattern in ("src/main/resources/templates", "src/main/webapp", "src/main/resources/static"):
                if (build_dir / pattern).exists():
                    info["has_frontend"] = True
                    if "Thymeleaf" in info["framework_type"]:
                        info["frontend_framework"] = "Thymeleaf"
                    elif "JSP" in info["framework_type"]:
                        info["frontend_framework"] = "JSP"
                    else:
                        info["frontend_framework"] = "Static HTML"
                    break

        # Endpoint count from Java/Python/TS source
        endpoint_count = 0
        mapping_pattern = re.compile(
            r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping|app\.get|app\.post|router\.get|router\.post|@app\.get|@app\.post|@router\.get)',
            re.IGNORECASE
        )
        for src_file in build_dir.rglob("*.*"):
            if src_file.suffix not in {".java", ".py", ".ts", ".js"}:
                continue
            if any(p in src_file.parts for p in ("target", "build", ".git", "node_modules", "venv", "__pycache__")):
                continue
            try:
                content = src_file.read_text(encoding="utf-8", errors="ignore")
                endpoint_count += len(mapping_pattern.findall(content))
            except Exception:
                pass
        info["endpoint_count"] = endpoint_count

        return info

    def detect_deprecated_apis(self, build_dir: Path) -> list:
        """Scan Java source for known deprecated/removed APIs in newer Java versions."""
        deprecated_patterns = [
            ("javax.xml.bind", "javax.xml.bind (JAXB removed in Java 11, needs jakarta.xml.bind)"),
            ("javax.activation", "javax.activation (removed in Java 11)"),
            ("javax.annotation", "javax.annotation (moved to jakarta.annotation)"),
            ("com.sun.misc.Unsafe", "sun.misc.Unsafe (strongly restricted in Java 17+)"),
            ("sun.reflect", "sun.reflect (removed in Java 17)"),
            ("java.security.acl", "java.security.acl (removed in Java 17)"),
            ("javax.security.auth.Policy", "javax.security.auth.Policy (removed)"),
            ("Thread.stop()", "Thread.stop() (deprecated for removal)"),
            ("Thread.suspend()", "Thread.suspend() (deprecated for removal)"),
            ("Thread.resume()", "Thread.resume() (deprecated for removal)"),
            ("System.runFinalizersOnExit", "System.runFinalizersOnExit (removed)"),
            ("Runtime.runFinalizersOnExit", "Runtime.runFinalizersOnExit (removed)"),
            ("java.util.Date.toLocaleString", "Date.toLocaleString() (deprecated)"),
            ("new Integer(", "new Integer() constructor (deprecated, use Integer.valueOf())"),
            ("new Long(", "new Long() constructor (deprecated, use Long.valueOf())"),
            ("new Boolean(", "new Boolean() constructor (deprecated, use Boolean.valueOf())"),
        ]
        
        found = []
        scanned = 0
        for java_file in build_dir.rglob("*.java"):
            if any(p in java_file.parts for p in ("target", "build", ".git")):
                continue
            if scanned >= 100:  # Cap for large repos
                break
            try:
                content = java_file.read_text(encoding="utf-8", errors="ignore")
                for pattern, description in deprecated_patterns:
                    if pattern in content and description not in found:
                        found.append(description)
                scanned += 1
            except Exception:
                pass
        return found

    def _calculate_risk_level(self, current_version: int, deprecated_apis: list, project_info: dict) -> str:
        """Calculate migration risk: Low / Medium / High."""
        score = 0
        # Version gap risk
        if current_version <= 8:
            score += 3
        elif current_version <= 11:
            score += 2
        elif current_version <= 16:
            score += 1
        # Deprecated API risk
        score += min(len(deprecated_apis), 3)
        # Multi-module risk
        if project_info.get("is_multi_module"):
            score += 1
        # External DB risk (needs connection during build/test)
        if project_info.get("database") not in ("None", "H2 (Embedded)", None):
            score += 1
        # WAR packaging risk (needs servlet container)
        if project_info.get("packaging_type") == "war":
            score += 1

        if score >= 6:
            return "High"
        elif score >= 3:
            return "Medium"
        return "Low"

    def find_build_file_directory(self, root_dir: Path) -> Path:
        for child in root_dir.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                if (child / "pom.xml").exists() or (child / "build.gradle").exists() or (child / "build.gradle.kts").exists():
                    return child
        return None

analysis_service = AnalysisService()
