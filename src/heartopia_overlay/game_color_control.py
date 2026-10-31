"""Tk排程的單次選色控制器；每次點擊前檢查視窗、尺寸與中止鍵。"""
import time
import ctypes
from ctypes import wintypes
import win32api
import win32con
import win32gui
from .game_color import SelectionError, SelectionPlan, observe_palette
from .win.window import get_client_rect
from .win.screen import grab_client
from .win.dpi import physical_coordinates


def physical_cursor_position():
    point = wintypes.POINT()
    if not ctypes.windll.user32.GetPhysicalCursorPos(ctypes.byref(point)):
        raise SelectionError('無法確認滑鼠的實體座標。')
    return point.x,point.y


def move_physical_cursor(point):
    if not ctypes.windll.user32.SetPhysicalCursorPos(int(point[0]),int(point[1])):
        raise SelectionError('無法將滑鼠移到遊戲色盤。')


class GameColorControl:
    def __init__(self,root,hwnd,color,palette,finished,started=None,calibration=None):
        self.root,self.hwnd,self.palette,self.finished = root,hwnd,palette,finished
        self.plan = SelectionPlan(color)
        with physical_coordinates():
            self.rect = get_client_rect(hwnd)
        self.timer = None
        self.done = False
        self.started = started or (lambda: None)
        self.focus_since = None
        self.calibration = calibration

    def activate(self):
        self.schedule(100,self.wait_for_game,require_focus=False)

    def schedule(self,delay,action,require_focus=True):
        self.timer = self.root.after(delay,lambda: self.guarded(action,require_focus))

    def wait_for_game(self):
        # 使用者自行切回遊戲並放開Alt/滑鼠；穩定300ms後才啟動。
        ready = (not win32gui.IsIconic(self.hwnd)
                 and win32gui.GetForegroundWindow()==self.hwnd and not self.input_held())
        now = time.monotonic()
        if not ready:
            self.focus_since = None
        elif self.focus_since is None:
            self.focus_since = now
        elif now-self.focus_since>=.3:
            self.rect = get_client_rect(self.hwnd)
            self.started()
            self.schedule(200,self.step)
            return
        self.schedule(100,self.wait_for_game,require_focus=False)

    def input_held(self):
        return any(win32api.GetAsyncKeyState(key)&0x8000 for key in
                   (win32con.VK_LBUTTON,win32con.VK_RBUTTON,win32con.VK_SHIFT,
                    win32con.VK_CONTROL,win32con.VK_MENU))

    def check(self):
        if win32api.GetAsyncKeyState(win32con.VK_ESCAPE)&0x8000:
            raise SelectionError('已取消選色。')
        if not win32gui.IsWindow(self.hwnd) or win32gui.IsIconic(self.hwnd):
            raise SelectionError('遊戲視窗已關閉或最小化，已停止。')
        if win32gui.GetForegroundWindow()!=self.hwnd:
            raise SelectionError('遊戲未在前景，已停止選色。')
        if get_client_rect(self.hwnd)!=self.rect:
            raise SelectionError('遊戲視窗位置或尺寸改變，已停止選色。')
        if self.input_held():
            raise SelectionError('偵測到滑鼠按鍵或修飾鍵仍按住，已停止選色。')

    def guarded(self,action,require_focus=True):
        self.timer = None
        if self.done:
            return
        try:
            with physical_coordinates():
                if require_focus:
                    self.check()
                else:
                    if win32api.GetAsyncKeyState(win32con.VK_ESCAPE)&0x8000:
                        raise SelectionError('已取消選色。')
                    if not win32gui.IsWindow(self.hwnd):
                        raise SelectionError('遊戲視窗已關閉，已停止。')
                action()
        except Exception as error:
            self.finish(f'選色停止：{error}')

    def step(self):
        image,rect = grab_client(self.hwnd)
        if rect!=self.rect:
            raise SelectionError('截圖時遊戲位置改變。')
        view = observe_palette(image,self.palette,self.calibration)
        action,point = self.plan.next(view)
        self.check()
        screen = (rect.left+point[0],rect.top+point[1])
        hit = win32gui.WindowFromPoint(screen)
        if win32gui.GetAncestor(hit,win32con.GA_ROOT)!=self.hwnd:
            raise SelectionError('色盤被其他視窗遮住。')
        move_physical_cursor(screen)
        time.sleep(.04)
        self.check()
        actual = physical_cursor_position()
        if max(abs(actual[i]-screen[i]) for i in (0,1))>2:
            raise SelectionError('滑鼠未到達色盤位置，可能受遊戲游標範圍限制；已停止選色。')
        hit = win32gui.WindowFromPoint(actual)
        if win32gui.GetAncestor(hit,win32con.GA_ROOT)!=self.hwnd:
            raise SelectionError('滑鼠位置被其他視窗遮住，已停止選色。')
        try:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,0,0,0,0)
            time.sleep(.06)
        finally:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,0,0,0,0)
        if action=='select':
            self.schedule(350,lambda: self.finish(f'已點選遊戲顏色 {self.plan.color.label}。'))
        else:
            self.schedule(350,self.step)

    def finish(self,message):
        if self.done:
            return
        self.done = True
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        self.finished(message)
