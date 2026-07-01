"""
provider_manager.py
===================
Centralized AI Provider Manager for APEX Migration.

Responsibilities:
- Delegate API Key rotation and selection to ApiKeyManager
- Support Groq, OpenAI, Gemini
- Token usage accounting
- Exponential backoff on 429 / rate limits
"""

import logging
import importlib
import time
import threading
from typing import Optional

from app.services.llm_runtime_service import llm_runtime_service
from app.ai.api_key_manager import api_key_manager

logger = logging.getLogger("provider_manager")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

FAILOVER_EXCEPTIONS = (
    "TokenExhaustedError",
    "RateLimitError",
    "APIConnectionError",
    "APITimeoutError",
    "ServiceUnavailableError",
)
FAILOVER_HTTP_CODES = {400, 401, 403, 408, 429, 500, 502, 503, 504}


class NoAvailableAIKeyError(RuntimeError):
    pass


def _is_failover_error(exc: Exception) -> tuple[bool, int, str]:
    exc_type = type(exc).__name__
    hard_cooldown = 1800
    
    for attr in ("status_code", "code", "status"):
        code = getattr(exc, attr, None)
        if code:
            code_int = int(code)
            if code_int == 429:
                return True, hard_cooldown, "rate_limit"
            if code_int in (401, 403):
                return True, hard_cooldown, "invalid"
            if code_int in FAILOVER_HTTP_CODES:
                return True, 60, "timeout"
                
    if exc_type in FAILOVER_EXCEPTIONS:
        if "RateLimit" in exc_type or "TokenExhausted" in exc_type:
            return True, hard_cooldown, "rate_limit"
        return True, 60, "timeout"
        
    msg = str(exc).lower()
    if any(kw in msg for kw in ["rate limit", "quota", "exhausted", "too many requests"]):
        return True, hard_cooldown, "rate_limit"
    if any(kw in msg for kw in ["unauthorized", "forbidden", "invalid api key"]):
        return True, hard_cooldown, "invalid"
    keywords = ["expired", "timeout", "connection", "unavailable", "overloaded", "authentication"]
    if any(kw in msg for kw in keywords):
        return True, 60, "timeout"
        
    return False, 0, "unknown"


def _scrub_api_key(error_msg: str) -> str:
    import re
    return re.sub(r"(?i)(bearer\s+|key[=\s:]+)?([a-z0-9_-]{20,})", r"\1[REDACTED]", error_msg)


def _usage_value(usage_obj, *names) -> int:
    if not usage_obj:
        return 0
    for name in names:
        value = getattr(usage_obj, name, None)
        if value is not None:
            return int(value)
        if isinstance(usage_obj, dict) and name in usage_obj:
            return int(usage_obj[name])
    return 0


class ProviderManager:
    def __init__(self):
        self._factories = {
            "groq": ("app.ai.groq_client", "GroqClient"),
            "openai": ("app.ai.openai_client", "OpenAIClient"),
            "gemini": ("app.ai.gemini_client", "GeminiClient"),
        }
        self.last_provider_used: str = ""
        self._model_fallbacks = {
            # Groq model
            "llama-3.3-70b-versatile": {
                "gemini": "gemini-2.5-flash",
                "openai": "gpt-4o-mini"
            },
            # Generic fallbacks
            "default": {
                "groq": "llama-3.3-70b-versatile",
                "gemini": "gemini-2.5-flash",
                "openai": "gpt-4o-mini"
            }
        }

    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        result = self.generate_with_metadata(prompt, system_instruction, api_key, model_name)
        return result["content"]

    def _get_fallback_model(self, original_model: str, target_provider: str) -> str:
        # Check specific fallbacks first
        if original_model in self._model_fallbacks and target_provider in self._model_fallbacks[original_model]:
            return self._model_fallbacks[original_model][target_provider]
            
        # Check generic fallbacks based on target provider if the original model isn't from the target provider
        return self._model_fallbacks["default"].get(target_provider, original_model)

    def generate_with_metadata(
        self,
        prompt: str,
        system_instruction: str = None,
        api_key: str = None,
        model_name: str = None,
    ) -> dict:
        import os
        from app.config import app_config
        from app.ai.request_scheduler import request_scheduler
        
        original_model = model_name or os.getenv(f"{app_config.ai_provider.upper()}_MODEL_NAME") or "llama-3.3-70b-versatile"
        estimated_input_tokens = llm_runtime_service.estimate_tokens((system_instruction or "") + "\n" + prompt)
        
        try:
            initial_provider, _ = api_key_manager.get_active_provider_and_key()
        except RuntimeError:
            initial_provider = "groq"
            
        current_model = self._get_fallback_model(original_model, initial_provider)
        
        def execute_llm(kid: str, kval: str) -> dict:
            active_provider, _ = api_key_manager.get_active_provider_and_key()
            active_model = self._get_fallback_model(original_model, active_provider)
            
            if active_provider not in self._factories:
                raise ValueError(f"Provider {active_provider} is not supported.")
                
            factory = self._load_factory(active_provider)
            client = factory()
            
            logger.info(f"[{active_provider.upper()}] Executing with key: {kid} using model: {active_model}")
            llm_runtime_service.update_job_progress(message=f"Using {active_provider} key '{kid}'")
            
            response = client.generate_with_metadata(prompt, system_instruction, kval, active_model)
            usage = self._normalize_usage(response.get("usage"), estimated_input_tokens, response.get("content", ""))
            
            # Update quota history
            limits = llm_runtime_service.get_model_limits(active_provider, active_model)
            llm_runtime_service.update_quota(
                active_provider,
                kid,
                kid,
                usage["input_tokens"],
                usage["output_tokens"],
                limits["daily_limit"],
                llm_runtime_service._next_reset_time(),
            )
            
            self.last_provider_used = active_provider
            llm_runtime_service.record_success(active_provider, active_model)
            
            return {
                "content": response.get("content", ""),
                "usage": usage,
                "model": response.get("model", active_model),
                "provider": active_provider,
                "keyName": kid,
            }
            
        return request_scheduler.execute(initial_provider, current_model, execute_llm)

    def _normalize_usage(self, usage_obj, estimated_input_tokens: int, content: str) -> dict:
        prompt_tokens = _usage_value(usage_obj, "prompt_tokens", "input_tokens", "prompt_token_count")
        completion_tokens = _usage_value(usage_obj, "completion_tokens", "output_tokens", "candidates_token_count")
        total_tokens = _usage_value(usage_obj, "total_tokens", "total_token_count")

        if not prompt_tokens:
            prompt_tokens = estimated_input_tokens
        if not completion_tokens:
            completion_tokens = llm_runtime_service.estimate_tokens(content)
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens

        return {
            "input_tokens": int(prompt_tokens),
            "output_tokens": int(completion_tokens),
            "total_tokens": int(total_tokens),
        }

    def _load_factory(self, provider_name: str):
        module_name, class_name = self._factories[provider_name]
        module = importlib.import_module(module_name)
        return getattr(module, class_name)


_provider_manager_instance: Optional[ProviderManager] = None
_init_lock = threading.Lock()


def get_provider_manager() -> ProviderManager:
    global _provider_manager_instance
    if _provider_manager_instance is None:
        with _init_lock:
            if _provider_manager_instance is None:
                _provider_manager_instance = ProviderManager()
    return _provider_manager_instance
