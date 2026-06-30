import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import app_config

class HistoryService:
    def __init__(self):
        self.db_path = app_config.workspace_directory / "migration_history.db"
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migration_history (
                    migration_id TEXT PRIMARY KEY,
                    repository_name TEXT NOT NULL,
                    repository_url TEXT NOT NULL,
                    branch_name TEXT,
                    repository_path TEXT,
                    target_version TEXT NOT NULL,
                    migration_status TEXT NOT NULL,
                    build_status TEXT,
                    runtime_status TEXT,
                    files_changed_java INTEGER DEFAULT 0,
                    files_changed_xml INTEGER DEFAULT 0,
                    files_changed_config INTEGER DEFAULT 0,
                    files_changed_total INTEGER DEFAULT 0,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    execution_time TEXT,
                    error_message TEXT,
                    details_json TEXT
                )
            """)
            conn.commit()

    def create_record(self, migration_id: str, repo_url: str, target_version: str):
        # Derive repository name
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        if not repo_name:
            repo_name = "UnknownRepository"
            
        start_time = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO migration_history (
                    migration_id, repository_name, repository_url, branch_name, 
                    target_version, migration_status, start_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                migration_id, repo_name, repo_url, "main", 
                target_version, "PENDING", start_time
            ))
            conn.commit()

    def update_record(self, migration_id: str, status: str, result_dict: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        end_time = datetime.now()
        end_time_iso = end_time.isoformat()
        
        with self._get_connection() as conn:
            # First fetch start_time to calculate execution_time
            cursor = conn.execute("SELECT start_time FROM migration_history WHERE migration_id = ?", (migration_id,))
            row = cursor.fetchone()
            execution_time = "0s"
            if row and row[0]:
                try:
                    start_dt = datetime.fromisoformat(row[0])
                    duration_sec = (end_time - start_dt).total_seconds()
                    execution_time = f"{duration_sec:.1f}s"
                except Exception:
                    pass
            
            build_status = "Pending"
            runtime_status = "Pending"
            files_java = 0
            files_xml = 0
            files_config = 0
            files_total = 0
            details_json = None
            
            if result_dict:
                build_status = result_dict.get("buildStatus", "Unknown")
                
                detailed_report_str = result_dict.get("detailedReport", "")
                detailed_report = {}
                if isinstance(detailed_report_str, str) and detailed_report_str.startswith("{"):
                    try:
                        detailed_report = json.loads(detailed_report_str)
                    except Exception:
                        pass
                elif isinstance(detailed_report_str, dict):
                    detailed_report = detailed_report_str
                    
                runtime_status = detailed_report.get("runtime_status", "Verified" if result_dict.get("success") else "Failed")
                
                modified_files = result_dict.get("modifiedFiles", [])
                if isinstance(modified_files, list):
                    files_total = len(modified_files)
                    files_java = sum(1 for f in modified_files if str(f).endswith(".java"))
                    files_xml = sum(1 for f in modified_files if str(f).endswith(".xml"))
                    files_config = sum(1 for f in modified_files if "application" in str(f) or "properties" in str(f) or "yml" in str(f))
                
                details_json = json.dumps(result_dict)
            else:
                build_status = "Failed"
                runtime_status = "Failed"

            if error_message:
                build_status = "Failed"
                
            conn.execute("""
                UPDATE migration_history
                SET migration_status = ?,
                    build_status = ?,
                    runtime_status = ?,
                    files_changed_java = ?,
                    files_changed_xml = ?,
                    files_changed_config = ?,
                    files_changed_total = ?,
                    end_time = ?,
                    execution_time = ?,
                    error_message = ?,
                    details_json = ?
                WHERE migration_id = ?
            """, (
                status, build_status, runtime_status,
                files_java, files_xml, files_config, files_total,
                end_time_iso, execution_time, error_message, details_json,
                migration_id
            ))
            conn.commit()

    def get_history(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM migration_history ORDER BY start_time DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def clear_history(self):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM migration_history")
            conn.commit()

history_service = HistoryService()
