import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.config import app_config
from app.ai.scheduler_db import scheduler_db

logger = logging.getLogger("token_bucket")

class TokenBucketManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.bucket_size = app_config.token_bucket_size
        self.refill_interval = app_config.token_refill_interval # seconds

    def _get_or_create_bucket(self, api_key_id: str, provider: str) -> Dict[str, Any]:
        bucket = scheduler_db.get_token_bucket(api_key_id)
        if not bucket:
            # Initialize full bucket
            now = datetime.now().isoformat()
            scheduler_db.upsert_token_bucket(
                api_key_id=api_key_id,
                provider=provider,
                tokens=self.bucket_size,
                last_refill=now
            )
            return scheduler_db.get_token_bucket(api_key_id)
        return bucket

    def _refill_tokens(self, bucket: Dict[str, Any]):
        last_refill_time = datetime.fromisoformat(bucket["last_refill_time"])
        now = datetime.now()
        elapsed_seconds = (now - last_refill_time).total_seconds()

        if elapsed_seconds >= self.refill_interval:
            # Full refill. We could do fractional if needed, but simple full refill is easiest
            scheduler_db.upsert_token_bucket(
                api_key_id=bucket["api_key_id"],
                provider=bucket["provider"],
                tokens=self.bucket_size,
                last_refill=now.isoformat(),
                health=bucket["health_status"],
                failures=bucket["failures"]
            )
            bucket["tokens_remaining"] = self.bucket_size
            bucket["last_refill_time"] = now.isoformat()

    def consume_token(self, api_key_id: str, provider: str, amount: int = 1) -> bool:
        """
        Attempts to consume tokens from the bucket.
        Returns True if successful, False if not enough tokens.
        """
        with self._lock:
            bucket = self._get_or_create_bucket(api_key_id, provider)
            self._refill_tokens(bucket)

            if bucket["tokens_remaining"] >= amount:
                new_tokens = bucket["tokens_remaining"] - amount
                scheduler_db.upsert_token_bucket(
                    api_key_id=bucket["api_key_id"],
                    provider=bucket["provider"],
                    tokens=new_tokens,
                    last_refill=bucket["last_refill_time"],
                    health=bucket["health_status"],
                    failures=bucket["failures"]
                )
                return True
            return False

    def mark_failure(self, api_key_id: str, provider: str):
        with self._lock:
            bucket = self._get_or_create_bucket(api_key_id, provider)
            new_failures = bucket["failures"] + 1
            health = "cooldown" if new_failures > 3 else bucket["health_status"]
            scheduler_db.upsert_token_bucket(
                api_key_id=bucket["api_key_id"],
                provider=bucket["provider"],
                tokens=bucket["tokens_remaining"],
                last_refill=bucket["last_refill_time"],
                health=health,
                failures=new_failures
            )

    def mark_success(self, api_key_id: str, provider: str):
        with self._lock:
            bucket = self._get_or_create_bucket(api_key_id, provider)
            scheduler_db.upsert_token_bucket(
                api_key_id=bucket["api_key_id"],
                provider=bucket["provider"],
                tokens=bucket["tokens_remaining"],
                last_refill=bucket["last_refill_time"],
                health="healthy",
                failures=0
            )

    def get_tokens_remaining(self, api_key_id: str, provider: str) -> int:
        with self._lock:
            bucket = self._get_or_create_bucket(api_key_id, provider)
            self._refill_tokens(bucket)
            return bucket["tokens_remaining"]

token_bucket_manager = TokenBucketManager()
