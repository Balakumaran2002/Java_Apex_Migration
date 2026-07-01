import traceback
from app.celery_app import celery_app
from app.services.migration_service import migration_service
from app.services.llm_runtime_service import llm_runtime_service
from app.services.history_service import history_service
from app.config import app_config
from pathlib import Path

@celery_app.task(bind=True, name="run_background_migration")
def run_background_migration(self, repo_url: str, target_version: str, api_key: str, model_name: str, provider: str = None):
    if provider:
        app_config.ai_provider = provider
    
    try:
        with llm_runtime_service.with_job(self.request.id, f"Migrating repository {repo_url.split('/')[-1]}"):
            result = migration_service.migrate_repository(repo_url, target_version, api_key, model_name)
        
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.dict()
        status_str = "SUCCESS" if result_dict.get("success") else "FAILED"
        
        history_service.update_record(
            migration_id=self.request.id,
            status=status_str,
            result_dict=result_dict
        )
        return result_dict
    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        history_service.update_record(
            migration_id=self.request.id,
            status="FAILURE",
            error_message=error_msg
        )
        raise e
