"""Shift+左鍵的只讀取色攔截器，不模擬或轉送遊戲輸入。"""
import ctypes
from ctypes import wintypes
import queue
import threading
import win32api
import win32con
import win32gui
from .right_drag_events import RightDragEvents


class PickGate:
    """配對吞掉取色的按下及放開，Shift 提早放開也不漏出滑鼠事件。"""
    def __init__(self):
        self.captured = False

    def event(self,message,eligible):
        if message==0x201:
            if eligible:
                self.captured = True
                return True,True
            return False,False
        if message==0x202 and self.captured:
            self.captured = False
            return True,False
        return False,False


class ColorPicker:
    def __init__(self):
        self.context = None
        self.points = queue.Queue()
        self.nudge_context = None
        self.nudges = queue.Queue()
        self.shortcut_context = None
        self.shortcuts = queue.Queue()
        self.right_drag_events = RightDragEvents()
        self.ready = threading.Event()
        self.error = None
        self.thread_id = None
        self.thread = threading.Thread(target=self.run,daemon=True)

    def start(self):
        self.thread.start()
        self.ready.wait(2)
        return self.ready.is_set() and self.error is None

    def run(self):
        user = ctypes.windll.user32
        kernel = ctypes.windll.kernel32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,ctypes.c_size_t,ctypes.c_ssize_t)
        class MouseData(ctypes.Structure):
            _fields_ = [('pt',wintypes.POINT),('mouseData',wintypes.DWORD),
                        ('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
        class KeyData(ctypes.Structure):
            _fields_ = [('vk',wintypes.DWORD),('scan',wintypes.DWORD),
                        ('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
        user.SetWindowsHookExW.argtypes = [ctypes.c_int,callback_type,wintypes.HINSTANCE,wintypes.DWORD]
        user.SetWindowsHookExW.restype = ctypes.c_void_p
        user.CallNextHookEx.argtypes = [ctypes.c_void_p,ctypes.c_int,ctypes.c_size_t,ctypes.c_ssize_t]
        user.CallNextHookEx.restype = ctypes.c_ssize_t
        user.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel.GetModuleHandleW.restype = wintypes.HMODULE
        gate = PickGate()
        hook = None
        key_hook = None
        arrows = ArrowGate()
        functions = FunctionKeyGate()
        def process_key(code,message,data):
            if code>=0:
                sample = ctypes.cast(data,ctypes.POINTER(KeyData)).contents
                if not sample.flags&16:
                    shortcut = functions.event(message,sample.vk,self.shortcut_context,win32gui.GetForegroundWindow())
                    if shortcut is not None:
                        self.shortcuts.put(shortcut)
                context = self.nudge_context
                eligible = bool(context and not sample.flags&16
                                and win32gui.GetForegroundWindow()==context[0]
                                and not win32api.GetAsyncKeyState(win32con.VK_CONTROL)&0x8000
                                and not win32api.GetAsyncKeyState(win32con.VK_MENU)&0x8000)
                consume,delta = arrows.event(message,sample.vk,eligible,
                                             bool(win32api.GetAsyncKeyState(win32con.VK_SHIFT)&0x8000))
                if delta and context:
                    self.nudges.put((context,delta))
                if consume:
                    return 1
            return user.CallNextHookEx(key_hook,code,message,data)
        def keyboard(code,message,data):
            try:
                return process_key(code,message,data)
            except Exception:
                return user.CallNextHookEx(key_hook,code,message,data)
        def process(code,message,data):
            try:
                if code>=0 and message in (0x200,0x204,0x205):
                    if message==0x200 and not self.right_drag_events.held:
                        return user.CallNextHookEx(hook,code,message,data)
                    sample = ctypes.cast(data,ctypes.POINTER(MouseData)).contents
                    if not sample.flags&1:
                        observer = self.right_drag_events
                        context = observer.context
                        eligible = bool(context and win32gui.GetForegroundWindow()==context[0])
                        if message==0x204 and eligible:
                            hit = win32gui.GetAncestor(win32gui.WindowFromPoint((sample.pt.x,sample.pt.y)),win32con.GA_ROOT)
                            eligible = hit in (context[0],context[2])
                        observer.event(message,(sample.pt.x,sample.pt.y),int(sample.time),eligible,context)
                    # 右鍵和移動只觀察，永遠交回原本的輸入鏈。
                    return user.CallNextHookEx(hook,code,message,data)
                if code>=0 and message in (0x201,0x202):
                    sample = ctypes.cast(data,ctypes.POINTER(MouseData)).contents
                    point = (sample.pt.x,sample.pt.y)
                    context = self.context
                    eligible = False
                    if message==0x201 and context and not sample.flags&1:
                        hwnd,bounds,overlay = context[:3]
                        x0,y0,x1,y1 = bounds
                        if (x0<=point[0]<x1 and y0<=point[1]<y1
                                and win32api.GetAsyncKeyState(win32con.VK_SHIFT)&0x8000
                                and win32gui.GetForegroundWindow()==hwnd):
                            hit = win32gui.GetAncestor(win32gui.WindowFromPoint(point),win32con.GA_ROOT)
                            eligible = hit in (hwnd,overlay)
                    consume,pick = gate.event(message,eligible)
                    if pick:
                        self.points.put((context,point))
                    if consume:
                        return 1
            except Exception:
                # 已攔截的 down 必須配對攔截 up，避免取色時點入遊戲。
                if code>=0 and message==0x202 and gate.captured:
                    gate.captured = False
                    return 1
            return user.CallNextHookEx(hook,code,message,data)
        self.callback = callback_type(process)
        self.key_callback = callback_type(keyboard)
        try:
            self.thread_id = kernel.GetCurrentThreadId()
            message = wintypes.MSG()
            user.PeekMessageW(ctypes.byref(message),None,0,0,0)
            hook = user.SetWindowsHookExW(14,self.callback,kernel.GetModuleHandleW(None),0)
            if not hook:
                raise OSError('無法啟用 Shift+左鍵快捷取色')
            key_hook = user.SetWindowsHookExW(13,self.key_callback,kernel.GetModuleHandleW(None),0)
            if not key_hook:
                raise OSError('無法啟用方向鍵微調')
            self.ready.set()
            while user.GetMessageW(ctypes.byref(message),None,0,0)>0:
                user.TranslateMessage(ctypes.byref(message))
                user.DispatchMessageW(ctypes.byref(message))
        except Exception as e:
            self.error = str(e)
            self.ready.set()
        finally:
            if hook:
                user.UnhookWindowsHookEx(hook)
            if key_hook:
                user.UnhookWindowsHookEx(key_hook)

    def close(self):
        self.right_drag_events.cancel()
        self.context = None
        self.nudge_context = None
        self.shortcut_context = None
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id,0x12,0,0)
        if self.thread.is_alive():
            self.thread.join(timeout=1)


class FunctionKeyGate:
    """記下短按與放開；功能鍵只觀察，不攔截或轉送給遊戲。"""
    def __init__(self):
        self.held = {}

    def event(self,message,key,context,foreground):
        if not 0x74<=key<=0x78:
            return None
        if message in (0x101,0x105):
            captured = self.held.pop(key,None)
            return (captured,key,False) if captured is not None else None
        if message in (0x100,0x104) and key not in self.held:
            captured = context if context and foreground in context else None
            self.held[key] = captured
            return (captured,key,True) if captured is not None else None
        return None


class ArrowGate:
    """成對攔截方向鍵；持續按住採Windows的按鍵重複節奏。"""
    vectors = {0x25:(-1,0),0x26:(0,-1),0x27:(1,0),0x28:(0,1)}

    def __init__(self):
        self.captured = set()

    def event(self,message,key,eligible,shift=False):
        if key not in self.vectors:
            return False,None
        if message in (0x101,0x105):
            consumed = key in self.captured
            self.captured.discard(key)
            return consumed,None
        if message in (0x100,0x104):
            if eligible:
                self.captured.add(key)
                dx,dy = self.vectors[key]
                return True,(dx*(10 if shift else 1),dy*(10 if shift else 1))
            if key in self.captured:
                return True,None
        return False,None
