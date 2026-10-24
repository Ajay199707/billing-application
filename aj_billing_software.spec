# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for compiling AJ Billing Software
into a standalone Windows executable directory.
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

added_files = [
    ('templates', 'templates'),
    ('docs', 'docs'),
    ('alembic', 'alembic'),
    ('alembic.ini', '.'),
    ('assets', 'assets'),
]

hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtPrintSupport',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.postgresql',
    'psycopg',
    'argon2',
    'reportlab',
    'reportlab.graphics.barcode',
    'openpyxl',
    'pandas',
    'matplotlib',
    'matplotlib.backends.backend_qtagg',
    'barcode',
    'barcode.writer',
    'PIL',
    'pydantic',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AJBillingSoftware',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AJBillingSoftware',
)
