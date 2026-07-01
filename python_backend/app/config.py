import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class AppConfig:
    def __init__(self):
        self.ai_provider = os.getenv("AI_PROVIDER", "gemini")
        self.work_dir_name = os.getenv("APP_WORK_DIR", "workspace")
        self.vector_db = os.getenv("VECTOR_DB", "faiss").lower()
        
        # Scheduler Configuration
        self.token_bucket_size = int(os.getenv("TOKEN_BUCKET_SIZE", "30"))
        self.token_refill_interval = int(os.getenv("TOKEN_REFILL_INTERVAL", "60"))
        self.max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "120"))
        self.max_queue_size = int(os.getenv("MAX_QUEUE_SIZE", "10000"))
        self.queue_poll_interval = int(os.getenv("QUEUE_POLL_INTERVAL", "1"))
        self.enable_auto_rotation = os.getenv("ENABLE_AUTO_ROTATION", "true").lower() == "true"
        self.enable_exponential_backoff = os.getenv("ENABLE_EXPONENTIAL_BACKOFF", "true").lower() == "true"

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
