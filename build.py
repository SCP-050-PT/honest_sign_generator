"""
Скрипт сборки .exe через PyInstaller API.
ИСПРАВЛЕНО: убран pylibdmtx, добавлен ZXing.Net через pythonnet.
ДОБАВЛЕНО: поддержка кастомной иконки.
"""

import sys
import os
from pathlib import Path

PYTHON_PATH = Path(sys.executable).parent
SITE_PACKAGES = PYTHON_PATH / "Lib" / "site-packages"
PROJECT_ROOT = Path(__file__).parent

from PyInstaller.__main__ import run

# === ИКОНКА ===
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"
if ICON_PATH.exists():
    print(f"[BUILD] Иконка найдена: {ICON_PATH}")
else:
    print(f"[BUILD] WARNING: Иконка не найдена в {ICON_PATH}")
    print("[BUILD] Создай папку assets/ и положи туда icon.ico (256x256)")
    ICON_PATH = None

# === ZXing.Net DLL ===
ZXING_DLL = PROJECT_ROOT / "zxing" / "ZXing.dll"
if not ZXING_DLL.exists():
    print(f"[BUILD] WARNING: ZXing.dll не найден в {ZXING_DLL}")
    print("[BUILD] Убедись, что папка zxing/ с ZXing.dll лежит рядом с build.py")
else:
    print(f"[BUILD] ZXing.dll: {ZXING_DLL}")

# === PyQt6 DLL ===
pyqt6_binaries = []
qt_dlls = ["Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll"]
for dll in qt_dlls:
    dll_path = SITE_PACKAGES / "PyQt6" / dll
    if dll_path.exists():
        pyqt6_binaries.append((str(dll_path), "PyQt6"))

platforms_path = SITE_PACKAGES / "PyQt6" / "Qt6" / "plugins" / "platforms"
if platforms_path.exists():
    for f in platforms_path.iterdir():
        if f.suffix == ".dll":
            pyqt6_binaries.append((str(f), "PyQt6" / "Qt6" / "plugins" / "platforms"))

# === Hidden imports ===
hiddenimports = [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.sip",
    "pandas",
    "openpyxl",
    "PIL",
    "PIL._imagingtk",
    "reportlab",
    "reportlab.pdfgen.canvas",
    "reportlab.lib.units",
    "reportlab.lib.utils",
    "clr",
    "pythonnet",
]

args = [
    "main.py",
    "--onefile",
    "--windowed",
    "--name=HonestSignGenerator",
    "--clean",
    f"--paths={SITE_PACKAGES}",
    f"--paths={PROJECT_ROOT}",
]

# === ИКОНКА ===
if ICON_PATH and ICON_PATH.exists():
    args.append(f"--icon={ICON_PATH}")

# === ZXing.Net DLL ===
if ZXING_DLL.exists():
    args.append(f"--add-binary={ZXING_DLL};zxing")

# PyQt6 DLL
for src, dst in pyqt6_binaries:
    args.append(f"--add-binary={src};{dst}")

# Данные проекта
args.extend(
    [
        f"--add-data={PROJECT_ROOT / 'config.py'};.",
        f"--add-data={PROJECT_ROOT / 'gui'};gui",
        f"--add-data={PROJECT_ROOT / 'core'};core",
        f"--add-data={PROJECT_ROOT / 'fonts'};fonts",
        f"--add-data={PROJECT_ROOT / 'zxing'};zxing",
    ]
)

# Hidden imports
for imp in hiddenimports:
    args.append(f"--hidden-import={imp}")

# Исключения
excludes = [
    "matplotlib",
    "numpy.random._examples",
    "scipy",
    "tkinter",
    "PyQt6.Qt3D",
    "PyQt6.QtAxContainer",
    "PyQt6.QtBluetooth",
    "PyQt6.QtDBus",
    "PyQt6.QtDesigner",
    "PyQt6.QtHelp",
    "PyQt6.QtLocation",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtNfc",
    "PyQt6.QtOpenGL",
    "PyQt6.QtPositioning",
    "PyQt6.QtPrintSupport",
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "PyQt6.QtQuick3D",
    "PyQt6.QtQuickWidgets",
    "PyQt6.QtRemoteObjects",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtSql",
    "PyQt6.QtSvg",
    "PyQt6.QtSvgWidgets",
    "PyQt6.QtTest",
    "PyQt6.QtTextToSpeech",
    "PyQt6.QtWebChannel",
    "PyQt6.QtWebEngine",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineQuick",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebSockets",
    "PyQt6.QtXml",
    "PIL.ImageQt",
    "PIL._tkinter_finder",
]

for exc in excludes:
    args.append(f"--exclude-module={exc}")

print(f"[BUILD] Args count: {len(args)}")
print("[BUILD] Starting PyInstaller...")

run(args)
print("[BUILD] Done! Check dist/HonestSignGenerator.exe")
