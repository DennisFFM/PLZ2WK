# -*- mode: python ; coding: utf-8 -*-
#pyinstaller --onefile --windowed --clean --name "PLZ2WK" --hidden-import shapely --hidden-import shapely.geometry --hidden-import pyproj --hidden-import geopandas._compat --hidden-import pyproj.crs "PLZ2WK.py"


a = Analysis(
    ['PLZ2WK.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['shapely', 'shapely.geometry', 'pyproj', 'geopandas._compat', 'pyproj.crs'],
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
    name='PLZ2WK',
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
)
