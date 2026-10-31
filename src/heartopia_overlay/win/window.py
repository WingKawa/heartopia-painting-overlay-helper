"""遊戲視窗查詢。座標一律是實體像素（呼叫端須先 ensure_dpi_aware）。"""
from dataclasses import dataclass

import win32gui

from ..errors import GameWindowError
from .dpi import ensure_dpi_aware

WINDOW_TITLE = "Heartopia"


def game_title_matches(title):
    """支援地區語言與版本後綴，但不把工具自己的標題當成遊戲。"""
    title = title.strip().casefold()
    if any(word in title for word in ('手動','疊圖','疊層','overlay','assist','preview')):
        return False
    return title in ('heartopia','心動小鎮','心动小镇') or title.startswith(('heartopia -','heartopia (','心動小鎮 -','心动小镇 -'))


@dataclass(frozen=True)
class ClientRect:
    """視窗 client area 在螢幕座標系中的位置與大小。"""
    left: int
    top: int
    width: int
    height: int


def find_game_hwnd() -> int:
    ensure_dpi_aware()
    matches = []

    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and game_title_matches(win32gui.GetWindowText(hwnd)):
            matches.append(hwnd)

    win32gui.EnumWindows(_cb, None)
    if not matches:
        raise GameWindowError(f"找不到標題為 {WINDOW_TITLE!r} 的視窗，請確認遊戲已啟動")
    foreground = win32gui.GetForegroundWindow()
    if foreground in matches:
        return foreground
    if len(matches)>1:
        raise GameWindowError('找到多個遊戲視窗，請先切到要使用的遊戲視窗再試。')
    return matches[0]


def screenshot_frames(hwnd):
    """Alt+PrintScreen 可能使用一般外框或 DWM 可見外框，皆記下客戶區位置。"""
    import ctypes
    from ctypes import wintypes
    client = get_client_rect(hwnd)
    boxes = [win32gui.GetWindowRect(hwnd)]
    rect = wintypes.RECT()
    api = ctypes.windll.dwmapi.DwmGetWindowAttribute
    api.argtypes = [wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
    api.restype = ctypes.c_long
    if api(hwnd,9,ctypes.byref(rect),ctypes.sizeof(rect))==0:
        boxes.append((rect.left,rect.top,rect.right,rect.bottom))
    frames = []
    for left,top,right,bottom in boxes:
        box = (right-left,bottom-top,client.left-left,client.top-top,
               client.left-left+client.width,client.top-top+client.height)
        if box not in frames and 0<=box[2]<box[4]<=box[0] and 0<=box[3]<box[5]<=box[1]:
            frames.append(box)
    return frames


def get_client_rect(hwnd: int) -> ClientRect:
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    _, _, right, bottom = win32gui.GetClientRect(hwnd)
    return ClientRect(left, top, right, bottom)
