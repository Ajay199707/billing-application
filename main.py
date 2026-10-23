"""
Main Executable Entry Point for AJ Billing Software.
"""

import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.ui.app import run_app

if __name__ == "__main__":
    run_app()
