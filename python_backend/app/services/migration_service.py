import os
import subprocess
import re
from pathlib import Path
from git import Repo
from app.config import app_config
from app.models import MigrationResponse
from app.services.java_runtime_service import java_runtime_service

class MigrationService:
    def migrate_repository(self, repo_url: str, target_version: str, api_key: str, model_name: str) -> MigrationResponse:
        try:
            from app.services.workflow_service import migration_workflow
            
            repo_name = repo_url.split('/')[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            
            project_dir = app_config.workspace_directory / repo_name
            
            initial_state = {
                "repo_url": repo_url,
                "target_version": target_version,
                "api_key": api_key,
                "model_name": model_name,
                "project_dir": project_dir,
                "build_dir": project_dir,
                "is_maven": False,
                "is_gradle": False,
                "output_log": [],
                "success": False,
                "build_result": {},
                "modified_files": [],
                "diff_output": "",
                "detailed_report": None,
                "used_provider": "",
                "error_message": ""
            }
            
            # Run LangGraph Orchestration
            final_state = migration_workflow.invoke(initial_state)
            
            if final_state.get("error_message"):
                return MigrationResponse(
                    success=False,
                    targetVersion=target_version,
                    buildStatus="Failed",
                    errorMessage=final_state["error_message"]
                )
                
            build_result = final_state.get("build_result", {})

            return MigrationResponse(
                success=final_state.get("success", False),
                targetVersion=target_version,
                modifiedFiles=final_state.get("modified_files", []),
                migrationSummary="\n".join(final_state.get("output_log", [])),
                buildStatus=build_result.get("status", "Unknown"),
                buildErrors=None if build_result.get("success") else build_result.get("buildLog"),
                suggestedFixes=build_result.get("suggestedFixes"),
                detailedReport=final_state.get("detailed_report"),
                gitDiff=final_state.get("diff_output"),
                fixHistory=build_result.get("fixHistory", []),
                usedProvider=final_state.get("used_provider")
            )
            
        except Exception as e:
            return MigrationResponse(
                success=False,
                targetVersion=target_version,
                buildStatus="Failed",
                errorMessage=str(e)
            )

    def run_maven_migration(self, project_dir: Path, target_version: str, output_log: list) -> bool:
        is_windows = os.name == 'nt'
        mvn_cmd = "mvn.cmd" if is_windows else "mvn"
        
        # Fallback to bundled maven
        local_maven = app_config.project_root / "apache-maven-3.9.6" / "bin" / mvn_cmd
        if local_maven.exists():
            mvn_cmd = str(local_maven)
            
        wrapper = project_dir / ("mvnw.cmd" if is_windows else "mvnw")
        wrapper_jar = project_dir / ".mvn" / "wrapper" / "maven-wrapper.jar"
        
        if wrapper.exists() and wrapper_jar.exists():
            if not is_windows:
                os.chmod(str(wrapper), 0o755)
            mvn_cmd = str(wrapper)

        # Apply pre-migration fixes
        pom = project_dir / "pom.xml"
        if pom.exists():
            content = pom.read_text(encoding='utf-8', errors='ignore')
            if "http://repo.spring.io" in content:
                content = content.replace("http://repo.spring.io", "https://repo.spring.io")
            
            # Remove plugins that cause build failures post-migration
            if "wro4j-maven-plugin" in content:
                content = re.sub(r'(?s)<plugin>\s*<groupId>ro\.isdc\.wro4j</groupId>.*?</plugin>', '', content)
            if "spring-javaformat-maven-plugin" in content:
                content = re.sub(r'(?s)<plugin>\s*<groupId>io\.spring\.javaformat</groupId>.*?</plugin>', '', content)
            if "maven-checkstyle-plugin" in content:
                content = re.sub(r'(?s)<plugin>\s*<groupId>org\.apache\.maven\.plugins</groupId>\s*<artifactId>maven-checkstyle-plugin</artifactId>.*?</plugin>', '', content)
            if "spotless-maven-plugin" in content:
                content = re.sub(r'(?s)<plugin>\s*<groupId>com\.diffplug\.spotless</groupId>.*?</plugin>', '', content)
            
            # Bump Lombok to 1.18.46 (minimum for JDK 21/25 compatibility)
            # Catches both <lombok.version>x.x.x</lombok.version> and inline <version>x.x.x</version> with lombok comment
            content = re.sub(r'<lombok\.version>[^<]+</lombok\.version>', '<lombok.version>1.18.46</lombok.version>', content)
            content = re.sub(r'<version>[^<]+</version>\s*<!--\s*lombok\s*-->', '<version>1.18.46</version>', content)
            # Also fix inline lombok dependency version declared directly (no property reference)
            content = re.sub(
                r'(<groupId>org\.projectlombok</groupId>\s*<artifactId>lombok</artifactId>\s*<version>)([^<]+)(</version>)',
                r'\g<1>1.18.46\g<3>',
                content
            )
            
            # If lombok is a dependency but lombok.version property is missing, inject it
            if "org.projectlombok" in content and "<lombok.version>" not in content:
                content = content.replace("<properties>", "<properties>\n\t\t<lombok.version>1.18.46</lombok.version>")
                
            # If lombok is a dependency but maven-compiler-plugin doesn't have annotationProcessorPaths, inject it
            if "org.projectlombok" in content and "annotationProcessorPaths" not in content:
                plugin_config = """
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <release>${java.version}</release>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                            <version>${lombok.version}</version>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>
"""
                if "<plugins>" in content:
                    content = content.replace("<plugins>", f"<plugins>{plugin_config}", 1)
                elif "<build>" in content:
                    content = content.replace("<build>", f"<build>\n\t\t<plugins>{plugin_config}\t\t</plugins>", 1)

            # Force upgrade Java compiler properties to the target version
            content = re.sub(r'<java\.version>.*?</java\.version>', f'<java.version>{target_version}</java.version>', content)
            content = re.sub(r'<maven\.compiler\.source>.*?</maven\.compiler\.source>', f'<maven.compiler.source>{target_version}</maven.compiler.source>', content)
            content = re.sub(r'<maven\.compiler\.target>.*?</maven\.compiler\.target>', f'<maven.compiler.target>{target_version}</maven.compiler.target>', content)
            
            # Force upgrade hardcoded maven-compiler-plugin configuration if it exists
            content = re.sub(r'<source>(?:1\.[0-8]|[0-9]+)</source>', f'<source>{target_version}</source>', content)
            content = re.sub(r'<target>(?:1\.[0-8]|[0-9]+)</target>', f'<target>{target_version}</target>', content)
            content = re.sub(r'<release>(?:1\.[0-8]|[0-9]+)</release>', f'<release>{target_version}</release>', content)
            
            pom.write_text(content, encoding='utf-8')

            has_spring_boot = "spring-boot" in content
            has_javax = True # Always run Jakarta migration for Java 17+ as javax imports might only exist in source files
            has_hibernate = "hibernate" in content
            has_junit = "junit" in content
            
        phases = []
        if target_version == "11":
            phases.append("org.openrewrite.java.migrate.Java8toJava11")
        else:
            phases.append(f"org.openrewrite.java.migrate.UpgradeToJava{target_version}")
        
        if (has_javax or has_hibernate) and (target_version == "17" or target_version == "21" or target_version == "25"):
            jakarta_recipes = []
            if has_javax:
                jakarta_recipes.append("org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta")
            if has_hibernate:
                jakarta_recipes.append("org.openrewrite.hibernate.Hibernate5To6Migration")
            phases.append(",".join(jakarta_recipes))
            
        if has_spring_boot and (target_version == "17" or target_version == "21" or target_version == "25"):
            phases.append("org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_2")

        if has_junit:
            phases.append("org.openrewrite.java.testing.junit5.JUnit5BestPractices")

        all_recipes = ",".join(phases)
        output_log.append(f"\n--- Starting Migration ---")
        command = [
            mvn_cmd, "-B", "-T", "1C",
            "org.openrewrite.maven:rewrite-maven-plugin:run",
            "-Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:RELEASE,org.openrewrite.recipe:rewrite-spring:RELEASE",
            f"-Drewrite.activeRecipes={all_recipes}",
            "-DskipTests=true",
            "-Dmaven.test.skip=true"
        ]
        overall_success = self.execute_process(command, project_dir, output_log)
        return overall_success

    def run_gradle_migration(self, project_dir: Path, target_version: str, output_log: list) -> bool:
        is_windows = os.name == 'nt'
        gradle_cmd = "gradle.bat" if is_windows else "gradle"
        
        wrapper = project_dir / ("gradlew.bat" if is_windows else "gradlew")
        if wrapper.exists():
            if not is_windows:
                os.chmod(str(wrapper), 0o755)
            gradle_cmd = str(wrapper)
            
        has_spring_boot = False
        has_javax = False
        has_hibernate = False
        has_junit = False
        
        build_gradle = project_dir / "build.gradle"
        if not build_gradle.exists():
            build_gradle = project_dir / "build.gradle.kts"
            
        if build_gradle.exists():
            content = build_gradle.read_text(encoding='utf-8', errors='ignore')
            has_spring_boot = "spring-boot" in content
            has_javax = True # Always run Jakarta migration for Java 17+
            has_hibernate = "hibernate" in content
            has_junit = "junit" in content

        phases = []
        if target_version == "11":
            phases.append("org.openrewrite.java.migrate.Java8toJava11")
        else:
            phases.append(f"org.openrewrite.java.migrate.UpgradeToJava{target_version}")
        
        if (has_javax or has_hibernate) and (target_version == "17" or target_version == "21" or target_version == "25"):
            jakarta_recipes = []
            if has_javax:
                jakarta_recipes.append("org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta")
            if has_hibernate:
                jakarta_recipes.append("org.openrewrite.hibernate.Hibernate5To6Migration")
            phases.append(",".join(jakarta_recipes))
            
        if has_spring_boot and (target_version == "17" or target_version == "21" or target_version == "25"):
            phases.append("org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_2")

        if has_junit:
            phases.append("org.openrewrite.java.testing.junit5.JUnit5BestPractices")

        all_recipes = ",".join(phases)
        output_log.append(f"\n--- Starting Migration ---")
        command = [
            gradle_cmd,
            "rewriteRun",
            f"-DactiveRecipe={all_recipes}",
            "-x", "test"
        ]
        
        overall_success = self.execute_process(command, project_dir, output_log)
        return overall_success

    def execute_process(self, command: list, project_dir: Path, output_log: list) -> bool:
        env, java_home = java_runtime_service.prepare_env()
        if java_home:
            output_log.append(f"[Java Runtime] Using preferred JDK 21 at: {java_home}")

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
            return process.returncode == 0
        except Exception as e:
            output_log.append(f"Execution Exception: {str(e)}")
            return False

migration_service = MigrationService()
