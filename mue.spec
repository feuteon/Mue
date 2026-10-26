# -*- mode: python ; coding: utf-8 -*-
# PyInstaller : pyinstaller --noconfirm --clean mue.spec
# Produit dist\Mue\Mue.exe (mode dossier : démarrage rapide, important pour le clic droit).

import glob
import os
import site
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs

datas = [("assets", "assets")]
binaries = collect_dynamic_libs("pymupdf")
hiddenimports = ["win32com.client", "pythoncom", "pywintypes", "_pillow_heif",
                 "pymupdf.mupdf", "pymupdf.extra", "pymupdf.utils", "pymupdf.table"]

# DLL « delvewheel » rangées à côté des paquets (ex. site-packages\pillow_heif.libs\)
for sp in site.getsitepackages():
    for name in ("pillow_heif.libs", "rawpy.libs", "pillow.libs"):
        for dll in glob.glob(os.path.join(sp, name, "*.dll")):
            binaries.append((dll, name))

ffmpeg = os.path.join("build", "bin", "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
if os.path.exists(ffmpeg):
    binaries.append((ffmpeg, "bin"))
else:
    print("ATTENTION : build/bin/ffmpeg.exe absent — lance d'abord tools/prepare_ffmpeg.py")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "imageio_ffmpeg", "pymupdf.layout", "pymupdf4llm", "onnxruntime",
              "scipy", "pandas", "matplotlib", "cv2", "skimage", "sklearn", "IPython", "gi",
              "PyQt5.QtWebEngineWidgets", "PyQt5.QtWebEngineCore", "PyQt5.QtQml", "PyQt5.QtQuick",
              "PyQt5.QtMultimedia", "PyQt5.QtBluetooth", "PyQt5.QtSql", "PyQt5.QtTest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Mue",
    debug=False,
    strip=False,
    upx=False,          # UPX déclenche souvent des faux positifs antivirus
    console=False,      # pas de fenêtre noire
    icon="assets/mue.ico",
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Mue")
