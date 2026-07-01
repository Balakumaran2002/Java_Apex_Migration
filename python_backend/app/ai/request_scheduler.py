import uuid
import time
import logging
import threading
from typing import Callable, Any

from app.config import app_config
from app.ai.scheduler_db import scheduler_db
from app.ai.token_bucket import token_bucket_manager
from app.ai.api_key_manager import api_key_manager

logger = logging.getLogger("request_scheduler")

class RequestScheduler:
    def __init__(self):
        self.concurrency_semaphore = threading.Semaphore(app_config.max_concurrent_requests)
        self.poll_interval = app_config.queue_poll_interval

    def execute(self, provider_name: str, fallback_model: str, callback: Callable[[str, str], Any]) -> Any:
        """
        Executes a callable that makes an LLM request, managing concurrency and token buckets.
        The callback should take (api_key_id, api_key_value) as arguments.
        """
        request_id = str(uuid.uuid4())
        
        # We start by logging that a request has arrived and is pending
        scheduler_db.upsert_request_queue(request_id, "PENDING")
        scheduler_db.log_request_action(request_id, "ENQUEUED")
        
        logger.debug(f"Request {request_id} enqueued for provider {provider_name}")

        # Enforce MAX_CONCURRENT_REQUESTS
        self.concurrency_semaphore.acquire()
        try:
            scheduler_db.upsert_request_queue(request_id, "PROCESSING")
            return self._wait_for_token_and_execute(request_id, provider_name, callback)
        finally:
            self.concurrency_semaphore.release()

    def _wait_for_token_and_execute(self, request_id: str, provider_name: str, callback: Callable[[str, str], Any]) -> Any:
        # We loop until we get a token
        while True:
            # 1. Ask API Key Manager for the active key
            try:
                active_provider, active_key_info = api_key_manager.get_active_provider_and_key()
            except RuntimeError as e:
                # If ALL keys are exhausted, api_key_manager throws RuntimeError in its current state.
                # However, the Token Bucket is what should manage rate limits now, so if api_key_manager fails,
                # we just wait and retry.
                logger.warning(f"Request {request_id} waiting: {e}")
                scheduler_db.upsert_request_queue(request_id, "WAITING", error_message=str(e))
                time.sleep(self.poll_interval)
                continue
            
            # If the provider from key manager doesn't match the requested one, it means we are falling back.
            current_provider = active_provider
            
            # 2. Check token bucket for this key
            kid = active_key_info.key_id
            kval = active_key_info.key_value

            if token_bucket_manager.consume_token(kid, current_provider):
                # Token acquired!
                scheduler_db.upsert_request_queue(request_id, "PROCESSING", assigned_key=kid, provider=current_provider)
                scheduler_db.log_request_action(request_id, "TOKEN_CONSUMED", api_key_id=kid, provider=current_provider)
                logger.info(f"Request {request_id} acquired token for key {kid} ({current_provider})")
                
                # Execute the actual LLM call
                try:
                    result = callback(kid, kval)
                    
                    # Success
                    token_bucket_manager.mark_success(kid, current_provider)
                    api_key_manager.record_success(kid)
                    
                    scheduler_db.upsert_request_queue(request_id, "COMPLETED", assigned_key=kid, provider=current_provider)
                    scheduler_db.log_request_action(request_id, "COMPLETED", api_key_id=kid, provider=current_provider)
                    
                    return result
                    
                except Exception as e:
                    # Request failed (e.g. rate limit error or timeout that slipped through)
                    from app.ai.provider_manager import _is_failover_error, _scrub_api_key
                    is_failover, penalty, error_type = _is_failover_error(e)
                    
                    if is_failover:
                        logger.warning(f"Request {request_id} failed with key {kid}. Reason: {_scrub_api_key(str(e))[:120]}")
                        token_bucket_manager.mark_failure(kid, current_provider)
                        api_key_manager.record_failure(kid, error_type, penalty_seconds=penalty)
                        
                        scheduler_db.log_request_action(request_id, "FAILED_RETRYING", api_key_id=kid, provider=current_provider, details=str(error_type))
                        
                        # We don't return, we continue the while True loop to try the next key or wait
                        scheduler_db.upsert_request_queue(request_id, "WAITING", assigned_key=kid, provider=current_provider, error_message=str(error_type))
                        time.sleep(self.poll_interval)
                        continue
                    else:
                        # Unrecoverable error (e.g. bad request, parsing error)
                        scheduler_db.upsert_request_queue(request_id, "FAILED", assigned_key=kid, provider=current_provider, error_message=str(e))
                        scheduler_db.log_request_action(request_id, "FAILED_FATAL", api_key_id=kid, provider=current_provider, details=str(e))
                        raise e
            else:
                # No tokens available. 
                # Ideally, we should check other keys, but api_key_manager handles rotation based on failure penalties.
                # Since token exhaustion means the key is rate limited, we can explicitly penalize it so api_key_manager rotates it.
                api_key_manager.record_failure(kid, "token_exhaustion", penalty_seconds=self.poll_interval)
                
                scheduler_db.upsert_request_queue(request_id, "WAITING", assigned_key=kid, provider=current_provider, error_message="No tokens available")
                time.sleep(self.poll_interval)

request_scheduler = RequestScheduler()
