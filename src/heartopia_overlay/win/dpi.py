"""DPI awareness 與實體座標轉換。

必須在取得任何座標之前呼叫 ensure_dpi_aware()。

Win32 可能回報經縮放的邏輯座標，截圖則使用實體像素。
需宣告並驗證 DPI awareness，避免視窗、游標與截圖使用不同座標系。
"""
import ctypes
from contextlib import contextmanager

from ..errors import GameWindowError

PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
PROCESS_PER_MONITOR_DPI_AWARE = 2
_done = False


@contextmanager
def physical_coordinates():
    """原生操作暫用同一個per-monitor座標系，離開時還原Tk執行緒設定。"""
    api = ctypes.windll.user32.SetThreadDpiAwarenessContext
    api.argtypes = [ctypes.c_void_p]
    api.restype = ctypes.c_void_p
    previous = api(PER_MONITOR_AWARE_V2)
    if not previous:
        raise GameWindowError('無法啟用選色所需的實體像素座標。')
    try:
        yield
    finally:
        api(previous)


def _current_awareness() -> int:
    value = ctypes.c_int()
    ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(value))
    return value.value


def ensure_dpi_aware() -> None:
    """宣告 per-monitor DPI aware，並驗證確實生效。"""
    global _done
    if _done:
        return

    if _current_awareness() != PROCESS_PER_MONITOR_DPI_AWARE:
        user32 = ctypes.windll.user32
        try:
            user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
            user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            user32.SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)
        except (AttributeError, OSError):
            pass
        if _current_awareness() != PROCESS_PER_MONITOR_DPI_AWARE:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
            except OSError:
                pass

    actual = _current_awareness()
    if actual != PROCESS_PER_MONITOR_DPI_AWARE:
        raise GameWindowError(
            f"無法將行程設為 per-monitor DPI aware（目前為 {actual}）。"
            f"在 DPI 縮放的螢幕上，這會讓所有座標偏移，必須先解決才能繼續。"
            f"請確認執行環境沒有透過 manifest 或相容性設定鎖定 DPI 模式。"
        )
    _done = True


def scale_factor(hwnd: int) -> float:
    """回傳該視窗所在螢幕的 DPI 縮放倍率（100% = 1.0）。"""
    return ctypes.windll.user32.GetDpiForWindow(hwnd) / 96.0
