"""Windows x64 免安裝版：python -m PyInstaller assist.spec --noconfirm"""
from pathlib import Path
import runpy

root = Path(SPECPATH)
product = runpy.run_path(str(root/'src'/'heartopia_overlay'/'version.py'))
name = product['APP_ID']
a = Analysis(
    ['run_assist.py'], pathex=['src'],
    datas=[('data/palette.json','data'),('docs/guide','docs/guide')],
    hiddenimports=['win32api','win32con','win32gui'],
    excludes=['pytest','matplotlib','IPython'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name=name,console=False,upx=False)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name=name)
