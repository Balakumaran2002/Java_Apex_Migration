from fastapi import APIRouter
from app.ai.scheduler_db import scheduler_db
from app.ai.api_key_manager import api_key_manager

scheduler_router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])

@scheduler_router.get("/metrics")
async def get_scheduler_metrics():
    queue_metrics = scheduler_db.get_queue_metrics()
    
    # Get token status for all known keys
    token_status = []
    for k in api_key_manager._keys:
        bucket = scheduler_db.get_token_bucket(k.key_id)
        if bucket:
            token_status.append(bucket)
            
    return {
        "status": "success",
        "queue_metrics": queue_metrics,
        "token_status": token_status
    }
