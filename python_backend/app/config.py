import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class AppConfig:
    def __init__(self):
        self.ai_provider = os.getenv("AI_PROVIDER", "gemini")
        self.work_dir_name = os.getenv("APP_WORK_DIR", "workspace")
        self.vector_db = os.getenv("VECTOR_DB", "faiss").lower()

    @property
    def workspace_directory(self) -> Path:
        # In java it was java_convertion/backend/workspace
        # Here we make it java_convertion/python_backend/workspace
        dir_path = Path(self.work_dir_name)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path.absolute()

    @property
    def project_root(self) -> Path:
        # Returns java_convertion directory
        return self.workspace_directory.parent.parent

app_config = AppConfig()
