# -*- mode: python ; coding: utf-8 -*-
# PhotoTools PyInstaller Spec File

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all customtkinter data files
ctk_datas = collect_data_files('customtkinter')

# Hidden imports for all dependencies
hidden_imports = [
    'customtkinter',
    'PIL',
    'PIL._tkinter_finder',
    'cv2',
    'numpy',
    'requests',
    'fal_client',
    'scipy',
    'webview',
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'json',
    'hashlib',
    'threading',
    'queue',
    'logging',
    'traceback',
    'datetime',
    'time',
    'os',
    'sys',
    'shutil',
    'tempfile',
    'zipfile',
    'urllib.request',
    'base64',
    'io',
    're',
    'pathlib',
]

a = Analysis(
    ['photo_tools.py'],
    pathex=[],
    binaries=[],
    datas=ctk_datas + [
        ('license_manager.py', '.'),
        ('login_window.py', '.'),
        ('auto_updater.py', '.'),
        ('perspective_engine.py', '.'),
        ('darktable_perspective.py', '.'),
    ],
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
    name='PhotoTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=True,  # Important for macOS
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PhotoTools',
)

app = BUNDLE(
    coll,
    name='PhotoTools.app',
    icon=None,  # Add icon path if available
    bundle_identifier='com.phototools.app',
    info_plist={
        'CFBundleName': 'PhotoTools',
        'CFBundleDisplayName': 'PhotoTools',
        'CFBundleVersion': '1.0.24',
        'CFBundleShortVersionString': '1.0.24',
        'CFBundleIdentifier': 'com.phototools.app',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # Support dark mode
        'LSMinimumSystemVersion': '10.15',
        'CFBundleDocumentTypes': [],
    },
)
