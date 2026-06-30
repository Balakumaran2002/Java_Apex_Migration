"""
provider_manager.py
===================
Centralized AI Provider Manager for APEX Migration.

Responsibilities:
- Support Groq, OpenAI, Gemini via KeyManagerService
- Automatic API Key rotation
- Token usage accounting and quota-aware waiting
- Exponential backoff on 429 / rate limits
"""

import logging
import os
import random
import threading
import time
import importlib
from dataclasses import dataclass
from typing import Dict, Optional

from app.services.key_manager_service import key_manager_service
from app.services.llm_runtime_service import llm_runtime_service

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


def _is_failover_error(exc: Exception) -> tuple[bool, int, bool]:
    exc_type = type(exc).__name__
    hard_cooldown = 1800
    is_rate_limit = False
    for attr in ("status_code", "code", "status"):
        code = getattr(exc, attr, None)
        if code:
            code_int = int(code)
            if code_int == 429:
                return True, hard_cooldown, True
            if code_int in (401, 403):
                return True, hard_cooldown, False
            if code_int in FAILOVER_HTTP_CODES:
                return True, 0, False
    if exc_type in FAILOVER_EXCEPTIONS:
        is_rate_limit = "RateLimit" in exc_type or "TokenExhausted" in exc_type
        return True, hard_cooldown if is_rate_limit else 0, is_rate_limit
    msg = str(exc).lower()
    if any(kw in msg for kw in ["rate limit", "quota", "exhausted", "too many requests"]):
        return True, hard_cooldown, True
    if any(kw in msg for kw in ["unauthorized", "forbidden", "invalid api key"]):
        return True, hard_cooldown, False
    keywords = ["expired", "timeout", "connection", "unavailable", "overloaded", "authentication"]
    if any(kw in msg for kw in keywords):
        return True, 0, False
    return False, 0, False


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


@dataclass
class KeyHealth:
    key_id: str
    cooldown_until: float = 0.0
    failures: int = 0

    @property
    def is_on_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def record_failure(self, penalty_seconds: int = 0):
        self.failures += 1
        backoff = penalty_seconds if penalty_seconds > 0 else min(60 * (2 ** min(self.failures - 1, 4)), 1800)
        self.cooldown_until = time.time() + backoff


class ProviderManager:
    def __init__(self):
        self._factories = {
            "groq": ("app.ai.groq_client", "GroqClient"),
            "openai": ("app.ai.openai_client", "OpenAIClient"),
            "gemini": ("app.ai.gemini_client", "GeminiClient"),
        }
        self._health: Dict[str, KeyHealth] = {}
        self._lock = threading.Lock()
        self.last_provider_used: str = ""

    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        result = self.generate_with_metadata(prompt, system_instruction, api_key, model_name)
        return result["content"]

    def generate_with_metadata(
        self,
        prompt: str,
        system_instruction: str = None,
        api_key: str = None,
        model_name: str = None,
    ) -> dict:
        provider_name = key_manager_service.get_active_provider()
        if provider_name not in self._factories:
            raise ValueError(f"Provider {provider_name} is not supported.")

        factory = self._load_factory(provider_name)
        limits = llm_runtime_service.get_model_limits(provider_name, model_name)
        estimated_input_tokens = llm_runtime_service.estimate_tokens((system_instruction or "") + "\n" + prompt)
        llm_runtime_service.update_job_progress(message="Preparing AI request...")

        keys = key_manager_service.get_active_keys(provider_name)
        if not keys:
            logger.warning(f"No active API keys found for {provider_name} in database. Falling back to environment variables.")
            return self._generate_with_env_fallback(factory, provider_name, prompt, system_instruction, model_name, estimated_input_tokens)

        while True:
            available_keys = []
            next_reset_times = []
            with self._lock:
                for key_data in keys:
                    kid = key_data["id"]
                    if kid not in self._health:
                        self._health[kid] = KeyHealth(key_id=kid)
                    health = self._health[kid]
                    if health.is_on_cooldown:
                        next_reset_times.append(health.cooldown_until)
                        continue

                    quota = llm_runtime_service.get_key_quota(
                        provider_name,
                        kid,
                        key_data["name"],
                        limits["daily_limit"],
                    )
                    if quota["remainingTokens"] <= limits["reserve_tokens"]:
                        next_reset_times.append(quota["resetAt"])
                        continue
                    available_keys.append((key_data, quota))

            if not available_keys:
                llm_runtime_service.update_job_progress(
                    message=f"LLM fallback mode active: all {provider_name} keys are rate-limited or exhausted. Skipping AI rewrite for this file and continuing."
                )
                raise NoAvailableAIKeyError(f"All {provider_name} keys are rate-limited or exhausted.")

            for key_data, quota in available_keys:
                result = self._attempt_with_key(
                    factory,
                    provider_name,
                    key_data,
                    prompt,
                    system_instruction,
                    model_name,
                    estimated_input_tokens,
                    quota,
                    limits,
                )
                if result is not None:
                    return result

    def _generate_with_env_fallback(self, factory, provider_name: str, prompt: str, system_instruction: str, model_name: str, estimated_input_tokens: int) -> dict:
        client = factory()
        response = client.generate_with_metadata(prompt, system_instruction, None, model_name)
        usage = self._normalize_usage(response.get("usage"), estimated_input_tokens, response.get("content", ""))
        llm_runtime_service.update_quota(
            provider_name,
            "env",
            "Environment",
            usage["input_tokens"],
            usage["output_tokens"],
            llm_runtime_service.get_model_limits(provider_name, model_name)["daily_limit"],
            llm_runtime_service._next_reset_time(),
        )
        self.last_provider_used = provider_name
        llm_runtime_service.record_success(provider_name, model_name)
        return {
            "content": response.get("content", ""),
            "usage": usage,
            "model": response.get("model", model_name),
            "provider": provider_name,
            "keyName": "Environment",
        }

    def _attempt_with_key(
        self,
        factory,
        provider_name: str,
        key_data: dict,
        prompt: str,
        system_instruction: str,
        model_name: str,
        estimated_input_tokens: int,
        quota: dict,
        limits: dict,
    ) -> Optional[dict]:
        kid = key_data["id"]
        kval = key_data["key"]
        kname = key_data["name"]
        health = self._health[kid]

        logger.info(f"[{provider_name.upper()}] Attempting with key: {kname}")
        llm_runtime_service.update_job_progress(message=f"Using {provider_name} key '{kname}'")

        client = factory()
        try:
            response = client.generate_with_metadata(prompt, system_instruction, kval, model_name)
            usage = self._normalize_usage(response.get("usage"), estimated_input_tokens, response.get("content", ""))
            llm_runtime_service.update_quota(
                provider_name,
                kid,
                kname,
                usage["input_tokens"],
                usage["output_tokens"],
                quota["dailyLimit"],
                quota["resetAt"],
            )
            with self._lock:
                health.failures = 0
                health.cooldown_until = 0.0
            self.last_provider_used = provider_name
            llm_runtime_service.record_success(provider_name, model_name)
            return {
                "content": response.get("content", ""),
                "usage": usage,
                "model": response.get("model", model_name),
                "provider": provider_name,
                "keyName": kname,
            }
        except Exception as exc:
            is_failover, penalty, is_rate_limit = _is_failover_error(exc)
            if not is_failover:
                raise exc

            if is_rate_limit:
                reduced = llm_runtime_service.record_rate_limit(provider_name, model_name)
                llm_runtime_service.update_job_progress(
                    message=f"LLM fallback mode active: rate limit hit on {kname}. Switching immediately to the next active key (~{reduced} tokens recommended)."
                )
                with self._lock:
                    health.record_failure(penalty_seconds=max(15, penalty or 15))
                logger.warning(f"Key '{kname}' rate limited. Moving to the next key.")
                return None

            with self._lock:
                health.record_failure(penalty)
            logger.warning(f"Key '{kname}' failed. Reason: {_scrub_api_key(str(exc))[:120]}. Switching to next key.")
            return None

    def _wait_until_available(self, wait_until: float, provider_name: str) -> None:
        while True:
            remaining = max(1, int(wait_until - time.time()))
            if remaining <= 0:
                break
            llm_runtime_service.update_job_progress(
                message=f"All {provider_name} keys are exhausted. Rechecking in {remaining}s..."
            )
            time.sleep(min(remaining, 5))

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
