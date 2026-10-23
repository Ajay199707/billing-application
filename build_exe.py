"""
PyInstaller Packaging Script for Windows Desktop Executable.
"""

import sys
import subprocess
from pathlib import Path


def build_executable():
    print("==================================================")
    print("Building Windows Executable via PyInstaller...")
    print("==================================================")

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "AntigravityBilling",
        "--add-data", "alembic;alembic",
        "--add-data", "alembic.ini;.",
        "--hidden-import", "sqlalchemy.dialects.sqlite",
        "--hidden-import", "sqlalchemy.dialects.postgresql",
        "--hidden-import", "psycopg",
        "--hidden-import", "argon2",
        "--hidden-import", "reportlab",
        "--hidden-import", "openpyxl",
        "main.py",
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\nSUCCESS: Executable created in dist/AntigravityBilling/")
    else:
        print(f"\nBUILD FAILED with exit code {res.returncode}")


if __name__ == "__main__":
    build_executable()
