# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

# Common hidden imports
hidden_imports = [
    'PIL',
    'pilmoji',
    'pyperclip',
]

# Platform specific hidden imports
if sys.platform == 'win32':
    hidden_imports.extend([
        'keyboard',
        'win32clipboard',
        'win32gui',
        'win32process',
        'psutil',
    ])
else:
    hidden_imports.extend([
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
    ])

a = Analysis(
    ['src/main.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        ('resources', 'resources'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='mahosojo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icons/icon.ico'
)
