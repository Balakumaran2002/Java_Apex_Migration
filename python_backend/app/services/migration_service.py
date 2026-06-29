import os
import re
import subprocess
from pathlib import Path

from app.config import app_config
from app.models import MigrationResponse
from app.services.java_compatibility_service import java_compatibility_service
from app.services.java_runtime_service import java_runtime_service


class MigrationService:
    def migrate_repository(self, repo_url: str, target_version: str, api_key: str, model_name: str) -> MigrationResponse:
        try:
            from app.services.workflow_service import migration_workflow

            repo_name = repo_url.split("/")[-1]
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
                "has_frontend": False,
                "frontend_dir": None,
                "frontend_framework": "None",
                "output_log": [],
                "success": False,
                "build_result": {},
                "frontend_result": {},
                "modified_files": [],
                "diff_output": "",
                "detailed_report": None,
                "used_provider": "",
                "error_message": "",
            }

            final_state = migration_workflow.invoke(initial_state)

            if final_state.get("error_message"):
                return MigrationResponse(
                    success=False,
                    targetVersion=target_version,
                    buildStatus="Failed",
                    errorMessage=final_state["error_message"],
                )

            build_result = final_state.get("build_result", {})
            project_type = final_state.get("project_type", "Java")
            build_success = build_result.get("success", False)

            if project_type != "Java":
                overall_success = build_success
            else:
                overall_success = final_state.get("success", False) and build_success

            return MigrationResponse(
                success=overall_success,
                targetVersion=target_version,
                modifiedFiles=final_state.get("modified_files", []),
                migrationSummary="\n".join(final_state.get("output_log", [])),
                buildStatus=build_result.get("status", "Unknown"),
                buildErrors=None if build_result.get("success") else build_result.get("buildLog"),
                suggestedFixes=build_result.get("suggestedFixes"),
                detailedReport=final_state.get("detailed_report"),
                gitDiff=final_state.get("diff_output"),
                fixHistory=build_result.get("fixHistory", []),
                usedProvider=final_state.get("used_provider"),
            )
        except Exception as exc:
            return MigrationResponse(
                success=False,
                targetVersion=target_version,
                buildStatus="Failed",
                errorMessage=str(exc),
            )

    def run_maven_migration(self, project_dir: Path, target_version: str, output_log: list) -> bool:
        plan = java_compatibility_service.analyze_and_select(
            project_dir,
            target_version=target_version,
            build_tool="Maven",
            output_log=output_log,
        )
        if not plan.get("success"):
            output_log.append(f"[Java Compatibility] Migration aborted: {plan['reason']}")
            return False

        mvn_cmd = java_compatibility_service.resolve_maven_command(project_dir)
        self._apply_pre_migration_fixes(project_dir, output_log)
        java_compatibility_service.align_build_configuration(project_dir, "Maven", plan, output_log)

        pom = project_dir / "pom.xml"
        pom_content = pom.read_text(encoding="utf-8", errors="ignore") if pom.exists() else ""
        has_spring_boot = "spring-boot" in pom_content
        has_javax = True
        has_hibernate = "hibernate" in pom_content
        has_junit = "junit" in pom_content

        recipe_target = plan["effective_release"]
        phases = []
        if recipe_target == 11:
            phases.append("org.openrewrite.java.migrate.Java8toJava11")
        else:
            phases.append(f"org.openrewrite.java.migrate.UpgradeToJava{recipe_target}")

        if (has_javax or has_hibernate) and recipe_target in {17, 21, 25}:
            jakarta_recipes = []
            if has_javax:
                jakarta_recipes.append("org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta")
            if has_hibernate:
                jakarta_recipes.append("org.openrewrite.hibernate.Hibernate5To6Migration")
            phases.append(",".join(jakarta_recipes))

        if has_spring_boot and recipe_target in {17, 21, 25}:
            phases.append("org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_2")

        if has_junit:
            phases.append("org.openrewrite.java.testing.junit5.JUnit5BestPractices")

        command = [
            mvn_cmd,
            "-B",
            "-T",
            "1C",
            "org.openrewrite.maven:rewrite-maven-plugin:run",
            "-Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:RELEASE,org.openrewrite.recipe:rewrite-spring:RELEASE",
            f"-Drewrite.activeRecipes={','.join(phases)}",
            "-DskipTests=true",
            "-Dmaven.test.skip=true",
        ]
        output_log.append("\n--- Starting Migration ---")
        output_log.append(f"[Java Compatibility] OpenRewrite target Java: {recipe_target}")
        return self.execute_process(command, project_dir, output_log, plan)

    def run_gradle_migration(self, project_dir: Path, target_version: str, output_log: list) -> bool:
        plan = java_compatibility_service.analyze_and_select(
            project_dir,
            target_version=target_version,
            build_tool="Gradle",
            output_log=output_log,
        )
        if not plan.get("success"):
            output_log.append(f"[Java Compatibility] Migration aborted: {plan['reason']}")
            return False

        gradle_cmd = java_compatibility_service.resolve_gradle_command(project_dir)
        java_compatibility_service.align_build_configuration(project_dir, "Gradle", plan, output_log)

        build_gradle = project_dir / "build.gradle"
        if not build_gradle.exists():
            build_gradle = project_dir / "build.gradle.kts"
        build_content = build_gradle.read_text(encoding="utf-8", errors="ignore") if build_gradle.exists() else ""

        has_spring_boot = "spring-boot" in build_content
        has_javax = True
        has_hibernate = "hibernate" in build_content
        has_junit = "junit" in build_content

        recipe_target = plan["effective_release"]
        phases = []
        if recipe_target == 11:
            phases.append("org.openrewrite.java.migrate.Java8toJava11")
        else:
            phases.append(f"org.openrewrite.java.migrate.UpgradeToJava{recipe_target}")

        if (has_javax or has_hibernate) and recipe_target in {17, 21, 25}:
            jakarta_recipes = []
            if has_javax:
                jakarta_recipes.append("org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta")
            if has_hibernate:
                jakarta_recipes.append("org.openrewrite.hibernate.Hibernate5To6Migration")
            phases.append(",".join(jakarta_recipes))

        if has_spring_boot and recipe_target in {17, 21, 25}:
            phases.append("org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_2")

        if has_junit:
            phases.append("org.openrewrite.java.testing.junit5.JUnit5BestPractices")

        command = [
            gradle_cmd,
            "rewriteRun",
            f"-DactiveRecipe={','.join(phases)}",
            "-x",
            "test",
        ]
        output_log.append("\n--- Starting Migration ---")
        output_log.append(f"[Java Compatibility] OpenRewrite target Java: {recipe_target}")
        return self.execute_process(command, project_dir, output_log, plan)

    def execute_process(self, command: list, project_dir: Path, output_log: list, plan: dict = None) -> bool:
        env, java_home = java_runtime_service.prepare_env(
            project_dir=project_dir,
            selection=plan,
        )
        if java_home:
            output_log.append(f"[Java Runtime] Using selected JDK at: {java_home}")

        try:
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
            return process.returncode == 0
        except Exception as exc:
            output_log.append(f"Execution Exception: {str(exc)}")
            return False

    def _apply_pre_migration_fixes(self, project_dir: Path, output_log: list) -> None:
        pom = project_dir / "pom.xml"
        if not pom.exists():
            return

        content = pom.read_text(encoding="utf-8", errors="ignore")
        updated = content

        if "http://repo.spring.io" in updated:
            updated = updated.replace("http://repo.spring.io", "https://repo.spring.io")

        plugin_patterns = [
            r"(?s)<plugin>\s*<groupId>ro\.isdc\.wro4j</groupId>.*?</plugin>",
            r"(?s)<plugin>\s*<groupId>io\.spring\.javaformat</groupId>.*?</plugin>",
            r"(?s)<plugin>\s*<groupId>org\.apache\.maven\.plugins</groupId>\s*<artifactId>maven-checkstyle-plugin</artifactId>.*?</plugin>",
            r"(?s)<plugin>\s*<groupId>com\.diffplug\.spotless</groupId>.*?</plugin>",
        ]
        for pattern in plugin_patterns:
            updated = re.sub(pattern, "", updated)

        updated = re.sub(
            r"<lombok\.version>[^<]+</lombok\.version>",
            "<lombok.version>1.18.46</lombok.version>",
            updated,
        )
        updated = re.sub(
            r"<version>[^<]+</version>\s*<!--\s*lombok\s*-->",
            "<version>1.18.46</version>",
            updated,
        )
        updated = re.sub(
            r"(<groupId>org\.projectlombok</groupId>\s*<artifactId>lombok</artifactId>\s*<version>)([^<]+)(</version>)",
            r"\g<1>1.18.46\g<3>",
            updated,
        )

        if "org.projectlombok" in updated and "<lombok.version>" not in updated and "<properties>" in updated:
            updated = updated.replace(
                "<properties>",
                "<properties>\n\t\t<lombok.version>1.18.46</lombok.version>",
                1,
            )

        if "org.projectlombok" in updated and "annotationProcessorPaths" not in updated:
            plugin_config = """
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
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
            if "<plugins>" in updated:
                updated = updated.replace("<plugins>", f"<plugins>{plugin_config}", 1)
            elif "<build>" in updated:
                updated = updated.replace("<build>", f"<build>\n\t\t<plugins>{plugin_config}\t\t</plugins>", 1)

        if updated != content:
            pom.write_text(updated, encoding="utf-8")
            output_log.append("[Migration Prep] Applied safe Maven cleanup fixes before migration.")


migration_service = MigrationService()
