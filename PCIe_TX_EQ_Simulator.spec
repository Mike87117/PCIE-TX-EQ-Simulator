# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

hiddenimports = [
    "pyqtgraph",
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtWidgets",
]

excludes = [
    "matplotlib",
    "pandas",
    "scipy",
    "sklearn",
    "PIL",
    "Pillow",
    "cv2",
    "torch",
    "tensorflow",
    "jupyter",
    "IPython",
    "notebook",
    "seaborn",
    "openpyxl",
    "sympy",
    "pytest",
    "pyqtgraph.opengl",
    "OpenGL",
    "PyQt6",
    "PySide2",
    "PySide6",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PCIe_TX_EQ_Simulator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
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
    name="PCIe_TX_EQ_Simulator",
)
