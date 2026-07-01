from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json

from app.langgraph.graphs.migration_graph import enterprise_workflow
from app.langgraph.memory.h2_checkpointer import h2_checkpointer
from app.langgraph.state.migration_state import EnterpriseMigrationState

router = APIRouter(prefix="/enterprise", tags=["Enterprise Migration"])

class EnterpriseMigrationRequest(BaseModel):
    repo_url: str
    target_version: str
    api_key: str
    model_name: str
    project_dir: str

def run_enterprise_workflow(request: EnterpriseMigrationRequest):
    project_dir = Path(request.project_dir)
    
    initial_state = EnterpriseMigrationState(
        repo_url=request.repo_url,
        project_dir=project_dir,
        build_dir=project_dir,
        project_type="Unknown",
        build_tool="Unknown",
        is_maven=False,
        is_gradle=False,
        has_frontend=False,
        frontend_framework="None",
        chunks={},
        active_chunks=[],
        completed_chunks=[],
        dependencies=[],
        architecture_summary="",
        migration_status="STARTING",
        progress=0,
        retry_count=0,
        migration_checkpoint_id="init",
        generated_files=[],
        build_status="PENDING",
        testing_status="PENDING",
        documentation={},
        output_log=["[Enterprise] Starting LangGraph Orchestration..."],
        error_history=[],
        api_key=request.api_key,
        model_name=request.model_name
    )
    
    config = {"configurable": {"thread_id": str(project_dir.name)}}
    
    # We execute the graph in a blocking manner for the background task
    try:
        final_state = enterprise_workflow.invoke(initial_state, config=config)
        
        # Save output to a report file
        report_path = project_dir.parent / "enterprise_last_migration.json"
        
        # Filter out non-serializable objects (like Path)
        serializable_state = dict(final_state)
        serializable_state["project_dir"] = str(serializable_state["project_dir"])
        serializable_state["build_dir"] = str(serializable_state["build_dir"])
        
        with open(report_path, "w") as f:
            json.dump(serializable_state, f, indent=4)
            
    except Exception as e:
        import traceback
        print(f"Enterprise workflow failed: {traceback.format_exc()}")

@router.post("/migrate")
async def start_enterprise_migration(request: EnterpriseMigrationRequest, background_tasks: BackgroundTasks):
    """
    Kicks off the Enterprise LangGraph + CrewAI migration workflow.
    """
    if not Path(request.project_dir).exists():
        raise HTTPException(status_code=400, detail="Project directory does not exist.")
        
    background_tasks.add_task(run_enterprise_workflow, request)
    return {"message": "Enterprise migration started via LangGraph", "thread_id": Path(request.project_dir).name}

@router.get("/status/{thread_id}")
async def get_enterprise_status(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = h2_checkpointer.get(config)
    if not state:
        return {"status": "NOT_FOUND"}
        
    return state["channel_values"]
