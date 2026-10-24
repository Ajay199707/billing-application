"""
Application configuration, database connection parameters, and business profiles.
"""

import json
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class DatabaseMode(str, Enum):
    SINGLE_SQLITE = "sqlite"
    LOCAL_POSTGRES = "local_postgres"
    REMOTE_POSTGRES = "remote_postgres"


class BusinessProfile(str, Enum):
    GROCERY = "grocery"
    HARDWARE = "hardware"
    TEXTILE = "textile"
    ELECTRONICS = "electronics"
    PHARMACY = "pharmacy"
    GENERAL = "general"


def get_default_app_dir() -> Path:
    """Returns the application data directory in user profile."""
    app_data = os.environ.get("LOCALAPPDATA")
    if app_data:
        base = Path(app_data) / "AJBillingSoftware"
    else:
        base = Path.home() / ".aj_billing_software"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_asset_path(filename: str = "app_icon.ico") -> Path:
    """Returns absolute path to an asset, handling both development and PyInstaller frozen modes."""
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent
    return base_dir / "assets" / filename


class DatabaseConfig(BaseModel):
    mode: DatabaseMode = DatabaseMode.SINGLE_SQLITE
    host: str = "localhost"
    port: int = 5432
    database: str = "billing_db"
    username: str = "postgres"
    password: str = ""
    sqlite_file: str = Field(default_factory=lambda: str(get_default_app_dir() / "shop_billing.db"))
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 15
    pool_recycle: int = 1800
    connect_timeout: int = 10

    def get_url(self) -> str:
        """Constructs SQLAlchemy connection URL based on mode."""
        if self.mode == DatabaseMode.SINGLE_SQLITE:
            # Absolute path with sqlite:///
            norm_path = Path(self.sqlite_file).as_posix()
            return f"sqlite:///{norm_path}"
        else:
            # PostgreSQL using psycopg 3 driver
            user = self.username or "postgres"
            pwd = self.password or ""
            auth = f"{user}:{pwd}@" if pwd else f"{user}@"
            return f"postgresql+psycopg://{auth}{self.host}:{self.port}/{self.database}"


class AppConfig(BaseModel):
    shop_name: str = "AJ Super Retail"
    business_profile: BusinessProfile = BusinessProfile.GENERAL
    currency_symbol: str = "₹"
    state_code: str = "33"  # Tamil Nadu default
    state_name: str = "Tamil Nadu"
    receipt_format: str = "80mm"  # "58mm", "80mm", "A4"
    printer_name: str = "Default"
    backup_dir: str = Field(default_factory=lambda: str(get_default_app_dir() / "backups"))
    invoices_dir: str = Field(default_factory=lambda: str(get_default_app_dir() / "invoices"))
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    @classmethod
    def config_path(cls) -> Path:
        return get_default_app_dir() / "app_config.json"

    @classmethod
    def load(cls) -> "AppConfig":
        path = cls.config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**data)
            except Exception:
                pass
        config = cls()
        config.save()
        return config

    def save(self) -> None:
        path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
