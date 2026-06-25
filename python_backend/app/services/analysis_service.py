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
    
    def analyze_repository(self, repo_url: str, api_key: str, model_name: str) -> AnalysisResponse:
        try:
            clone_dir = self.clone_repository(repo_url)
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
            
            # Read all relevant files to provide comprehensive context
            project_context = ""
            for ext in ['.xml', '.gradle', '.kts', '.properties', '.yml', '.yaml']:
                for file_path in build_dir.rglob(f"*{ext}"):
                    if 'target' not in file_path.parts and 'build' not in file_path.parts and 'node_modules' not in file_path.parts:
                        try:
                            content = file_path.read_text(encoding='utf-8', errors='ignore')
                            if len(content) > 10000:
                                content = content[:10000] + "\n...[TRUNCATED]"
                            project_context += f"\n\n--- File: {file_path.relative_to(clone_dir)} ---\n{content}"
                        except Exception:
                            pass
            
            # Gather unique imports from Java files
            java_imports = set()
            for java_file in build_dir.rglob("*.java"):
                try:
                    content = java_file.read_text(encoding='utf-8', errors='ignore')
                    for line in content.splitlines():
                        if line.strip().startswith("import "):
                            java_imports.add(line.strip())
                except Exception:
                    pass
            
            if java_imports:
                project_context += "\n\n--- Unique Java Imports Across Project ---\n" + "\n".join(sorted(list(java_imports))[:100]) # limit to 100 imports to save tokens
            
            query = f"Migrating Java project. Current version: {current_java_version}. Frameworks: {framework_versions}."
            retrieved_docs = rag_service.search(query)
            
            rag_context = "Relevant Migration Knowledge:\n"
            for doc in retrieved_docs:
                rag_context += f"- From {doc['source']}:\n{doc['content']}\n\n"
                
            system_instruction = (
                "You are an expert Java architect advising on migration paths. "
                "You must read the raw project files provided below to accurately determine versions, dependencies, and configuration details. "
                "Use the provided knowledge base context along with the raw file context to analyze the project details and give concrete "
                "recommendations on whether the project should be migrated to Java 17 or Java 21, and Spring Boot version upgrades. "
                "Be detailed and provide formatting (markdown)."
            )
            
            user_prompt = (
                f"{rag_context}\n\n"
                f"Project Details (Basic):\n"
                f"- Extracted Java Version: {current_java_version}\n"
                f"- Extracted Dependencies: {dependencies}\n"
                f"- Extracted Frameworks: {framework_versions}\n\n"
                f"Raw Project Files Context:\n{project_context}\n\n"
                "Provide your recommendation. If the project is already using Java 21 or Java 25 and Spring Boot 3.x, say:\n"
                "\"This project is already using the latest Java version. No migration is required.\"\n"
                "Otherwise, provide a clear suggestion: \"Migrate to Java 17\" or \"Migrate to Java 21\" followed by detailed reasoning based on the files you read, and step-by-step guidance."
            )
            
            ai_client = AIFactory.get_client()
            ai_result = ai_client.generate(user_prompt, system_instruction, api_key, model_name)
            
            recommendation = "Migrate to Java 21"
            if "latest Java version" in ai_result or "No migration is required" in ai_result:
                recommendation = "This project is already using the latest Java version. No migration is required."
            elif "Migrate to Java 17" in ai_result:
                recommendation = "Migrate to Java 17"
            elif "Migrate to Java 21" in ai_result:
                recommendation = "Migrate to Java 21"
                
            return AnalysisResponse(
                repoUrl=repo_url,
                projectType="Java",
                isJava=True,
                detectedJavaVersion=current_java_version,
                dependencies=dependencies,
                frameworkVersions=framework_versions,
                migrationRecommendation=recommendation,
                reasoning=ai_result,
                errorMessage=None,
                usedProvider=getattr(ai_client, "last_provider_used", None)
            )
            
        except Exception as e:
            return AnalysisResponse(
                repoUrl=repo_url,
                projectType="Unknown",
                isJava=False,
                errorMessage=str(e)
            )

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
