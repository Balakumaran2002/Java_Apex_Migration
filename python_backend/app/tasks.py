from app.celery_app import celery_app
from app.services.migration_service import migration_service
from app.config import app_config
from pathlib import Path

@celery_app.task(bind=True, name="run_background_migration")
def run_background_migration(self, repo_url: str, target_version: str, api_key: str, model_name: str, provider: str = None):
    if provider:
        app_config.ai_provider = provider
    result = migration_service.migrate_repository(repo_url, target_version, api_key, model_name)
    return result.model_dump() if hasattr(result, 'model_dump') else result.dict()
