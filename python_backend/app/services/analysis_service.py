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
    SKIP_DIRS = {".git", "target", "build", "node_modules", ".idea", ".vscode", ".mvn", "__pycache__"}
    CONFIG_EXTENSIONS = {".xml", ".gradle", ".kts", ".properties", ".yml", ".yaml"}
    MAX_CONTEXT_CHARS = 90000
    MAX_CONFIG_FILE_BYTES = 256 * 1024
    MAX_JAVA_SCAN_BYTES = 64 * 1024
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
            
            if project_type.lower() != "java":
                return AnalysisResponse(
                repoUrl=repo_url,
                projectType=project_type,
                isJava=False,
                migrationRecommendation="This is not a Java project. Migration is not applicable.",
                errorMessage=f"Migration analysis only supports Java projects. We detected: {project_type}"
                )
            
            build_dir = clone_dir
            if not (build_dir / "pom.xml").exists() and not (build_dir / "build.gradle").exists() and not (build_dir / "build.gradle.kts").exists():
                sub_dir = self.find_build_file_directory(clone_dir)
                if sub_dir:
                    build_dir = sub_dir
            
            current_java_version = self.detect_java_version(build_dir)
            dependencies = []
            framework_versions = {}
            self.parse_dependencies_and_frameworks(build_dir, dependencies, framework_versions)
            
            context_notes = []
            context_parts = []
            self.collect_project_context(build_dir, clone_dir, context_parts, context_notes)
            project_context = "".join(context_parts)
            
            # Rule-based migration recommendation
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
            
            query = f"Migrating Java project. Current version: {current_java_version}. Frameworks: {framework_versions}."
            retrieved_docs = rag_service.search(query)
            
            rag_context = "Relevant Migration Knowledge:\n"
            for doc in retrieved_docs:
                rag_context += f"- From {doc['source']}:\n{doc['content']}\n\n"
                
            system_instruction = (
                "You are an expert Java architect advising on migration paths. "
                "Provide a concise explanation and code fix suggestions for the migration."
                "Do not repeat the recommendation itself, just provide the detailed reasoning based on the files you read, and step-by-step guidance."
            )

            processing_summary = ""
            if context_notes:
                processing_summary = "Repository Processing Summary:\n" + "\n".join(f"- {note}" for note in context_notes) + "\n\n"
            
            user_prompt = (
                f"{rag_context}\n\n"
                f"{processing_summary}"
                f"Project Details (Basic):\n"
                f"- Extracted Java Version: {current_java_version}\n"
                f"- Extracted Dependencies: {dependencies}\n"
                f"- Extracted Frameworks: {framework_versions}\n"
                f"- Planned Migration: {recommendation}\n\n"
                f"Raw Project Files Context:\n{project_context}\n\n"
                "Provide your detailed reasoning and step-by-step guidance."
            )
            
            ai_client = AIFactory.get_client()
            ai_result = ai_client.generate(user_prompt, system_instruction, api_key, model_name)
                
            reasoning = ai_result
            if processing_summary:
                reasoning = processing_summary + ai_result

            response = AnalysisResponse(
                repoUrl=repo_url,
                projectType="Java",
                isJava=True,
                detectedJavaVersion=current_java_version,
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
        
        if ext_counts.get("java", 0) > 0 or (repo_dir / "pom.xml").exists() or (repo_dir / "build.gradle").exists():
            return "Java"
        if ext_counts.get("py", 0) > 0:
            return "Python"
        if ext_counts.get("ts", 0) > 0 or ext_counts.get("tsx", 0) > 0:
            return "TypeScript"
        if ext_counts.get("js", 0) > 0 or ext_counts.get("jsx", 0) > 0:
            return "JavaScript"
        if ext_counts.get("c", 0) > 0 or ext_counts.get("cpp", 0) > 0 or ext_counts.get("h", 0) > 0:
            return "C/C++"
        return "Other"

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

    def find_build_file_directory(self, root_dir: Path) -> Path:
        for child in root_dir.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                if (child / "pom.xml").exists() or (child / "build.gradle").exists() or (child / "build.gradle.kts").exists():
                    return child
        return None

analysis_service = AnalysisService()
