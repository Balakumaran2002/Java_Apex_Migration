import os
import re
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from fastapi import APIRouter, Response, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
import httpx
from app.models import (
    AnalyzeRequest, AnalysisResponse,
    MigrateRequest, MigrationResponse, TaskResponse,
    ConvertRequest, ConversionResponse,
    ChatRequest, ChatResponse,
    ExecutionStatus, ExecutionResult,
    RunStartRequest, RunStatusResponse
)
from app.tasks import run_background_migration
from celery.result import AsyncResult
from app.config import app_config
from app.services.rag_service import rag_service
from app.services.analysis_service import analysis_service
from app.services.migration_service import migration_service
from app.services.code_conversion_service import code_conversion_service
from app.services.report_service import report_service
from app.services.execution_service import execution_service
from app.ai.ai_factory import AIFactory
import asyncio

router = APIRouter()
PREVIEW_PROXY_PREFIX = "/api/run/preview"


def get_backend_origin(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def get_absolute_preview_url(request: Request, repo_name: str) -> str:
    return f"{get_backend_origin(request)}{PREVIEW_PROXY_PREFIX}/{repo_name}"


def attach_preview_url(status: dict, request: Request, repo_name: str) -> dict:
    payload = dict(status)
    preview_url = payload.get("previewUrl")
    if preview_url:
        if preview_url.startswith("/"):
            payload["previewUrl"] = f"{get_backend_origin(request)}{preview_url}"
        return payload

    if payload.get("status") in {"STARTING", "RUNNING", "SUCCESS", "RUNNING_JAVA"}:
        # Generate preview URL using the API proxy instead of direct localhost
        payload["previewUrl"] = get_absolute_preview_url(request, repo_name)
    return payload


def rewrite_html_preview_assets(html: str, proxy_prefix: str) -> str:
    """Keep common root-relative asset and form URLs inside the preview proxy."""
    if "<base " not in html.lower():
        html = re.sub(
            r"(?i)</head>",
            f'<base href="{proxy_prefix}/"></head>',
            html,
            count=1,
        )

    replacements = (
        ('href="/', f'href="{proxy_prefix}/'),
        ('src="/', f'src="{proxy_prefix}/'),
        ('action="/', f'action="{proxy_prefix}/'),
        ("href='/", f"href='{proxy_prefix}/"),
        ("src='/", f"src='{proxy_prefix}/"),
        ("action='/", f"action='{proxy_prefix}/"),
        ("url(/", f"url({proxy_prefix}/"),
    )
    for old, new in replacements:
        html = html.replace(old, new)
    return html

def get_reports_dir():
    reports = app_config.workspace_directory / "reports"
    reports.mkdir(exist_ok=True)
    return reports

def save_report_to_file(filename: str, data: dict):
    file_path = get_reports_dir() / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_report_from_file(filename: str) -> dict:
    file_path = get_reports_dir() / filename
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

@router.get("/status")
async def get_status():
    return {
        "ragInitialized": rag_service.is_initialized,
        "ragMessage": rag_service.initialization_status,
        "provider": app_config.ai_provider
    }

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalyzeRequest):
    if request.provider:
        app_config.ai_provider = request.provider
        
    response = analysis_service.analyze_repository(request.repoUrl, request.apiKey, request.modelName)
    save_report_to_file("last_analysis.json", response.model_dump())
    return response

@router.post("/migrate", response_model=TaskResponse)
async def migrate(request: MigrateRequest):
    if request.provider:
        app_config.ai_provider = request.provider
        
    task = run_background_migration.delay(
        request.repoUrl, 
        request.targetVersion,
        request.apiKey,
        request.modelName,
        request.provider
    )
    return TaskResponse(task_id=task.id, status="PENDING")

@router.get("/migrate/status/{task_id}")
async def migrate_status(task_id: str):
    task_result = AsyncResult(task_id)
    if task_result.state == 'PENDING':
        return {"status": "PENDING"}
    elif task_result.state == 'SUCCESS':
        result = task_result.result
        save_report_to_file("last_migration.json", result)
        return {"status": "SUCCESS", "result": result}
    elif task_result.state == 'FAILURE':
        return {"status": "FAILURE", "error": str(task_result.info)}
    else:
        return {"status": task_result.state}

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if request.provider:
        app_config.ai_provider = request.provider
        
    try:
        retrieved_docs = rag_service.search(request.message)
        
        rag_context = "System Knowledge Base Context:\n"
        for doc in retrieved_docs:
            rag_context += f"- Source: {doc['source']}\n{doc['content']}\n\n"
            
        reports_dir = get_reports_dir()
        last_analysis = reports_dir / "last_analysis.json"
        if last_analysis.exists():
            with open(last_analysis, "r", encoding="utf-8") as f:
                data = json.load(f)
                rag_context += "=== Current Repository Context ===\n"
                rag_context += f"- Project Name: {data.get('projectType')}\n"
                rag_context += f"- Java Version: {data.get('detectedJavaVersion')}\n"
                rag_context += f"- Frameworks: {data.get('frameworkVersions')}\n"
                rag_context += f"- Dependencies: {data.get('dependencies')}\n\n"
                
        last_migration = reports_dir / "last_migration.json"
        if last_migration.exists():
            with open(last_migration, "r", encoding="utf-8") as f:
                data = json.load(f)
                rag_context += "=== Current Migration Summary ===\n"
                rag_context += f"- Target Java Version: {data.get('targetVersion')}\n"
                rag_context += f"- Build Status: {data.get('buildStatus')}\n"
                rag_context += f"- Modified Files Count: {len(data.get('modifiedFiles', []))}\n\n"

        system_instruction = (
            "You are a highly helpful and expert assistant for the Java Migration Center. "
            "Always answer the user's questions accurately and directly. "
            "If the question is about the repository, migration, or Java technical details, "
            "leverage the provided context (System Knowledge Base Context, Current Repository Context, and Current Migration Summary). "
            "If the question is general or unrelated to Java migration, "
            "answer it fully using your own general knowledge, keeping the tone polite, helpful, and professional. "
            "Provide concise, accurate, and markdown-formatted answers."
        )

        user_prompt = f"{rag_context}\nUser Question: {request.message}"
        
        ai_client = AIFactory.get_client()
        answer = ai_client.generate(user_prompt, system_instruction, request.apiKey, request.modelName)
        
        return ChatResponse(response=answer)
    except Exception as e:
        return ChatResponse(errorMessage=str(e))

@router.post("/convert", response_model=ConversionResponse)
async def convert(request: ConvertRequest):
    if request.provider:
        app_config.ai_provider = request.provider
        
    response = code_conversion_service.convert_files(request.files, request.apiKey, request.modelName)
    if response.success:
        save_report_to_file("last_conversion.json", response.model_dump())
    return response

@router.get("/report/migration")
async def report_migration():
    try:
        migration_data = load_report_from_file("last_migration.json")
        if not migration_data:
            return JSONResponse(status_code=404, content={"error": "No migration report found. Please run a migration first."})
        
        response_obj = MigrationResponse(**migration_data)
        pdf_bytes = report_service.generate_migration_pdf(response_obj)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=JavaMigrationReports.pdf"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/report/conversion")
async def report_conversion():
    try:
        conversion_data = load_report_from_file("last_conversion.json")
        if not conversion_data:
            return JSONResponse(status_code=404, content={"error": "No conversion report found. Please run a code conversion first."})
        
        response_obj = ConversionResponse(**conversion_data)
        pdf_bytes = report_service.generate_conversion_pdf(response_obj)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=JavaConversionReports.pdf"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/download/python")
async def download_python():
    try:
        reports_dir = get_reports_dir()
        conversion_file = reports_dir / "last_conversion.json"
        
        if not conversion_file.exists():
            return JSONResponse(status_code=400, content={"error": "No converted code found."})
            
        with open(conversion_file, "r", encoding="utf-8") as f:
            conversion_data = json.load(f)
            # Create a mock ConversionResponse from the dict
            converted_files = [ConvertedFile(**cf) for cf in conversion_data.get("convertedFiles", [])]
            
        analysis_data = None
        analysis_file = reports_dir / "last_analysis.json"
        if analysis_file.exists():
            with open(analysis_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                analysis_data = AnalysisResponse(**data)
                
        zip_bytes = code_conversion_service.package_python_zip(converted_files, analysis_data)
        
        return Response(
            content=zip_bytes,
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=python_converted_files.zip"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/repository/{repo_name}/tree")
async def get_repository_tree(repo_name: str):
    project_dir = app_config.workspace_directory / repo_name
    if not project_dir.exists():
        return JSONResponse(status_code=404, content={"error": "Repository not found in workspace"})

    def build_tree(dir_path):
        tree = []
        try:
            for entry in sorted(os.scandir(dir_path), key=lambda e: (not e.is_dir(), e.name)):
                if entry.name in [".git", "target", "node_modules", ".idea", ".vscode"]:
                    continue
                item = {"name": entry.name, "path": str(Path(entry.path).relative_to(project_dir)).replace("\\", "/")}
                if entry.is_dir():
                    item["type"] = "folder"
                    item["children"] = build_tree(entry.path)
                else:
                    item["type"] = "file"
                tree.append(item)
        except Exception:
            pass
        return tree

    return {"name": repo_name, "type": "folder", "children": build_tree(project_dir), "path": ""}

@router.get("/repository/{repo_name}/file")
async def get_repository_file(repo_name: str, file_path: str, version: str = "new"):
    project_dir = app_config.workspace_directory / repo_name
    if not project_dir.exists():
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    full_path = project_dir / file_path
    
    if version == "new":
        if not full_path.exists():
            return JSONResponse(status_code=404, content={"error": "File not found"})
        try:
            content = full_path.read_text(encoding='utf-8', errors='replace')
            return {"content": content}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Error reading file: {e}"})
    elif version == "old":
        import subprocess
        try:
            # We use git show HEAD:{file_path} to get the old version.
            # Convert Windows paths to Git paths if necessary
            git_path = file_path.replace("\\", "/")
            content = subprocess.check_output(
                ["git", "show", f"HEAD:{git_path}"],
                cwd=str(project_dir),
                text=True,
                errors='replace'
            )
            return {"content": content}
        except subprocess.CalledProcessError:
            # If the file didn't exist in the old commit, or git show fails
            return {"content": "// File not found in original repository (may be newly created)"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Error reading old file: {e}"})
    else:
        return JSONResponse(status_code=400, content={"error": "Invalid version specified"})

# Execution Module
execution_log_queues = {}
execution_logs_history = {}
execution_results = {}

@router.post("/repository/{repo_name}/run/{version}")
async def run_repository(repo_name: str, version: str):
    key = f"{repo_name}_{version}"
    execution_log_queues[key] = []
    execution_logs_history[key] = []
    execution_results[key] = {
        "repository": repo_name,
        "version": version,
        "buildStatus": "Pending",
        "startupStatus": "Pending",
        "testStatus": "Pending"
    }

    async def bg_execute():
        def on_log(line: str):
            execution_logs_history[key].append(line)
            # Send to all connected queues
            for q in execution_log_queues.get(key, []):
                q.put_nowait(line)
                
        result = await execution_service.execute_repository(repo_name, version, on_log)
        result["logs"] = "".join(execution_logs_history[key])
        execution_results[key] = result
        
        # Send EOF
        for q in execution_log_queues.get(key, []):
            q.put_nowait(None)

    asyncio.create_task(bg_execute())
    return {"status": "started", "key": key}

@router.get("/repository/{repo_name}/execution-status/{version}")
async def get_execution_status(repo_name: str, version: str):
    key = f"{repo_name}_{version}"
    if key in execution_results:
        return execution_results[key]
    return {"status": "Not Found"}

@router.get("/repository/{repo_name}/logs/{version}")
async def get_execution_logs(repo_name: str, version: str):
    key = f"{repo_name}_{version}"
    if key in execution_logs_history:
        return {"logs": "".join(execution_logs_history[key])}
    return {"logs": ""}

@router.websocket("/ws/repository/{repo_name}/logs/{version}")
async def execution_logs_ws(websocket: WebSocket, repo_name: str, version: str):
    await websocket.accept()
    key = f"{repo_name}_{version}"
    
    # Send history first
    if key in execution_logs_history:
        for line in execution_logs_history[key]:
            await websocket.send_text(line)
            
    # Then stream live logs
    if key in execution_results and execution_results[key].get("buildStatus") == "Pending":
        queue = asyncio.Queue()
        if key not in execution_log_queues:
            execution_log_queues[key] = []
        execution_log_queues[key].append(queue)
        
        try:
            while True:
                line = await queue.get()
                if line is None:
                    break
                await websocket.send_text(line)
        except WebSocketDisconnect:
            pass
        finally:
            if queue in execution_log_queues.get(key, []):
                execution_log_queues[key].remove(queue)
    else:
        # Execution already finished
        pass
    
    try:
        await websocket.close()
    except Exception:
        pass

# Project Runner Module
from app.services.project_runner_service import project_runner_service

@router.post("/run/start", response_model=RunStatusResponse)
async def start_project(request: RunStartRequest, http_request: Request):
    await project_runner_service.start_project(request.repoName)
    return attach_preview_url(project_runner_service.get_status(request.repoName), http_request, request.repoName)

@router.post("/run/stop", response_model=RunStatusResponse)
async def stop_project(request: RunStartRequest, http_request: Request):
    await project_runner_service.stop_project(request.repoName)
    return attach_preview_url(project_runner_service.get_status(request.repoName), http_request, request.repoName)

@router.get("/run/status/{repo_name}", response_model=RunStatusResponse)
async def get_project_status(repo_name: str, http_request: Request):
    return attach_preview_url(project_runner_service.get_status(repo_name), http_request, repo_name)

@router.get("/run/logs/{repo_name}")
async def get_project_logs(repo_name: str):
    return {"logs": project_runner_service.get_logs(repo_name)}


async def _close_preview_stream(response: httpx.Response, client: httpx.AsyncClient):
    await response.aclose()
    await client.aclose()


async def _proxy_preview_request(repo_name: str, request: Request, path: str = ""):
    status = project_runner_service.get_status(repo_name)
    port = status.get("port")
    if not port:
        return JSONResponse(status_code=404, content={"error": "Preview server is not running"})

    target_base_url = f"http://127.0.0.1:{port}"
    proxy_prefix = f"{PREVIEW_PROXY_PREFIX}/{repo_name}"
    target_path = f"/{path.lstrip('/')}" if path else "/"

    forward_headers = {}
    for key, value in request.headers.items():
        if key.lower() not in {"host", "content-length"}:
            forward_headers[key] = value

    client = httpx.AsyncClient(base_url=target_base_url, follow_redirects=False)
    upstream_request = client.build_request(
        request.method,
        target_path,
        headers=forward_headers,
        content=request.stream(),
    )

    try:
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.ConnectError:
        await client.aclose()
        return JSONResponse(status_code=502, content={"error": "Preview server is not reachable"})

    headers = dict(upstream_response.headers)
    headers.pop("x-frame-options", None)
    headers.pop("content-security-policy", None)
    headers.pop("transfer-encoding", None)
    headers.pop("content-encoding", None)

    location = upstream_response.headers.get("location")
    if location:
        resolved_location = urljoin(f"{target_base_url}/", location)
        parsed_location = urlsplit(resolved_location)
        if parsed_location.hostname in {"127.0.0.1", "localhost"} and parsed_location.port == port:
            rewritten_path = parsed_location.path or "/"
            if not rewritten_path.startswith("/"):
                rewritten_path = f"/{rewritten_path}"
            rewritten_location = f"{proxy_prefix}{rewritten_path}"
            if parsed_location.query:
                rewritten_location = f"{rewritten_location}?{parsed_location.query}"
            headers["location"] = rewritten_location

    content_type = upstream_response.headers.get("content-type", "").lower()
    if "text/html" in content_type:
        body = await upstream_response.aread()
        encoding = upstream_response.encoding or "utf-8"
        html = body.decode(encoding, errors="replace")
        html = rewrite_html_preview_assets(html, proxy_prefix)
        headers.pop("content-length", None)
        return Response(
            content=html,
            status_code=upstream_response.status_code,
            headers=headers,
            media_type=upstream_response.headers.get("content-type"),
        )

    return StreamingResponse(
        upstream_response.aiter_raw(),
        status_code=upstream_response.status_code,
        headers=headers,
        background=BackgroundTask(_close_preview_stream, upstream_response, client),
    )


@router.api_route("/run/preview/{repo_name}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def preview_root(repo_name: str, request: Request):
    return await _proxy_preview_request(repo_name, request)


@router.api_route("/run/preview/{repo_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def preview_path(repo_name: str, path: str, request: Request):
    return await _proxy_preview_request(repo_name, request, path)

@router.websocket("/ws/run/logs/{repo_name}")
async def run_project_logs_ws(websocket: WebSocket, repo_name: str):
    await websocket.accept()
    
    # Send historical logs first
    logs = project_runner_service.get_logs(repo_name)
    if logs:
        await websocket.send_text(logs)
        
    # Register queue to stream live logs
    queue = asyncio.Queue()
    if repo_name not in project_runner_service.log_queues:
        project_runner_service.log_queues[repo_name] = []
    project_runner_service.log_queues[repo_name].append(queue)
    
    try:
        while True:
            line = await queue.get()
            if line is None:  # EOF signal
                break
            await websocket.send_text(line)
    except WebSocketDisconnect:
        pass
    finally:
        if repo_name in project_runner_service.log_queues and queue in project_runner_service.log_queues[repo_name]:
            project_runner_service.log_queues[repo_name].remove(queue)
        try:
            await websocket.close()
        except Exception:
            pass
