from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from heartopia_overlay.palette import Palette
from heartopia_overlay.game_color import observe_palette, SelectionError, SelectionPlan, PaletteView


def screenshot(group,size=(3840,2160)):
    # 2026-10提供的真實截圖；只保留色盤，移除遊戲其餘區域。
    image = Image.new('RGB',(3840,2160))
    with Image.open(Path(__file__).parent/'fixtures'/'game_palette'/f'group_{group:02d}.png') as crop:
        image.paste(crop,(3400,575))
    return np.asarray(image.resize(size))


@pytest.mark.parametrize('group',range(1,14))
@pytest.mark.parametrize('size',[(3840,2160),(2560,1440),(1920,1080)])
def test_actual_screenshots(group,size):
    view = observe_palette(screenshot(group,size),Palette.load())
    assert view.group==group
    for color in Palette.load().by_group(group):
        x,y = view.point(color.slot)
        assert x>size[0]*.89
        assert .36*size[1]<y<.74*size[1]
    if group<13:
        assert view.neighbor(group+1)[0]>view.chip[0]
    if group>1:
        assert view.neighbor(group-1)[0]<view.chip[0]


def test_reject_missing_palette_and_missing_white_frame():
    with pytest.raises(SelectionError):
        observe_palette(np.zeros((1440,2560,3),dtype=np.uint8),Palette.load())
    image = screenshot(8).copy()
    image[575:725] = 0
    with pytest.raises(SelectionError,match='白框'):
        observe_palette(image,Palette.load())


def test_reject_unsupported_aspect():
    with pytest.raises(SelectionError,match='16:9'):
        observe_palette(np.zeros((1000,1000,3),dtype=np.uint8),Palette.load())


def test_closed_loop_navigates_both_directions_and_stops_on_no_change():
    palette = Palette.load()
    plan = SelectionPlan(palette.by_label('13-10'))
    for group in range(1,14):
        view = PaletteView(group,3840,2160,(3589,652,82))
        action,point = plan.next(view)
        assert action==('select' if group==13 else 'navigate')
    assert point==view.point(10)
    plan = SelectionPlan(palette.by_label('1-5'))
    for group in range(13,0,-1):
        action,point = plan.next(PaletteView(group,3840,2160,(3589,652,82)))
    assert action=='select'
    plan = SelectionPlan(palette.by_label('9-5'))
    view = PaletteView(2,3840,2160,(3589,652,82))
    plan.next(view)
    with pytest.raises(SelectionError,match='預期'):
        plan.next(view)


def test_same_group_selects_exact_slot_without_navigation():
    for color in Palette.load().colors:
        view = PaletteView(color.group,3840,2160,(3589,652,82))
        assert SelectionPlan(color).next(view)==('select',view.point(color.slot))


@pytest.fixture
def controller(monkeypatch):
    from types import SimpleNamespace
    from contextlib import nullcontext
    import heartopia_overlay.game_color_control as module
    from heartopia_overlay.win.window import ClientRect
    rect = ClientRect(0,0,3840,2160)
    clicks,messages,scheduled = [],[],[]
    monkeypatch.setattr(module,'get_client_rect',lambda hwnd: rect)
    monkeypatch.setattr(module,'physical_coordinates',nullcontext)
    monkeypatch.setattr(module.win32gui,'IsWindow',lambda hwnd: True)
    monkeypatch.setattr(module.win32gui,'IsIconic',lambda hwnd: False)
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda: 42)
    monkeypatch.setattr(module.win32gui,'WindowFromPoint',lambda point: 42)
    monkeypatch.setattr(module.win32gui,'GetAncestor',lambda *args: 42)
    monkeypatch.setattr(module.win32api,'GetAsyncKeyState',lambda key: 0)
    position = [None]
    def move(point):
        position[0] = point
        clicks.append(('move',point))
    monkeypatch.setattr(module,'move_physical_cursor',move)
    monkeypatch.setattr(module,'physical_cursor_position',lambda: position[0])
    monkeypatch.setattr(module.win32api,'mouse_event',lambda kind,*args: clicks.append(('event',kind)))
    monkeypatch.setattr(module.time,'sleep',lambda seconds: None)
    root = SimpleNamespace(after=lambda ms,fn: scheduled.append(fn) or len(scheduled),
                           after_cancel=lambda timer: None)
    control = module.GameColorControl(root,42,Palette.load().by_label('2-7'),Palette.load(),messages.append)
    return module,control,rect,clicks,messages,scheduled


def test_control_navigates_then_clicks_once_and_restores(controller,monkeypatch):
    module,control,rect,clicks,messages,scheduled = controller
    images = iter([screenshot(1),screenshot(2)])
    monkeypatch.setattr(module,'grab_client',lambda hwnd: (next(images),rect))
    control.guarded(control.step)
    scheduled.pop(0)()
    scheduled.pop(0)()
    assert control.done
    assert len([c for c in clicks if c[0]=='move'])==2
    assert '2-7' in messages[0]


@pytest.mark.parametrize('reason',['focus','escape','resize'])
def test_control_stops_before_input(controller,monkeypatch,reason):
    module,control,rect,clicks,messages,scheduled = controller
    if reason=='focus':
        monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda: 99)
    elif reason=='escape':
        monkeypatch.setattr(module.win32api,'GetAsyncKeyState',lambda k: 0x8000 if k==module.win32con.VK_ESCAPE else 0)
    else:
        monkeypatch.setattr(module,'get_client_rect',lambda hwnd: None)
    control.guarded(control.step)
    assert control.done and messages and not clicks and not scheduled


def test_control_releases_button_even_if_press_fails(controller,monkeypatch):
    module,control,rect,clicks,messages,scheduled = controller
    monkeypatch.setattr(module,'grab_client',lambda hwnd: (screenshot(2),rect))
    def event(kind,*args):
        clicks.append(('event',kind))
        if kind==module.win32con.MOUSEEVENTF_LEFTDOWN:
            raise OSError('test press failure')
    monkeypatch.setattr(module.win32api,'mouse_event',event)
    control.guarded(control.step)
    assert clicks[-1]==('event',module.win32con.MOUSEEVENTF_LEFTUP)
    assert control.done and messages


def test_control_uses_saved_palette_geometry(controller,monkeypatch):
    from heartopia_overlay.palette_calibration import calibrate_palette
    module,control,rect,clicks,messages,scheduled = controller
    image = screenshot(2)
    calibration,_ = calibrate_palette(Image.fromarray(image),(3360,560,3830,1650),(3840,2160),Palette.load())
    control.calibration = calibration
    monkeypatch.setattr(module,'grab_client',lambda hwnd: (image,rect))
    control.guarded(control.step)
    assert clicks[0]==('move',calibration.point(7))
    assert not messages


@pytest.mark.parametrize('origin',[(0,0),(-3840,120),(3840,-200)])
def test_control_uses_game_screen_origin(controller,monkeypatch,origin):
    from heartopia_overlay.win.window import ClientRect
    module,control,_,clicks,messages,scheduled = controller
    rect = ClientRect(*origin,3840,2160)
    control.rect = rect
    monkeypatch.setattr(module,'get_client_rect',lambda hwnd: rect)
    monkeypatch.setattr(module,'grab_client',lambda hwnd: (screenshot(2),rect))
    control.guarded(control.step)
    x,y = PaletteView(2,3840,2160,()).point(7)
    assert clicks[0]==('move',(origin[0]+x,origin[1]+y))
    assert not messages


def test_activate_waits_for_user_focus_without_moving_cursor(controller,monkeypatch):
    module,control,rect,clicks,messages,scheduled = controller
    monkeypatch.setattr(module.win32gui,'SetForegroundWindow',lambda hwnd: clicks.append(('focus',hwnd)))
    focus,clock = [99],[0.0]
    started = []
    control.started = lambda: started.append(True)
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda: focus[0])
    monkeypatch.setattr(module.time,'monotonic',lambda: clock[0])
    control.activate()
    scheduled.pop(0)()
    assert not clicks and not messages and not started and not control.done
    focus[0] = 42
    scheduled.pop(0)()
    clock[0] = .4
    scheduled.pop(0)()
    assert started==[True]
    assert not clicks and not messages
    assert len(scheduled)==1  # 下一步才開始辨識／點擊。


def test_waiting_releases_alt_and_resets_if_focus_leaves(controller,monkeypatch):
    module,control,rect,clicks,messages,scheduled = controller
    clock,held,focus = [0.0],[True],[42]
    monkeypatch.setattr(module.time,'monotonic',lambda: clock[0])
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda: focus[0])
    monkeypatch.setattr(module.win32api,'GetAsyncKeyState',
                        lambda key: 0x8000 if held[0] and key==module.win32con.VK_MENU else 0)
    control.activate()
    scheduled.pop(0)()
    assert control.focus_since is None and not control.done
    held[0] = False
    scheduled.pop(0)()
    assert control.focus_since==0
    focus[0] = 99
    clock[0] = 1
    scheduled.pop(0)()
    assert control.focus_since is None
    assert not clicks and not messages


def test_escape_cancels_while_waiting_for_game(controller,monkeypatch):
    module,control,rect,clicks,messages,scheduled = controller
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda: 99)
    monkeypatch.setattr(module.win32api,'GetAsyncKeyState',lambda key: 0x8000 if key==module.win32con.VK_ESCAPE else 0)
    control.activate()
    scheduled.pop(0)()
    assert control.done and '取消' in messages[0] and not clicks and not scheduled


def test_control_does_not_click_when_cursor_is_clipped(controller,monkeypatch):
    module,control,rect,clicks,messages,scheduled = controller
    monkeypatch.setattr(module,'grab_client',lambda hwnd: (screenshot(2),rect))
    monkeypatch.setattr(module,'physical_cursor_position',lambda: (5000,800))
    control.guarded(control.step)
    assert control.done
    assert '未到達' in messages[0]
    assert all(kind!='event' for kind,value in clicks)


def test_physical_context_restored_after_error(monkeypatch):
    import ctypes
    from heartopia_overlay.win.dpi import physical_coordinates
    calls = []
    def set_context(value):
        calls.append(value)
        return 123
    monkeypatch.setattr(ctypes.windll.user32,'SetThreadDpiAwarenessContext',set_context)
    with pytest.raises(RuntimeError):
        with physical_coordinates():
            raise RuntimeError('test')
    assert calls[0].value==ctypes.c_void_p(-4).value
    assert calls[1]==123
