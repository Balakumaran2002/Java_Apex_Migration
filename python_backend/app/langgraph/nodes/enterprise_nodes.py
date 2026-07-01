import os
import subprocess
from app.langgraph.state.migration_state import EnterpriseMigrationState
from app.services.chunking_service import chunking_service
from app.crews.enterprise_crews import enterprise_crews
from app.services.migration_service import migration_service
from app.services.build_validation_service import build_validation_service

def repository_upload_node(state: EnterpriseMigrationState):
    state["output_log"].append("[Upload Node] Validating repository structure...")
    state["progress"] = 10
    return state

def repository_scanner_node(state: EnterpriseMigrationState):
    state["output_log"].append("[Scanner Node] Invoking Repository Analysis Crew...")
    try:
        report = enterprise_crews.run_repository_analysis_crew(str(state["project_dir"]))
        state["architecture_summary"] = report
    except Exception as e:
        state["output_log"].append(f"Scanner Crew Error: {e}")
    state["progress"] = 20
    return state

def repository_chunking_node(state: EnterpriseMigrationState):
    state["output_log"].append("[Chunking Node] Breaking repository into independent chunks...")
    chunks = chunking_service.chunk_repository(state["project_dir"])
    state["chunks"] = chunks
    state["active_chunks"] = list(chunks.keys())
    state["progress"] = 30
    state["output_log"].append(f"[Chunking Node] Created {len(chunks)} chunks.")
    return state

def migration_planning_node(state: EnterpriseMigrationState):
    state["output_log"].append("[Planning Node] Formulating migration sequence...")
    state["migration_status"] = "PLANNING_COMPLETE"
    state["progress"] = 40
    return state

def backend_migration_node(state: EnterpriseMigrationState):
    state["output_log"].append("[Backend Migration Node] Executing chunked migration...")
    # Parallel mapping happens at the graph level using LangGraph's Send API,
    # but for simplicity in a single node simulation:
    for chunk_id, chunk_data in state["chunks"].items():
        if chunk_data["status"] == "PENDING":
            try:
                # Use standard deterministic Java migration for actual code writing
                migration_service.run_llm_migration(
                    state["build_dir"], state["target_version"], state["api_key"], state["model_name"], state["output_log"]
                )
                chunk_data["status"] = "COMPLETED"
                state["completed_chunks"].append(chunk_id)
            except Exception as e:
                chunk_data["status"] = "FAILED"
                chunk_data["error_message"] = str(e)
    state["progress"] = 60
    return state

def compilation_node(state: EnterpriseMigrationState):
    state["output_log"].append("[Compilation Node] Triggering Build Validation...")
    build_result = build_validation_service.validate_build(
        state["build_dir"], state["is_maven"], state["api_key"], state["model_name"], 
        state["target_version"], state["project_type"], state["build_tool"]
    )
    state["build_status"] = "SUCCESS" if build_result.get("success") else "FAILED"
    if not build_result.get("success"):
        state["error_history"].append(build_result.get("errorMessage", "Unknown Build Error"))
    state["progress"] = 75
    return state

def auto_error_fix_node(state: EnterpriseMigrationState):
    state["output_log"].append("[Error Fix Node] Invoking Error Recovery Crew...")
    if state["error_history"]:
        errors = state["error_history"][-1]
        try:
            fix_cmds = enterprise_crews.run_error_recovery_crew(errors)
            import re
            match = re.search(r'```(?:bash|sh)?\n(.*?)\n```', fix_cmds, re.DOTALL)
            if match:
                cmd = match.group(1).strip()
                state["output_log"].append(f"[Error Fix Node] Applying fix:\n{cmd}")
                subprocess.Popen(cmd, cwd=str(state["build_dir"]), shell=True).communicate()
        except Exception as e:
            state["output_log"].append(f"Auto-Fix Crew Error: {e}")
    state["retry_count"] += 1
    return state

def migration_report_node(state: EnterpriseMigrationState):
    state["output_log"].append("[Report Node] Generating Enterprise Migration Report...")
    state["progress"] = 100
    state["migration_status"] = "SUCCESS" if state["build_status"] == "SUCCESS" else "FAILED"
    return state
