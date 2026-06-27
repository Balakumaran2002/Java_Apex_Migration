"""
provider_manager.py
===================
Centralized AI Provider Manager for APEX Migration.

Responsibilities:
- Support Groq, OpenAI, Gemini via KeyManagerService
- Automatic API Key rotation (failover to next key)
"""

import os
import time
import threading
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from app.services.key_manager_service import key_manager_service
from app.ai.groq_client import GroqClient
from app.ai.openai_client import OpenAIClient
from app.ai.gemini_client import GeminiClient

logger = logging.getLogger("provider_manager")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Error Classification
FAILOVER_EXCEPTIONS = (
    "TokenExhaustedError",
    "RateLimitError",
    "APIConnectionError",
    "APITimeoutError",
    "ServiceUnavailableError",
)
FAILOVER_HTTP_CODES = {400, 401, 403, 408, 429, 500, 502, 503, 504}

def _is_failover_error(exc: Exception) -> tuple[bool, int]:
    """Return (True, penalty_seconds) if this exception should trigger failover."""
    exc_type = type(exc).__name__
    HARD_COOLDOWN = 1800
    for attr in ("status_code", "code", "status"):
        code = getattr(exc, attr, None)
        if code:
            code_int = int(code)
            if code_int in (401, 403, 429):
                return True, HARD_COOLDOWN
            if code_int in FAILOVER_HTTP_CODES:
                return True, 0
    if exc_type in FAILOVER_EXCEPTIONS:
        return True, 0
    if "TokenExhausted" in exc_type:
        return True, HARD_COOLDOWN
    msg = str(exc).lower()
    if any(kw in msg for kw in ["rate limit", "quota", "exhausted", "unauthorized", "forbidden", "invalid api key", "too many requests"]):
        return True, HARD_COOLDOWN
    keywords = ["expired", "timeout", "connection", "unavailable", "overloaded", "authentication"]
    if any(kw in msg for kw in keywords):
        return True, 0
    return False, 0

def _scrub_api_key(error_msg: str) -> str:
    """Remove anything that looks like an API key or token from the error message."""
    import re
    return re.sub(r'(?i)(bearer\s+|key[=\s:]+)?([a-z0-9_-]{20,})', r'\1[REDACTED]', error_msg)

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
            "groq": GroqClient,
            "openai": OpenAIClient,
            "gemini": GeminiClient
        }
        self._health: Dict[str, KeyHealth] = {}
        self.last_provider_used: str = ""
        
    def generate(self, prompt: str, system_instruction: str = None, api_key: str = None, model_name: str = None) -> str:
        provider_name = key_manager_service.get_active_provider()
        if provider_name not in self._factories:
            raise ValueError(f"Provider {provider_name} is not supported.")
            
        factory = self._factories[provider_name]
        
        keys = key_manager_service.get_active_keys(provider_name)
        if not keys:
            # Fallback to env vars if no keys in DB
            logger.warning(f"No active API keys found for {provider_name} in database. Falling back to environment variables.")
            client = factory()
            try:
                self.last_provider_used = provider_name
                return client.generate(prompt, system_instruction, None, model_name)
            except Exception as e:
                raise RuntimeError(f"Fallback to env var failed. Please add API keys for {provider_name}. Error: {_scrub_api_key(str(e))}")

        last_exc: Optional[Exception] = None
        attempted = 0
        
        for k in keys:
            kid = k["id"]
            kval = k["key"]
            kname = k["name"]
            
            if kid not in self._health:
                self._health[kid] = KeyHealth(key_id=kid)
                
            health = self._health[kid]
            if health.is_on_cooldown:
                logger.debug(f"Skipping key '{kname}' - on cooldown for {health.cooldown_until - time.time():.0f}s")
                continue
                
            logger.info(f"[{provider_name.upper()}] Attempting with key: {kname}")
            attempted += 1
            
            try:
                client = factory()
                result = client.generate(prompt, system_instruction, kval, model_name)
                # Success -> reset failures
                health.failures = 0
                health.cooldown_until = 0.0
                self.last_provider_used = provider_name
                return result
            except Exception as exc:
                is_failover, penalty = _is_failover_error(exc)
                if is_failover:
                    health.record_failure(penalty)
                    last_exc = exc
                    logger.warning(f"Key '{kname}' failed. Reason: {_scrub_api_key(str(exc))[:100]}. Switching to next key.")
                    continue
                else:
                    raise exc
                    
        # Exhausted
        if attempted > 0:
            raise RuntimeError(f"All {attempted} active API keys for {provider_name} are rate-limited or unauthorized. Last error: {_scrub_api_key(str(last_exc))}")
        else:
            raise RuntimeError(f"All active API keys for {provider_name} are currently on cooldown. Please wait or add more keys.")

_provider_manager_instance: Optional[ProviderManager] = None
_init_lock = threading.Lock()

def get_provider_manager() -> ProviderManager:
    global _provider_manager_instance
    if _provider_manager_instance is None:
        with _init_lock:
            if _provider_manager_instance is None:
                _provider_manager_instance = ProviderManager()
    return _provider_manager_instance
