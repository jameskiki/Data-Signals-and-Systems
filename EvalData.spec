# -*- mode: python ; coding: utf-8 -*-


import os
a = Analysis(
    ['EvalData.py'],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join('main_window', '*.py'), 'main_window'),
        (os.path.join('analysis_workspace', '*.py'), 'analysis_workspace'),
        (os.path.join('data_ops', '*.py'), 'data_ops'),
    ],
    hiddenimports=['main_window', 'analysis_workspace', 'data_ops', 'matplotlib', 'numpy', 'pandas'],
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
    name='EvalData',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    name='EvalData'
)
