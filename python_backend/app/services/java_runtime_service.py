import os
from pathlib import Path
from typing import Optional, Tuple

from app.services.java_compatibility_service import java_compatibility_service


class JavaRuntimeService:
    def find_preferred_java_home(self, target_version: Optional[int] = None, project_dir: Optional[Path] = None) -> Optional[Path]:
        selection = java_compatibility_service.analyze_and_select(
            project_dir or Path.cwd(),
            str(target_version) if target_version else None,
        )
        return selection.get("java_home")

    def prepare_env(
        self,
        env: Optional[dict] = None,
        target_version: Optional[int] = None,
        project_dir: Optional[Path] = None,
        selection: Optional[dict] = None,
    ) -> Tuple[dict, Optional[Path]]:
        chosen = selection or java_compatibility_service.analyze_and_select(
            project_dir or Path.cwd(),
            str(target_version) if target_version else None,
        )
        prepared = java_compatibility_service.prepare_env(chosen, env)
        return prepared, chosen.get("java_home")

    def get_installed_java_version(self, target_version: Optional[int] = None, project_dir: Optional[Path] = None) -> int:
        selection = java_compatibility_service.analyze_and_select(
            project_dir or Path.cwd(),
            str(target_version) if target_version else None,
        )
        selected = selection.get("selected_jdk")
        if selected:
            return selected["version"]
        return -1

    def get_maven_runtime_version(self, project_dir: Path) -> int:
        selection = java_compatibility_service.analyze_and_select(project_dir)
        diagnostics = selection.get("diagnostics", {})
        match_text = diagnostics.get("mvn_version", "")
        import re

        match = re.search(r"Java version:\s*([^\s,]+)", match_text)
        if match:
            parsed = java_compatibility_service.normalize_version(match.group(1))
            if parsed is not None:
                return parsed

        selected = selection.get("selected_jdk")
        if selected:
            return selected["version"]
        return -1


java_runtime_service = JavaRuntimeService()
