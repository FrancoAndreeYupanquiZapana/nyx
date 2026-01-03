# -*- mode: python ; coding: utf-8 -*-

import mediapipe
import os
mediapipe_path = os.path.dirname(mediapipe.__file__)


a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (mediapipe_path, 'mediapipe'),
        ('src/assets', 'assets'),
        ('src/config', 'config'),
    ],
    hiddenimports=[
        'pyautogui',
        'keyboard',
        'cv2',
        'mediapipe',
        'PyQt6',
        'numpy',
        'pynput',
        'pygetwindow',
        'pyrect',
        'mouseinfo',
        'pytweening',
        'pyscreeze',
        'pygetwindow',
        'packaging',
        'PIL',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='Nyx',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True, # MANTENER ADMIN RIGHTS PARA CLICS
    icon=['src\\assets\\nyx.ico'],
)
