import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import app_config

logger = logging.getLogger("scheduler_db")

class SchedulerDBService:
    def __init__(self):
        self.db_path = app_config.workspace_directory / "request_scheduler.db"
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _init_db(self):
        with self._get_connection() as conn:
            # Token Bucket Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_bucket (
                    api_key_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    tokens_remaining INTEGER NOT NULL,
                    last_refill_time TEXT NOT NULL,
                    health_status TEXT DEFAULT 'healthy',
                    failures INTEGER DEFAULT 0
                )
            """)

            # Request Queue Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_queue (
                    request_id TEXT PRIMARY KEY,
                    queue_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    assigned_key TEXT,
                    provider TEXT,
                    error_message TEXT
                )
            """)

            # Request History Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS request_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    api_key_id TEXT,
                    provider TEXT,
                    action TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT
                )
            """)
            conn.commit()

    def get_token_bucket(self, api_key_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM token_bucket WHERE api_key_id = ?", (api_key_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "api_key_id": row[0],
                    "provider": row[1],
                    "tokens_remaining": row[2],
                    "last_refill_time": row[3],
                    "health_status": row[4],
                    "failures": row[5]
                }
            return None

    def upsert_token_bucket(self, api_key_id: str, provider: str, tokens: int, last_refill: str, health: str = "healthy", failures: int = 0):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO token_bucket (api_key_id, provider, tokens_remaining, last_refill_time, health_status, failures)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(api_key_id) DO UPDATE SET
                    tokens_remaining=excluded.tokens_remaining,
                    last_refill_time=excluded.last_refill_time,
                    health_status=excluded.health_status,
                    failures=excluded.failures
            """, (api_key_id, provider, tokens, last_refill, health, failures))
            conn.commit()

    def log_request_action(self, request_id: str, action: str, api_key_id: str = None, provider: str = None, details: str = None):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO request_history (request_id, api_key_id, provider, action, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (request_id, api_key_id, provider, action, datetime.now().isoformat(), details))
            conn.commit()
            
    def upsert_request_queue(self, request_id: str, status: str, assigned_key: str = None, provider: str = None, error_message: str = None):
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO request_queue (request_id, queue_status, created_at, updated_at, assigned_key, provider, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    queue_status=excluded.queue_status,
                    updated_at=excluded.updated_at,
                    assigned_key=excluded.assigned_key,
                    error_message=excluded.error_message
            """, (request_id, status, now, now, assigned_key, provider, error_message))
            conn.commit()
            
    def get_queue_metrics(self) -> Dict[str, int]:
        metrics = {}
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT queue_status, COUNT(*) FROM request_queue GROUP BY queue_status")
            for row in cursor.fetchall():
                metrics[row[0]] = row[1]
        return metrics

scheduler_db = SchedulerDBService()
