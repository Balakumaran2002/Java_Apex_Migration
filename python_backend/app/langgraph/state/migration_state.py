from typing import TypedDict, Any, List, Dict
import operator
from typing_extensions import Annotated
from pathlib import Path

class ChunkState(TypedDict):
    chunk_id: str
    files: List[str]
    status: str
    error_message: str
    retries: int

class EnterpriseMigrationState(TypedDict):
    # Repository Info
    repo_url: str
    project_dir: Path
    build_dir: Path
    project_type: str
    build_tool: str
    is_maven: bool
    is_gradle: bool
    has_frontend: bool
    frontend_framework: str
    
    # Chunking Engine
    chunks: Dict[str, ChunkState]
    active_chunks: List[str]
    completed_chunks: List[str]
    
    # Analysis & Architecture
    dependencies: List[str]
    architecture_summary: str
    
    # Workflow State
    migration_status: str
    progress: int
    retry_count: int
    migration_checkpoint_id: str
    
    # Results
    generated_files: Annotated[List[str], operator.add]
    build_status: str
    testing_status: str
    documentation: Dict[str, str]
    
    # Logs and Errors
    output_log: Annotated[List[str], operator.add]
    error_history: Annotated[List[str], operator.add]
    
    # API context
    api_key: str
    model_name: str
