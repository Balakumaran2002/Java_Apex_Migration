from langgraph.graph import StateGraph, END
from app.langgraph.state.migration_state import EnterpriseMigrationState
from app.langgraph.nodes.enterprise_nodes import (
    repository_upload_node,
    repository_scanner_node,
    repository_chunking_node,
    migration_planning_node,
    backend_migration_node,
    compilation_node,
    auto_error_fix_node,
    migration_report_node
)

def build_status_conditional(state: EnterpriseMigrationState):
    if state["build_status"] == "SUCCESS":
        return "success"
    if state["retry_count"] >= 3:
        return "max_retries"
    return "failure"

def create_enterprise_workflow() -> StateGraph:
    workflow = StateGraph(EnterpriseMigrationState)
    
    # Add Nodes
    workflow.add_node("upload", repository_upload_node)
    workflow.add_node("scanner", repository_scanner_node)
    workflow.add_node("chunking", repository_chunking_node)
    workflow.add_node("planning", migration_planning_node)
    workflow.add_node("backend_migration", backend_migration_node)
    workflow.add_node("compilation", compilation_node)
    workflow.add_node("auto_fix", auto_error_fix_node)
    workflow.add_node("report", migration_report_node)
    
    # Define Edges
    workflow.set_entry_point("upload")
    workflow.add_edge("upload", "scanner")
    workflow.add_edge("scanner", "chunking")
    workflow.add_edge("chunking", "planning")
    workflow.add_edge("planning", "backend_migration")
    workflow.add_edge("backend_migration", "compilation")
    
    # Conditional Edges for Compilation and Auto Fix
    workflow.add_conditional_edges(
        "compilation",
        build_status_conditional,
        {
            "success": "report",
            "failure": "auto_fix",
            "max_retries": "report"
        }
    )
    workflow.add_edge("auto_fix", "compilation")
    workflow.add_edge("report", END)
    
    return workflow.compile()

enterprise_workflow = create_enterprise_workflow()
