"""
Enterprise Database Backup and Disaster Recovery Service.
Supports SQLite hot online backups (zero-downtime API), PostgreSQL pg_dump runners,
SHA-256 cryptographic verification, and safe restoration workflows.
"""

import hashlib
import logging
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from src.core.config import DatabaseConfig, DatabaseMode
from src.core.database import DatabaseManager
from src.core.exceptions import BackupError, RestoreError, PermissionDeniedError
from src.models import BackupHistory, AuditLog
from src.services.auth_service import UserSession

logger = logging.getLogger(__name__)


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class BackupService:
    def __init__(self, db_manager: DatabaseManager, backup_dir: Optional[Path] = None):
        self.db = db_manager
        if backup_dir is None:
            from src.core.config import get_default_app_dir
            backup_dir = get_default_app_dir() / "backups"
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        current_session: UserSession,
        backup_type: str = "MANUAL",  # MANUAL, SCHEDULED, PRE_MIGRATION
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a complete database backup with SHA-256 verification and records it in BackupHistory.
        """
        if not current_session.has_permission("backup:manage"):
            raise PermissionDeniedError("backup:manage")

        config = self.db.config
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            if config.mode == DatabaseMode.SINGLE_SQLITE:
                backup_file = self._backup_sqlite(config, timestamp_str)
            else:
                backup_file = self._backup_postgres(config, timestamp_str)

            file_size = backup_file.stat().st_size
            sha256_hash = compute_sha256(backup_file)

            # Record in backup history
            with self.db.session() as session:
                entry = BackupHistory(
                    backup_timestamp=datetime.now(timezone.utc),
                    backup_type=backup_type,
                    file_path=str(backup_file),
                    file_size_bytes=file_size,
                    checksum_sha256=sha256_hash,
                    status="SUCCESS",
                    notes=notes,
                )
                session.add(entry)
                session.flush()

                audit = AuditLog(
                    user_id=current_session.user_id,
                    action="DATABASE_BACKUP_CREATED",
                    entity_name="BackupHistory",
                    entity_id=str(entry.id),
                    details_json=f'{{"file": "{backup_file.name}", "size": {file_size}}}',
                )
                session.add(audit)

                logger.info(f"Database backup created: {backup_file} ({file_size} bytes, SHA256: {sha256_hash[:8]}...)")
                return {
                    "id": entry.id,
                    "file_path": str(backup_file),
                    "file_size": file_size,
                    "checksum_sha256": sha256_hash,
                    "status": "SUCCESS",
                }

        except Exception as exc:
            logger.error(f"Backup failed: {exc}")
            raise BackupError(f"Failed to create database backup: {exc}")

    def verify_backup(self, backup_file_path: str) -> Tuple[bool, str]:
        """
        Verifies that a backup file exists, is non-empty, and possesses valid internal integrity.
        """
        path = Path(backup_file_path)
        if not path.exists():
            return False, "Backup file does not exist on disk."

        if path.stat().st_size == 0:
            return False, "Backup file is empty (0 bytes)."

        # If it's a SQLite file, run integrity check
        if path.suffix.lower() in [".db", ".sqlite", ".bak"]:
            try:
                conn = sqlite3.connect(str(path))
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()
                conn.close()
                if result and result[0] == "ok":
                    return True, "SQLite database integrity verified (PRAGMA integrity_check: ok)."
                return False, f"Integrity check failed: {result}"
            except Exception as e:
                return False, f"Cannot open SQLite backup: {e}"

        return True, "File verified and non-empty."

    def restore_backup(
        self,
        current_session: UserSession,
        backup_file_path: str,
    ) -> bool:
        """
        Restores database from a selected verified backup file.
        Safely creates a pre-restoration rollback backup before altering the database.
        """
        if not current_session.has_permission("backup:manage"):
            raise PermissionDeniedError("backup:manage")

        is_valid, msg = self.verify_backup(backup_file_path)
        if not is_valid:
            raise RestoreError(f"Backup verification failed: {msg}")

        config = self.db.config
        if config.mode == DatabaseMode.SINGLE_SQLITE:
            target_path = Path(config.sqlite_file)

            # 1. Take a safety backup of current live DB
            safety_copy = target_path.with_suffix(f".safety_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
            if target_path.exists():
                shutil.copy2(target_path, safety_copy)
                logger.info(f"Pre-restoration safety snapshot saved: {safety_copy}")

            # 2. Close active engine pool
            self.db.close()

            # 3. Replace database file
            shutil.copy2(backup_file_path, target_path)

            # 4. Re-initialize database engine
            self.db.initialize()

            # 5. Verify restored DB
            test_ok, test_msg = self.db.test_connection()
            if not test_ok:
                # Rollback
                shutil.copy2(safety_copy, target_path)
                self.db.initialize()
                raise RestoreError(f"Restored database failed connection check ({test_msg}). Reverted to safety copy.")

            logger.info("Database restoration completed successfully.")
            return True
        else:
            raise RestoreError("PostgreSQL remote restoration requires administrative pg_restore terminal execution.")

    def list_backups(self) -> List[Dict[str, Any]]:
        """Lists historical backups recorded in database and present on disk."""
        with self.db.session() as session:
            entries = session.query(BackupHistory).order_by(BackupHistory.backup_timestamp.desc()).all()
            return [
                {
                    "id": b.id,
                    "timestamp": b.backup_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": b.backup_type,
                    "file_path": b.file_path,
                    "file_name": Path(b.file_path).name,
                    "file_size": b.file_size_bytes,
                    "checksum": b.checksum_sha256[:12] + "...",
                    "status": b.status,
                }
                for b in entries
            ]

    def _backup_sqlite(self, config: DatabaseConfig, timestamp: str) -> Path:
        """Executes zero-downtime hot online backup via sqlite3.backup() API."""
        dest_file = self.backup_dir / f"backup_shop_{timestamp}.db"
        src_conn = sqlite3.connect(config.sqlite_file)
        dest_conn = sqlite3.connect(str(dest_file))

        with dest_conn:
            src_conn.backup(dest_conn, pages=100)

        dest_conn.close()
        src_conn.close()
        return dest_file

    def _backup_postgres(self, config: DatabaseConfig, timestamp: str) -> Path:
        """Executes pg_dump for PostgreSQL databases."""
        dest_file = self.backup_dir / f"backup_postgres_{timestamp}.sql"
        env = os.environ.copy()
        if config.password:
            env["PGPASSWORD"] = config.password

        cmd = [
            "pg_dump",
            "-h", config.host,
            "-p", str(config.port),
            "-U", config.username,
            "-F", "c",  # Custom compressed format
            "-b",       # Blobs
            "-v",
            "-f", str(dest_file),
            config.database,
        ]

        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            raise BackupError(f"pg_dump error: {res.stderr}")
        return dest_file
