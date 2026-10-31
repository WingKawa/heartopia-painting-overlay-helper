"""純度守衛。

色盤、圖片與疊層幾何應可離線驗證，不應依賴遊戲截圖或輸入模擬。
"""
import ast
import pathlib

PURE_MODULES = ["palette.py", "target.py", "composition.py", "manual_overlay.py", "paths.py"]
FORBIDDEN_PREFIXES = ("heartopia_overlay.win", "heartopia_overlay.vision", "mss", "win32", "tkinter", "ctypes")
SRC = pathlib.Path(__file__).parent.parent / "src" / "heartopia_overlay"


def _imported_names(path: pathlib.Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_pure_modules_never_touch_screen_or_input():
    for name in PURE_MODULES:
        path = SRC / name
        assert path.exists(), f"{name} 尚未建立"
        for imported in _imported_names(path):
            for bad in FORBIDDEN_PREFIXES:
                assert not imported.startswith(bad), \
                    f"{name} 不得 import {imported}：純模組必須可離線測試"
