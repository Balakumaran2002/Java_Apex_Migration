import contextlib
import contextvars
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.config import app_config


class LLMRuntimeService:
    def __init__(self):
        self.state_file = app_config.workspace_directory / "llm_runtime_state.json"
        self.chunk_cache_file = app_config.workspace_directory / "analysis_chunk_cache.json"
        self.resume_file = app_config.workspace_directory / "analysis_resume.json"
        self._lock = threading.Lock()
        self._current_job_id = contextvars.ContextVar("llm_current_job_id", default=None)
        self._ensure_files()

    def _ensure_files(self) -> None:
        for path, initial in (
            (self.state_file, {"providers": {}, "current_job": {}}),
            (self.chunk_cache_file, {}),
            (self.resume_file, {}),
        ):
            if not path.exists():
                path.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def _read_json(self, path: Path, fallback):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return fallback

    def _write_json(self, path: Path, data) -> None:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        rough = max(1, len(text) // 4)
        words = max(1, len(text.split()))
        return max(rough, int(words * 1.3))

    def get_model_limits(self, provider: str, model_name: Optional[str]) -> Dict[str, int]:
        active_model = (model_name or "").lower()
        context_limit = 8192
        daily_limit = int(os.getenv("LLM_DAILY_TOKEN_LIMIT", "900000"))

        if provider == "groq":
            context_limit = int(os.getenv("GROQ_CONTEXT_LIMIT", "8192"))
            daily_limit = int(os.getenv("GROQ_DAILY_TOKEN_LIMIT", str(daily_limit)))
            if "70b-versatile" in active_model:
                context_limit = int(os.getenv("GROQ_CONTEXT_LIMIT_LLAMA_70B", "8192"))
        elif provider == "openai":
            context_limit = int(os.getenv("OPENAI_CONTEXT_LIMIT", "128000"))
            daily_limit = int(os.getenv("OPENAI_DAILY_TOKEN_LIMIT", str(daily_limit)))
        elif provider == "gemini":
            context_limit = int(os.getenv("GEMINI_CONTEXT_LIMIT", "1000000"))
            daily_limit = int(os.getenv("GEMINI_DAILY_TOKEN_LIMIT", str(daily_limit)))

        min_chunk = int(os.getenv("LLM_MIN_CHUNK_TOKENS", "500"))
        max_chunk = int(os.getenv("LLM_MAX_CHUNK_TOKENS", "1500"))
        default_chunk = int(os.getenv("LLM_DEFAULT_CHUNK_TOKENS", "900"))
        safe_context = max(min_chunk * 2, int(context_limit * 0.6))
        return {
            "context_limit": context_limit,
            "daily_limit": daily_limit,
            "min_chunk_tokens": min_chunk,
            "max_chunk_tokens": max_chunk,
            "default_chunk_tokens": max(min_chunk, min(default_chunk, max_chunk)),
            "safe_context_tokens": safe_context,
            "reserve_tokens": int(os.getenv("LLM_RESERVE_TOKENS", "5000")),
            "chunk_overlap_tokens": int(os.getenv("LLM_CHUNK_OVERLAP_TOKENS", "120")),
            "chunk_concurrency": int(os.getenv("LLM_CHUNK_CONCURRENCY", "1")),
        }

    def get_recommended_chunk_size(self, provider: str, model_name: Optional[str]) -> int:
        limits = self.get_model_limits(provider, model_name)
        state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
        provider_state = state.get("providers", {}).get(provider, {})
        hints = provider_state.get("chunk_size_hints", {})
        hint_key = model_name or "default"
        hinted = hints.get(hint_key, limits["default_chunk_tokens"])
        return max(limits["min_chunk_tokens"], min(hinted, limits["max_chunk_tokens"]))

    def record_rate_limit(self, provider: str, model_name: Optional[str]) -> int:
        with self._lock:
            state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
            provider_state = state.setdefault("providers", {}).setdefault(provider, {})
            hints = provider_state.setdefault("chunk_size_hints", {})
            limits = self.get_model_limits(provider, model_name)
            hint_key = model_name or "default"
            current = hints.get(hint_key, limits["default_chunk_tokens"])
            reduced = max(limits["min_chunk_tokens"], int(current * 0.75))
            hints[hint_key] = reduced
            self._write_json(self.state_file, state)
            return reduced

    def record_success(self, provider: str, model_name: Optional[str]) -> int:
        with self._lock:
            state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
            provider_state = state.setdefault("providers", {}).setdefault(provider, {})
            hints = provider_state.setdefault("chunk_size_hints", {})
            limits = self.get_model_limits(provider, model_name)
            hint_key = model_name or "default"
            current = hints.get(hint_key, limits["default_chunk_tokens"])
            grown = min(limits["max_chunk_tokens"], current + 50)
            hints[hint_key] = grown
            self._write_json(self.state_file, state)
            return grown

    def chunk_text(self, text: str, target_tokens: int, overlap_tokens: int = 120) -> List[str]:
        if self.estimate_tokens(text) <= target_tokens:
            return [text]

        lines = text.splitlines()
        chunks = []
        current_lines: List[str] = []
        current_tokens = 0
        overlap_lines: List[str] = []

        def finalize_chunk():
            nonlocal overlap_lines
            chunk_text = "\n".join(current_lines).strip()
            if chunk_text:
                chunks.append(chunk_text)
                overlap_lines = self._tail_lines_for_overlap(current_lines, overlap_tokens)

        for line in lines:
            line_tokens = self.estimate_tokens(line + "\n")
            if current_lines and current_tokens + line_tokens > target_tokens:
                finalize_chunk()
                current_lines = overlap_lines.copy()
                current_tokens = self.estimate_tokens("\n".join(current_lines))
            current_lines.append(line)
            current_tokens += line_tokens

        if current_lines:
            finalize_chunk()
        return chunks or [text]

    def _tail_lines_for_overlap(self, lines: List[str], overlap_tokens: int) -> List[str]:
        if not lines:
            return []
        collected: List[str] = []
        total = 0
        for line in reversed(lines):
            line_tokens = self.estimate_tokens(line + "\n")
            if collected and total + line_tokens > overlap_tokens:
                break
            collected.append(line)
            total += line_tokens
        return list(reversed(collected))

    def hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    def with_job(self, job_id: str, label: str):
        @contextlib.contextmanager
        def manager():
            token = self._current_job_id.set(job_id)
            self.start_job(job_id, label)
            try:
                yield
            finally:
                self.finish_job(job_id)
                self._current_job_id.reset(token)

        return manager()

    def start_job(self, job_id: str, label: str, total_chunks: int = 0) -> None:
        with self._lock:
            state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
            state["current_job"] = {
                "jobId": job_id,
                "label": label,
                "status": "running",
                "message": label,
                "currentChunk": 0,
                "totalChunks": total_chunks,
                "startedAt": time.time(),
                "updatedAt": time.time(),
            }
            self._write_json(self.state_file, state)

    def update_job_progress(
        self,
        current_chunk: Optional[int] = None,
        total_chunks: Optional[int] = None,
        message: Optional[str] = None,
        status: str = "running",
        job_id: Optional[str] = None,
    ) -> None:
        active_job_id = job_id or self._current_job_id.get()
        if not active_job_id:
            return
        with self._lock:
            state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
            current_job = state.get("current_job", {})
            if current_job.get("jobId") != active_job_id:
                current_job = {"jobId": active_job_id}
            current_job["status"] = status
            if current_chunk is not None:
                current_job["currentChunk"] = current_chunk
            if total_chunks is not None:
                current_job["totalChunks"] = total_chunks
            if message:
                current_job["message"] = message
            current_job["updatedAt"] = time.time()
            state["current_job"] = current_job
            self._write_json(self.state_file, state)

    def finish_job(self, job_id: Optional[str] = None) -> None:
        active_job_id = job_id or self._current_job_id.get()
        if not active_job_id:
            return
        with self._lock:
            state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
            current_job = state.get("current_job", {})
            if current_job.get("jobId") == active_job_id:
                current_job["status"] = "idle"
                current_job["message"] = "Idle"
                current_job["updatedAt"] = time.time()
                state["current_job"] = current_job
                self._write_json(self.state_file, state)

    def update_quota(
        self,
        provider: str,
        key_id: str,
        key_name: str,
        input_tokens: int,
        output_tokens: int,
        daily_limit: int,
        reset_at: Optional[float],
    ) -> None:
        with self._lock:
            state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
            provider_state = state.setdefault("providers", {}).setdefault(provider, {})
            key_state = provider_state.setdefault("keys", {}).setdefault(key_id, {"keyName": key_name})

            now = time.time()
            previous_reset = key_state.get("resetAt")
            if previous_reset and now >= previous_reset:
                key_state["inputTokens"] = 0
                key_state["outputTokens"] = 0
                key_state["totalTokens"] = 0

            key_state["keyName"] = key_name
            key_state["inputTokens"] = key_state.get("inputTokens", 0) + input_tokens
            key_state["outputTokens"] = key_state.get("outputTokens", 0) + output_tokens
            key_state["totalTokens"] = key_state.get("totalTokens", 0) + input_tokens + output_tokens
            key_state["dailyLimit"] = daily_limit
            key_state["remainingTokens"] = max(0, daily_limit - key_state["totalTokens"])
            key_state["resetAt"] = reset_at or self._next_reset_time()
            key_state["updatedAt"] = now
            provider_state["updatedAt"] = now
            self._write_json(self.state_file, state)

    def get_key_quota(self, provider: str, key_id: str, key_name: str, daily_limit: int) -> Dict:
        state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
        provider_state = state.get("providers", {}).get(provider, {})
        key_state = provider_state.get("keys", {}).get(key_id, {})
        reset_at = key_state.get("resetAt") or self._next_reset_time()
        if time.time() >= reset_at:
            return {
                "keyName": key_name,
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
                "dailyLimit": daily_limit,
                "remainingTokens": daily_limit,
                "resetAt": reset_at,
            }
        return {
            "keyName": key_name,
            "inputTokens": key_state.get("inputTokens", 0),
            "outputTokens": key_state.get("outputTokens", 0),
            "totalTokens": key_state.get("totalTokens", 0),
            "dailyLimit": key_state.get("dailyLimit", daily_limit),
            "remainingTokens": key_state.get("remainingTokens", daily_limit),
            "resetAt": reset_at,
        }

    def get_status(self) -> Dict:
        state = self._read_json(self.state_file, {"providers": {}, "current_job": {}})
        current_job = state.get("current_job", {}) or {}
        return {
            "currentJob": current_job,
            "providers": state.get("providers", {}),
        }

    def get_chunk_cache(self) -> Dict:
        return self._read_json(self.chunk_cache_file, {})

    def save_chunk_cache(self, cache: Dict) -> None:
        with self._lock:
            self._write_json(self.chunk_cache_file, cache)

    def get_resume_state(self) -> Dict:
        return self._read_json(self.resume_file, {})

    def save_resume_state(self, state: Dict) -> None:
        with self._lock:
            self._write_json(self.resume_file, state)

    def _next_reset_time(self) -> float:
        now = time.time()
        local = time.localtime(now)
        midnight = time.mktime(
            (
                local.tm_year,
                local.tm_mon,
                local.tm_mday + 1,
                0,
                0,
                0,
                0,
                0,
                -1,
            )
        )
        return midnight


llm_runtime_service = LLMRuntimeService()
