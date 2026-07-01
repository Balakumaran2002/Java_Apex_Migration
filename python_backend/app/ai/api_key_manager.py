import os
import re
import time
import threading
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from app.config import app_config

logger = logging.getLogger("api_key_manager")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

@dataclass
class ApiKeyInfo:
    key_id: str
    provider: str
    key_value: str
    status: str = "Healthy"  # Healthy, Rate Limited, Invalid
    cooldown_until: float = 0.0
    requests: int = 0
    failures: int = 0
    rotations: int = 0
    rate_limits: int = 0
    last_used: float = 0.0
    
    def mask_key(self) -> str:
        if not self.key_value:
            return ""
        if len(self.key_value) <= 8:
            return "***"
        return f"{self.key_value[:4]}...{self.key_value[-4:]}"

class ApiKeyManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._keys: List[ApiKeyInfo] = []
        self._current_index_by_provider: Dict[str, int] = {}
        self._provider_fallback_order = ["groq", "gemini", "openai"]
        
        # Load keys on startup
        self._load_keys()

    def _load_keys(self):
        with self._lock:
            # 1. Discover keys from environment variables
            # Pattern matches GROQ_API_KEY, GROQ_API_KEY_1, GEMINI_API_KEY_2, etc.
            pattern = re.compile(r"^(GROQ|GEMINI|OPENAI)_API_KEY(?:_\d+)?$")
            env_keys = {}
            for env_var, value in os.environ.items():
                match = pattern.match(env_var)
                if match and value.strip():
                    provider = match.group(1).lower()
                    env_keys[value.strip()] = (env_var, provider)

            # Ignore duplicates, add to internal store
            for key_val, (env_var, provider) in env_keys.items():
                # Avoid duplicates
                if not any(k.key_value == key_val for k in self._keys):
                    self._keys.append(ApiKeyInfo(
                        key_id=env_var,
                        provider=provider,
                        key_value=key_val
                    ))

            # Merge with DB keys from key_manager_service so UI doesn't break
            try:
                from app.services.key_manager_service import key_manager_service
                for p in ["groq", "gemini", "openai"]:
                    db_keys = key_manager_service.get_active_keys(p)
                    for k in db_keys:
                        k_val = k.get("key", "").strip()
                        k_name = k.get("name", "Unknown DB Key")
                        if k_val and not any(existing.key_value == k_val for existing in self._keys):
                            self._keys.append(ApiKeyInfo(
                                key_id=k_name,
                                provider=p,
                                key_value=k_val
                            ))
            except Exception as e:
                logger.warning(f"Could not merge keys from key_manager_service: {e}")

            # Initialize provider indices
            for provider in self._provider_fallback_order:
                self._current_index_by_provider[provider] = 0

            logger.info(f"Loaded {len(self._keys)} API keys successfully.")

    def _get_provider_keys(self, provider: str) -> List[ApiKeyInfo]:
        return [k for k in self._keys if k.provider == provider]

    def _get_healthy_key_for_provider(self, provider: str) -> Optional[ApiKeyInfo]:
        provider_keys = self._get_provider_keys(provider)
        if not provider_keys:
            return None

        # Check if current key is healthy
        current_idx = self._current_index_by_provider.get(provider, 0)
        
        # We need to loop at most len(provider_keys) times to find a healthy key
        for _ in range(len(provider_keys)):
            idx = current_idx % len(provider_keys)
            k = provider_keys[idx]
            
            # Reset cooldowns if expired
            if k.status == "Rate Limited" and time.time() > k.cooldown_until:
                k.status = "Healthy"
                
            if k.status == "Healthy":
                self._current_index_by_provider[provider] = idx
                return k
                
            current_idx += 1
            
        return None

    def get_active_provider_and_key(self) -> Tuple[str, ApiKeyInfo]:
        """
        Returns the (provider, ApiKeyInfo) of the first available healthy key,
        respecting the fallback order.
        Raises RuntimeError if all configured providers are unavailable.
        """
        with self._lock:
            # First check if the active provider configured in DB is available (if any)
            try:
                from app.services.key_manager_service import key_manager_service
                db_preferred = key_manager_service.get_active_provider()
            except Exception:
                db_preferred = None
            
            # We construct an ordered list of providers to try
            ordered_providers = []
            if db_preferred and db_preferred in self._provider_fallback_order:
                ordered_providers.append(db_preferred)
                
            for p in self._provider_fallback_order:
                if p not in ordered_providers:
                    ordered_providers.append(p)
                    
            for provider in ordered_providers:
                k = self._get_healthy_key_for_provider(provider)
                if k:
                    return provider, k
                    
            raise RuntimeError("All configured AI providers and API keys are unavailable (rate limited or invalid).")

    def record_success(self, key_id: str):
        with self._lock:
            for k in self._keys:
                if k.key_id == key_id:
                    k.status = "Healthy"
                    k.failures = 0
                    k.requests += 1
                    k.last_used = time.time()
                    break

    def record_failure(self, key_id: str, error_type: str, penalty_seconds: int = 0):
        """
        error_type: "rate_limit", "invalid", "timeout", or "unknown"
        """
        with self._lock:
            for k in self._keys:
                if k.key_id == key_id:
                    k.failures += 1
                    k.rotations += 1
                    
                    if error_type == "rate_limit":
                        k.rate_limits += 1
                        k.status = "Rate Limited"
                        # Use penalty if provided (e.g. from Retry-After header), otherwise default backoff
                        backoff = penalty_seconds if penalty_seconds > 0 else min(60 * (2 ** min(k.rate_limits - 1, 4)), 1800)
                        k.cooldown_until = time.time() + backoff
                        logger.warning(f"[{k.provider}] Key '{k.key_id}' rate limited. Cooldown for {backoff}s.")
                    elif error_type == "invalid":
                        k.status = "Invalid"
                        logger.warning(f"[{k.provider}] Key '{k.key_id}' marked as invalid. Removing from rotation.")
                    else:
                        # Timeout or connection error -> soft fail, maybe rate limit
                        k.status = "Rate Limited"
                        k.cooldown_until = time.time() + (penalty_seconds if penalty_seconds > 0 else 60)
                        logger.warning(f"[{k.provider}] Key '{k.key_id}' failed due to {error_type}. Cooldown applied.")
                    
                    # Advance the index so the next call picks the next key
                    provider_keys = self._get_provider_keys(k.provider)
                    if provider_keys:
                        self._current_index_by_provider[k.provider] = (self._current_index_by_provider.get(k.provider, 0) + 1) % len(provider_keys)
                    break

    def get_dashboard_stats(self) -> dict:
        with self._lock:
            stats = []
            for k in self._keys:
                stats.append({
                    "key_id": k.key_id,
                    "provider": k.provider,
                    "masked_key": k.mask_key(),
                    "status": k.status,
                    "cooldown_remaining": max(0, int(k.cooldown_until - time.time())),
                    "requests": k.requests,
                    "failures": k.failures,
                    "rotations": k.rotations,
                    "rate_limits": k.rate_limits,
                    "last_used": k.last_used
                })
                
            return {
                "total_keys": len(self._keys),
                "healthy_keys": sum(1 for k in self._keys if k.status == "Healthy"),
                "keys": stats
            }

# Singleton instance
api_key_manager = ApiKeyManager()
