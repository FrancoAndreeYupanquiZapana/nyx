# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import mediapipe

# Locate mediapipe installation path
mediapipe_path = os.path.dirname(mediapipe.__file__)
mediapipe_modules_path = os.path.join(mediapipe_path, 'modules')

a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/assets', 'src/assets'),
        ('src/scripts', 'src/scripts'),
        ('src/models', 'src/models'),
        ('src/config', 'src/config'),
        (mediapipe_modules_path, 'mediapipe/modules')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NYX_System',
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
    icon=['src\\assets\\Nyx.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NYX_System',
)
