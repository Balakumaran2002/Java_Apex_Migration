import os
import re
import subprocess
import json
from pathlib import Path

from app.config import app_config
from app.models import MigrationResponse
from app.services.java_compatibility_service import java_compatibility_service
from app.services.llm_runtime_service import llm_runtime_service
from app.services.java_runtime_service import java_runtime_service


class MigrationService:
    def _load_cached_analysis(self, repo_name: str, repo_url: str) -> dict:
        metadata_path = app_config.workspace_directory / "reports" / "repository_metadata" / f"{repo_name}.json"
        if metadata_path.exists():
            try:
                cached = json.loads(metadata_path.read_text(encoding="utf-8"))
                if cached.get("repoUrl"):
                    return cached
            except Exception:
                pass

        report_path = app_config.workspace_directory / "reports" / "last_analysis.json"
        if not report_path.exists():
            return {}
        try:
            cached = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        cached_name = str(cached.get("repoUrl", "")).rstrip("/").split("/")[-1].replace(".git", "")
        if cached_name == repo_name:
            return cached
        if str(cached.get("repoUrl", "")).rstrip("/") == repo_url.rstrip("/"):
            return cached
        return {}

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
                "analysis_result": self._load_cached_analysis(repo_name, repo_url),
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
            llm_status = llm_runtime_service.get_status()
            used_provider = final_state.get("used_provider") or build_result.get("usedProvider")

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
                usedProvider=used_provider,
                llmUsage=build_result.get("llmUsage"),
                llmQuota=llm_status.get("providers", {}).get(used_provider or app_config.ai_provider, {}),
            )
        except Exception as exc:
            return MigrationResponse(
                success=False,
                targetVersion=target_version,
                buildStatus="Failed",
                errorMessage=str(exc),
            )

    def run_llm_migration(self, project_dir: Path, target_version: str, api_key: str, model_name: str, output_log: list) -> bool:
        from app.services.llm_migration_engine import llm_migration_engine
        return llm_migration_engine.migrate_repository(project_dir, target_version, api_key, model_name, output_log)


migration_service = MigrationService()
