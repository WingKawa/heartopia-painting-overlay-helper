"""不開啟遊戲或顯示視窗，驗證實際 Tk 控制項的縮放與捲動版面。"""
import tkinter as tk
from types import SimpleNamespace
import pytest
from heartopia_overlay.assist import Assist
from heartopia_overlay.win.dpi import ensure_dpi_aware


def test_hidden_layout_scales_and_all_controls_fit_content():
    # Windows Tk 與 PhotoImage 在同一程序重建主解譯器會相互干擾；版面獨立驗證。
    import subprocess
    import sys
    subprocess.run([sys.executable,'-c',
                    "import sys; sys.path.insert(0,'src'); from tests.test_assist_layout import check_hidden_layout; check_hidden_layout()"],check=True)


def check_hidden_layout():
    ensure_dpi_aware()
    root = tk.Tk()
    root.withdraw()
    failures = []
    root.report_callback_exception = lambda *args: failures.append(args)
    app = Assist.__new__(Assist)
    app.root = root
    app.target = None
    app.overlay = tk.Toplevel(root)
    app.overlay.withdraw()
    try:
        app._build()
        root.update_idletasks()
        assert app.work_tabs.tabs()==tuple(str(page) for page in app.stage_pages.values())
        assert list(app.stage_pages)==['作品設定','疊層設定','繪畫工具']
        assert app.sync_drag.get() and app.arrow_nudge.get()
        assert app.row_entry.winfo_class()=='TEntry' and app.col_entry.winfo_class()=='TEntry'
        assert str(app.minimap).startswith(str(app.layout.panels[0]))
        assert app.layout.header.master is root and app.layout.footer.master is root
        before = app.layout.host.winfo_reqwidth()
        app.ui_scale.set("200%")
        app.resize_ui()
        root.update_idletasks()
        for name,page in app.stage_pages.items():
            app.work_tabs.select(page)
            root.update_idletasks()
            assert app.current_stage()==name
            assert int(app.work_tabs.cget('height'))>=page.winfo_reqheight()
        old_height = int(app.work_tabs.cget('height'))
        app.palette_disclosure.toggle()
        root.update_idletasks()
        assert int(app.work_tabs.cget('height'))>old_height
        assert app.layout.host.winfo_reqwidth() >= before*1.9
        from tkinter import ttk
        style = ttk.Style(root)
        selected = tuple(int(str(v)) for v in root.tk.splitlist(style.lookup('TNotebook.Tab','padding',('selected',))))
        normal = tuple(int(str(v)) for v in root.tk.splitlist(style.lookup('TNotebook.Tab','padding',('!selected',))))
        assert selected[0]>normal[0] and selected[1]>normal[1]
        # 拖曳鈕比軌道厚，且保留 slider 元素名稱以支援 Tk 的拖曳綁定。
        for slider_element,track_element,check_element,images in root._assist_control_images.values():
            slider,track,off,on = images
            assert slider.height()>track.height()*3
            assert slider_element.endswith('slider') and track_element.endswith('trough')
            assert off.width()==on.width() and off.height()==on.height()
        for inner,shell in zip(app.layout.panels,app.layout.shells):
            assert shell.winfo_reqheight() >= inner.winfo_reqheight()
        region = tuple(map(float,app.layout.view.cget("scrollregion").split()))
        assert region[2] >= app.layout.host.winfo_reqwidth()
        assert region[3] >= app.layout.host.winfo_reqheight()
        assert root.resizable() == (1,1)
        assert not failures
    finally:
        root.destroy()


def test_poll_leaves_open_dropdown_untouched():
    scheduled = []
    app = Assist.__new__(Assist)
    app.root = SimpleNamespace(_w='.',tk=SimpleNamespace(call=lambda *args: '.combo.popdown'),
                               after=lambda ms,callback: scheduled.append((ms,callback)))
    # 其餘遊戲與視窗欄位刻意不設定：下拉清單展開時不得操作它們。
    app.poll()
    assert scheduled == [(100,app.poll)]


def test_overlay_can_be_topmost_without_promoting_main_window(monkeypatch):
    import heartopia_overlay.assist as module
    from heartopia_overlay.win.window import ClientRect
    app = Assist.__new__(Assist)
    positioned = []
    app.game_selection,app.hwnd,app.handle,app.enabled = None,11,22,True
    app.rect,app.shown_geometry,app.clip = None,None,(0,0,600,400)
    app.root = SimpleNamespace(_w='.',tk=SimpleNamespace(call=lambda *args:''),
                               winfo_id=lambda:99,after=lambda *args:None)
    app.overlay = SimpleNamespace(geometry=lambda *args:None,withdraw=lambda:None)
    app.connection_text = SimpleNamespace(set=lambda *args:None)
    monkeypatch.setattr(module.win32gui,'IsWindow',lambda hwnd:True)
    monkeypatch.setattr(module.win32gui,'IsIconic',lambda hwnd:False)
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda:11)
    monkeypatch.setattr(module.win32gui,'GetAncestor',lambda *args:99)
    monkeypatch.setattr(module.win32gui,'GetWindowText',lambda hwnd:'Heartopia')
    monkeypatch.setattr(module.win32gui,'SetWindowPos',lambda hwnd,*args:positioned.append(hwnd))
    monkeypatch.setattr(module,'get_client_rect',lambda hwnd:ClientRect(0,0,1200,700))
    app.poll()
    assert positioned==[22]
    withdrawn = []
    app.overlay.withdraw = lambda:withdrawn.append(True)
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda:99)
    monkeypatch.setattr(module.win32gui,'GetWindowRect',lambda hwnd:(10,10,300,300))
    app.poll()
    assert withdrawn and positioned==[22]
    monkeypatch.setattr(module.win32gui,'GetWindowRect',lambda hwnd:(1300,0,1600,400))
    app.poll()
    assert positioned==[22,22]


def test_color_completion_does_not_restore_or_activate_main_window():
    app = Assist.__new__(Assist)
    messages = []
    # No window activation API is available: completion must only update state.
    app.root = SimpleNamespace()
    app.game_selection = object()
    app.game_color_button = SimpleNamespace(configure=lambda **kwargs:None)
    app.status = SimpleNamespace(set=messages.append)
    app.game_color_finished('完成')
    assert app.game_selection is None and messages==['完成']


def test_dialog_pause_lasts_until_parent_dialog_destroyed():
    from heartopia_overlay.assist_layout import pause_overlay_for_dialog
    app = Assist.__new__(Assist)
    hidden,scheduled,resets = [],[],[]
    app.game_selection = None
    app.overlay = SimpleNamespace(withdraw=lambda:hidden.append(True))
    app.root = SimpleNamespace(assist_app=app,after=lambda *args:scheduled.append(args))
    app.reset_drag_sync = lambda:resets.append(True)
    class Window:
        def bind(self,event,callback,**kwargs):
            self.destroy_callback = callback
    window = Window()
    pause_overlay_for_dialog(app.root,window)
    # No native game calls should happen, even when no Tk grab has been set yet.
    for _ in range(3):
        app.poll()
    assert len(hidden)==4 and len(scheduled)==3
    window.destroy_callback(SimpleNamespace(widget=object()))
    assert window in app.overlay_dialogs
    window.destroy_callback(SimpleNamespace(widget=window))
    assert not app.overlay_dialogs and resets==[True]


def test_shortcut_poll_works_without_any_detected_game(monkeypatch):
    import heartopia_overlay.assist as module
    app = Assist.__new__(Assist)
    scheduled,seen = [],[]
    app.game_selection,app.link_waiting,app.hwnd,app.handle = None,False,None,200
    app.root = SimpleNamespace(_w='.',tk=SimpleNamespace(call=lambda *args:''),winfo_id=lambda:1,
                               after=lambda ms,callback:scheduled.append((ms,callback)))
    app.poll_shortcuts = seen.append
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda:100)
    monkeypatch.setattr(module.win32gui,'GetAncestor',lambda *args:100)
    app.poll_inputs()
    assert seen==[True]
    assert scheduled==[(20,app.poll_inputs)]


def test_manual_game_link_does_not_require_game_title(monkeypatch):
    import heartopia_overlay.assist as module
    from heartopia_overlay.win.window import ClientRect
    app = Assist.__new__(Assist)
    app.game_selection,app.link_waiting,app.hwnd,app.handle,app.manual_hwnd = None,True,None,200,None
    app.root = SimpleNamespace(_w='.',tk=SimpleNamespace(call=lambda *args:''),winfo_id=lambda:1,after=lambda *args:None)
    app.link_button = SimpleNamespace(configure=lambda **kwargs:None)
    messages = []
    app.status = SimpleNamespace(set=messages.append)
    app.poll_shortcuts = lambda relevant:None
    app.attach = lambda:setattr(app,'hwnd',app.manual_hwnd)
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda:777)
    monkeypatch.setattr(module.win32gui,'GetAncestor',lambda *args:100)
    monkeypatch.setattr(module.win32api,'GetAsyncKeyState',lambda *args:0)
    monkeypatch.setattr(module.win32gui,'GetClassName',lambda *args:'UnityWndClass')
    monkeypatch.setattr(module.win32gui,'GetWindowText',lambda *args:'Unknown regional title')
    monkeypatch.setattr(module,'get_client_rect',lambda *args:ClientRect(0,0,1600,900))
    app.poll_inputs()
    assert app.hwnd==777 and app.manual_hwnd==777 and not app.link_waiting
    assert 'Unknown regional title' in messages[-1]


def test_fast_shortcut_taps_survive_poll_interval_without_duplicate_actions(monkeypatch):
    import queue
    import heartopia_overlay.assist as module
    app = Assist.__new__(Assist)
    app.last_keys = {}
    app.game_selection = None
    events = []
    app.toggle_picker = lambda:events.append('pick')
    app.show_all = app.select_game_color = app.toggle = app.switch_mode = lambda:None
    app.picker = SimpleNamespace(shortcuts=queue.Queue())
    handles = (42,43)
    for down in (True,False,True,False):
        app.picker.shortcuts.put((handles,module.win32con.VK_F5,down))
    monkeypatch.setattr(module.win32api,'GetAsyncKeyState',lambda key:0)
    app.read_shortcut_events(handles,True)
    app.poll_shortcuts(True)
    assert events==['pick','pick']


@pytest.mark.parametrize('key,name',[(0x74,'pick'),(0x75,'all'),(0x76,'select')])
def test_color_shortcuts_require_relevant_focus_and_fire_once(monkeypatch,key,name):
    import heartopia_overlay.assist as module
    app = Assist.__new__(Assist)
    app.last_keys = {}
    events = []
    app.toggle_picker = lambda: events.append('pick')
    app.show_all = lambda: events.append('all')
    app.select_game_color = lambda: events.append('select')
    app.toggle = lambda: events.append('overlay')
    app.switch_mode = lambda: events.append('mode')
    pressed = [True]
    monkeypatch.setattr(module.win32api,'GetAsyncKeyState',lambda k: 0x8000 if pressed[0] and k==key else 0)
    app.poll_shortcuts(False)
    app.poll_shortcuts(True)
    assert not events  # 在其他程式按住快捷鍵，切回來不觸發。
    pressed[0] = False
    app.poll_shortcuts(True)
    pressed[0] = True
    app.poll_shortcuts(True)
    app.poll_shortcuts(True)
    assert events==[name]


def test_dialog_starts_at_parent_and_stays_on_parent_monitor(monkeypatch):
    from heartopia_overlay import assist_layout as layout
    monkeypatch.setattr(layout.win32api,'MonitorFromWindow',lambda *args: 1)
    monkeypatch.setattr(layout.win32api,'GetMonitorInfo',lambda m: {'Work':(0,0,3840,2100)})
    positions = []
    window = SimpleNamespace(update_idletasks=lambda:None,winfo_reqwidth=lambda:900,
                             winfo_reqheight=lambda:600,geometry=positions.append,resizable=lambda *args:None)
    parent = SimpleNamespace(update_idletasks=lambda:None,winfo_id=lambda:1,
                             winfo_x=lambda:400,winfo_y=lambda:250)
    assert layout.fit_dialog(window,parent,1200,900)==(1200,900,400,250)
    parent.winfo_x=lambda:3700
    parent.winfo_y=lambda:1950
    w,h,x,y = layout.fit_dialog(window,parent,1200,900)
    assert x+w<=3840 and y+h<=2100
    assert x>0 and y>0
