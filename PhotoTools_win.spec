# -*- mode: python ; coding: utf-8 -*-
# PhotoTools Windows Build Spec (PyInstaller)
# Usage: pyinstaller PhotoTools_win.spec --clean --noconfirm


a = Analysis(
    ['photo_tools.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('license_manager.py', '.'),
        ('login_window.py', '.'),
        ('auto_updater.py', '.'),
        ('perspective_engine.py', '.'),
        ('darktable_perspective.py', '.'),
    ],
    hiddenimports=[
        'PIL', 'fal_client', 'customtkinter', 'cv2',
        'pynput', 'pynput.mouse', 'pynput.keyboard',
        'pynput.mouse._win32', 'pynput.keyboard._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['lensfunpy', 'Quartz', 'AppKit', 'objc', 'Cocoa'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PhotoTools',
)
