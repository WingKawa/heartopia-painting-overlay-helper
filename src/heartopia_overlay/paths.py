"""疊層資源與使用者資料路徑。

palette.json 與離線教學跟隨程式封裝；assist_state.json、logs 等使用者資料
保存在執行檔旁，避免更新程式或結束暫存解壓目錄後遺失。
"""
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundled(*parts) -> pathlib.Path:
    """跟著程式走的唯讀資料。"""
    if is_frozen():
        base = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(sys.executable).parent))
    else:
        base = _HERE.parent.parent          # src/heartopia_overlay -> 專案根目錄
    return base.joinpath(*parts)


def userdata(*parts) -> pathlib.Path:
    """使用者可改、需要持久保存的設定。"""
    base = pathlib.Path(sys.executable).parent if is_frozen() else _HERE.parent.parent
    return base.joinpath(*parts)
