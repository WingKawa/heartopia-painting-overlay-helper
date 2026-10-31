from types import SimpleNamespace
import win32con
from heartopia_overlay.assist import Assist, KEY
from heartopia_overlay.manual_overlay import Placement
from heartopia_overlay.overlay_raster import render_overlay
from heartopia_overlay.palette import Palette


def test_large_sparse_overlay_avoids_full_frame_upload():
    from heartopia_overlay.overlay_raster import use_raster
    clip=(745,501,3014,1817)
    assert not use_raster(1450,clip)
    assert not use_raster(1450,clip,selected=True)
    assert not use_raster(1450,clip,aligning=True)
    assert use_raster(8400,(0,0,1200,700))
    assert use_raster(2613,(0,0,1200,700),aligning=True)


def test_drag_render_coalesces_without_dropping_position_updates():
    app = Assist.__new__(Assist)
    pending,drawn = [],[]
    app.root = SimpleNamespace(after=lambda delay,callback:pending.append(callback) or 1)
    app.position = Placement(0,0,10,10)
    app.render = lambda:drawn.append((app.position.left,app.position.top))
    for _ in range(100):
        app.position.move(2,3)
        app.request_drag_render()
    assert len(pending)==1 and not drawn
    pending.pop()()
    assert drawn==[(200,300)] and app.render_timer is None


def test_passthrough_repair_requires_new_drag_and_verifies_result(monkeypatch):
    import heartopia_overlay.assist as module
    app = Assist.__new__(Assist)
    app.aligning=app.pick_mode=False
    app.handle=42
    required=win32con.WS_EX_LAYERED|win32con.WS_EX_TRANSPARENT|win32con.WS_EX_NOACTIVATE
    state=[win32con.WS_EX_LAYERED]
    repairs,resets,messages=[],[],[]
    monkeypatch.setattr(module.win32gui,'GetWindowLong',lambda *args:state[0])
    def set_style(*args):
        repairs.append(args[-1]);state[0]=args[-1]
    monkeypatch.setattr(module.win32gui,'SetWindowLong',set_style)
    app.reset_drag_sync=lambda:resets.append(True)
    app.status=SimpleNamespace(set=messages.append)
    assert not app.check_passthrough()
    assert state[0]&required==required and resets==[True]
    assert app.check_passthrough() and len(repairs)==1 and not messages
    state[0]=0
    monkeypatch.setattr(module.win32gui,'SetWindowLong',lambda *args:None)
    assert not app.check_passthrough() and messages
    app.pick_mode=True
    assert app.check_passthrough() and state[0]==0


def test_raster_colors_gap_filter_and_pan_are_exact():
    palette=Palette.load()
    p=Placement(-10,0,20,20,16)
    clip=(0,0,40,20)
    cells=list(p.visible(3,1,clip))
    values=[0,1,None]
    def draw(selected=None):
        return render_overlay(p,clip,cells,lambda c,r:values[c],palette,False,False,selected,KEY)
    image=draw()
    assert image.getpixel((0,5))==palette.by_index(0).rgb
    assert image.getpixel((20,5))==palette.by_index(1).rgb
    assert image.getpixel((9,5))==(1,2,3)  # gap
    assert image.getpixel((39,5))==(1,2,3)  # transparent cell
    filtered=draw(1)
    assert filtered.getpixel((0,5))==(1,2,3)
    assert filtered.getpixel((20,10))==(255,255,255)  # selected center


def test_raster_partial_selected_cell_keeps_original_center():
    palette=Palette.load()
    p=Placement(-30,-30,40,40,36)
    image=render_overlay(p,(0,0,10,10),list(p.visible(1,1,(0,0,10,10))),
                         lambda *args:0,palette,False,False,0,KEY)
    # Original center is offscreen; it must not be relocated into the clipped corner.
    assert image.getpixel((2,2))==palette.by_index(0).rgb
