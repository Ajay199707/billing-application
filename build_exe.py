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

    spec_file = Path(__file__).parent / "aj_billing_software.spec"

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        str(spec_file),
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\nSUCCESS: Executable created in dist/AJBillingSoftware/AJBillingSoftware.exe")
    else:
        print(f"\nBUILD FAILED with exit code {res.returncode}")
        sys.exit(res.returncode)


if __name__ == "__main__":
    build_executable()
