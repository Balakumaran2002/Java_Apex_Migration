from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class AnalyzeRequest(BaseModel):
    repoUrl: str
    apiKey: Optional[str] = None
    provider: Optional[str] = None
    modelName: Optional[str] = None

class MigrateRequest(BaseModel):
    repoUrl: str
    targetVersion: str
    apiKey: Optional[str] = None
    provider: Optional[str] = None
    modelName: Optional[str] = None

class ConvertRequest(BaseModel):
    files: Dict[str, str]
    apiKey: Optional[str] = None
    provider: Optional[str] = None
    modelName: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    apiKey: Optional[str] = None
    provider: Optional[str] = None
    modelName: Optional[str] = None

class ChatResponse(BaseModel):
    response: Optional[str] = None
    errorMessage: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    status: str


class AnalysisResponse(BaseModel):
    repoUrl: str
    projectType: Optional[str] = None
    isJava: bool = True
    detectedJavaVersion: Optional[str] = None
    dependencies: List[str] = []
    frameworkVersions: Dict[str, str] = {}
    migrationRecommendation: Optional[str] = None
    reasoning: Optional[str] = None
    errorMessage: Optional[str] = None
    usedProvider: Optional[str] = None

class MigrationResponse(BaseModel):
    success: bool
    targetVersion: str
    modifiedFiles: List[str] = []
    buildStatus: str
    suggestedFixes: Optional[str] = None
    detailedReport: Optional[str] = None
    buildErrors: Optional[str] = None
    migrationSummary: Optional[str] = None
    errorMessage: Optional[str] = None
    gitDiff: Optional[str] = None
    fixHistory: Optional[List[Dict[str, Any]]] = []
    usedProvider: Optional[str] = None

class ConvertedFile(BaseModel):
    originalName: str
    newName: str
    content: str
    explanation: Optional[str] = None

class ConversionResponse(BaseModel):
    success: bool
    convertedFiles: List[ConvertedFile] = []
    errorMessage: Optional[str] = None

class ExecutionStatus(BaseModel):
    repository: str
    version: str # "original" | "migrated"
    status: str # "RUNNING" | "STOPPED" | "FAILED"

class ExecutionResult(BaseModel):
    repository: str
    version: str # "original" | "migrated"
    buildStatus: str
    startupStatus: str
    testStatus: str
    testsPassed: int = 0
    testsFailed: int = 0
    executionTime: str = ""
    logs: str = ""

class RunStartRequest(BaseModel):
    repoName: str

class RunStatusResponse(BaseModel):
    repoName: str
    status: str  # "STARTING" | "RUNNING" | "FAILED" | "STOPPED" | "IDLE"
    port: Optional[int] = None
    projectType: Optional[str] = None
    previewUrl: Optional[str] = None
    endpoints: List[Dict[str, str]] = []
    errorReason: Optional[str] = None
