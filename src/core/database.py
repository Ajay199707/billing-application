"""
Database engine factory, session providers, and dialect adapters
for PostgreSQL and SQLite WAL with atomic concurrency controls.
"""

import contextlib
import logging
import sqlite3
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from src.core.config import DatabaseConfig, DatabaseMode
from src.core.exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)


def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Configures high-concurrency WAL mode, busy timeout, and foreign keys for SQLite."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()


class DatabaseManager:
    """
    Manages SQLAlchemy engine lifecycle, connection pooling,
    and thread-safe session factories for both PostgreSQL and SQLite.
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engine: Engine | None = None
        self._sessionmaker: sessionmaker[Session] | None = None

    def initialize(self) -> Engine:
        """Creates the engine and configures dialect-specific settings."""
        url = self.config.get_url()
        is_sqlite = self.config.mode == DatabaseMode.SINGLE_SQLITE

        if is_sqlite:
            # Check directory
            if self.config.sqlite_file != ":memory:":
                from pathlib import Path
                Path(self.config.sqlite_file).parent.mkdir(parents=True, exist_ok=True)

            self._engine = create_engine(
                url,
                connect_args={"check_same_thread": False, "timeout": 15},
                pool_pre_ping=True,
            )
            event.listen(self._engine, "connect", _set_sqlite_pragmas)
            logger.info(f"SQLite WAL engine initialized at: {self.config.sqlite_file}")
        else:
            # PostgreSQL Engine with QueuePool and pre-ping for resilient reconnection
            self._engine = create_engine(
                url,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=True,
                connect_args={"connect_timeout": self.config.connect_timeout},
            )
            logger.info(f"PostgreSQL engine initialized for {self.config.username}@{self.config.host}:{self.config.port}/{self.config.database}")

        self._sessionmaker = sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        return self._engine

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self.initialize()
        return self._engine

    @property
    def session_factory(self) -> sessionmaker[Session]:
        if self._sessionmaker is None:
            self.initialize()
        return self._sessionmaker

    def test_connection(self) -> tuple[bool, str]:
        """Tests if the database server or file is accessible."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).scalar()
                if result == 1:
                    return True, "Database connection successful."
                return False, f"Unexpected response: {result}"
        except Exception as exc:
            logger.error(f"Connection test failed: {exc}")
            return False, str(exc)

    @contextlib.contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provides a transactional database session scope with automatic commit/rollback."""
        sess: Session = self.session_factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def create_all_tables(self, base) -> None:
        """Creates all schema tables directly (used in tests or fresh database setup)."""
        base.metadata.create_all(bind=self.engine)
        logger.info("Database schema tables created.")

    def drop_all_tables(self, base) -> None:
        """Drops all schema tables (used for testing teardown)."""
        base.metadata.drop_all(bind=self.engine)
        logger.warning("Database schema tables dropped.")

    def close(self) -> None:
        """Disposes the connection pool."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            logger.info("Database engine disposed.")


# Global default database manager
_db_manager: DatabaseManager | None = None


def get_db_manager(config: DatabaseConfig | None = None) -> DatabaseManager:
    """Returns the singleton or newly configured DatabaseManager."""
    global _db_manager
    if config is not None or _db_manager is None:
        from src.core.config import AppConfig
        cfg = config or AppConfig.load().database
        _db_manager = DatabaseManager(cfg)
    return _db_manager
