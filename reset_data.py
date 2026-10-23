"""
Data Reset Utility for AJ Billing Software.
Run this script to reset the admin password or completely wipe the database for a fresh start.
"""

import os
import sys
from pathlib import Path
from src.core.config import get_default_app_dir
from src.core.security import hash_password


def reset_password(new_password: str = "admin123"):
    """Resets the root admin password in the active database."""
    import sqlite3
    db_file = get_default_app_dir() / "shop_billing.db"
    if not db_file.exists():
        print(f"Database file not found at: {db_file}")
        return

    pwd_hash = hash_password(new_password)
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = ? WHERE username = 'admin'", (pwd_hash,))
    if cur.rowcount > 0:
        conn.commit()
        print(f"[OK] Password for user 'admin' successfully reset to: {new_password}")
    else:
        print("[FAIL] User 'admin' not found in database.")
    conn.close()


def full_reset():
    """Wipes all local database records and config so the Setup Wizard re-runs from scratch."""
    app_dir = get_default_app_dir()
    print(f"Cleaning all data from: {app_dir}")
    for item in app_dir.glob("*"):
        try:
            if item.is_file():
                item.unlink()
                print(f"Deleted: {item.name}")
        except Exception as e:
            print(f"Could not delete {item.name}: {e}")
    print("[OK] Full reset complete. Launch 'python main.py' to run the Setup Wizard from scratch.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        full_reset()
    else:
        reset_password("admin123")
