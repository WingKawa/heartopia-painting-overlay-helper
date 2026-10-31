"""截圖。回傳 RGB ndarray、shape (h, w, 3)、dtype uint8。

座標系一律是「相對 client area 左上角」的實體像素，呼叫端不需要知道
視窗在螢幕哪裡。

mss 一律用實體像素，Win32 只有在宣告 DPI aware 之後才用實體像素，
所以 grab_client 會強制檢查兩者尺寸相符——不符就是致命錯誤，不能
使用不一致的座標辨識色盤。
"""
import mss
import numpy as np

from ..errors import GameWindowError
from .dpi import ensure_dpi_aware
from .window import get_client_rect

_MSS = getattr(mss, "MSS", None) or mss.mss


def grab_client(hwnd: int) -> tuple:
    """回傳 (img, rect)。"""
    ensure_dpi_aware()
    rect = get_client_rect(hwnd)
    with _MSS() as sct:
        raw = sct.grab({
            "left": rect.left, "top": rect.top,
            "width": rect.width, "height": rect.height,
        })

    if (raw.width, raw.height) != (rect.width, rect.height):
        raise GameWindowError(
            f"截圖尺寸 {raw.width}x{raw.height} 與 client rect "
            f"{rect.width}x{rect.height} 不符，座標系不一致。"
            f"這通常是 DPI awareness 未生效，或視窗超出了螢幕範圍。"
        )

    bgra = np.asarray(raw, dtype=np.uint8)
    return bgra[:, :, [2, 1, 0]].copy(), rect
