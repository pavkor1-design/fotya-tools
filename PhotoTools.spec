# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['photo_tools.py'],
    pathex=[],
    binaries=[],
    datas=[('license_manager.py', '.'), ('login_window.py', '.'), ('auto_updater.py', '.')],
    hiddenimports=['PIL', 'fal_client', 'customtkinter', 'cv2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['lensfunpy'],
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
app = BUNDLE(
    coll,
    name='PhotoTools.app',
    icon=None,
    bundle_identifier=None,
)
