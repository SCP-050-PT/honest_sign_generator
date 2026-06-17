# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=['C:\\Users\\Administrator\\Desktop\\honest_sign_generator\\venv\\Scripts\\Lib\\site-packages', 'C:\\Users\\Administrator\\Desktop\\honest_sign_generator'],
    binaries=[('C:\\Users\\Administrator\\Desktop\\honest_sign_generator\\zxing\\ZXing.dll', 'zxing')],
    datas=[('C:\\Users\\Administrator\\Desktop\\honest_sign_generator\\config.py', '.'), ('C:\\Users\\Administrator\\Desktop\\honest_sign_generator\\gui', 'gui'), ('C:\\Users\\Administrator\\Desktop\\honest_sign_generator\\core', 'core'), ('C:\\Users\\Administrator\\Desktop\\honest_sign_generator\\fonts', 'fonts'), ('C:\\Users\\Administrator\\Desktop\\honest_sign_generator\\zxing', 'zxing')],
    hiddenimports=['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'PyQt6.sip', 'pandas', 'openpyxl', 'PIL', 'PIL._imagingtk', 'reportlab', 'reportlab.pdfgen.canvas', 'reportlab.lib.units', 'reportlab.lib.utils', 'clr', 'pythonnet'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy.random._examples', 'scipy', 'tkinter', 'PyQt6.Qt3D', 'PyQt6.QtAxContainer', 'PyQt6.QtBluetooth', 'PyQt6.QtDBus', 'PyQt6.QtDesigner', 'PyQt6.QtHelp', 'PyQt6.QtLocation', 'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets', 'PyQt6.QtNetwork', 'PyQt6.QtNfc', 'PyQt6.QtOpenGL', 'PyQt6.QtPositioning', 'PyQt6.QtPrintSupport', 'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtQuickWidgets', 'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtSql', 'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'PyQt6.QtTest', 'PyQt6.QtTextToSpeech', 'PyQt6.QtWebChannel', 'PyQt6.QtWebEngine', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineQuick', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebSockets', 'PyQt6.QtXml', 'PIL.ImageQt', 'PIL._tkinter_finder'],
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
    name='HonestSignGenerator',
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
    icon=['C:\\Users\\Administrator\\Desktop\\honest_sign_generator\\assets\\icon.ico'],
)
