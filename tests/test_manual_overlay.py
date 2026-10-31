from types import SimpleNamespace
import pytest
from heartopia_overlay.manual_overlay import Placement
from heartopia_overlay.assist import Assist


def test_huge_grid_pan_and_hit_testing():
    p = Placement(-5000,-9000,100,120)
    cells = list(p.visible(150,150,(0,0,200,240)))
    assert [(c,r) for c,r,b in cells] == [(50,75),(51,75),(50,76),(51,76)]
    assert p.cell_at(1,1,150,150) == (50,75)
    p.move(10,-20)
    assert p.cell_at(11,-19,150,150) == (50,75)
    assert p.cell_at(-6000,0,150,150) is None


def test_drag_moves_overlay_without_selecting_or_drawing_in_game():
    app = Assist.__new__(Assist)
    app.aligning = True
    app.target = object()
    app.position = Placement(100,200,163,163)
    app.render = lambda: None
    app.request_drag_render = lambda:None
    app.drag_start(SimpleNamespace(x_root=40,y_root=50))
    app.drag_move(SimpleNamespace(x_root=70,y_root=90))
    app.drag_end(SimpleNamespace(x_root=70,y_root=90))
    assert (app.position.left,app.position.top) == (130,240)
    assert app.drag is None
    app.aligning = False
    app.drag_start(SimpleNamespace(x_root=1,y_root=1))
    assert app.drag is None


def test_mode_changes_mouse_passthrough(monkeypatch):
    import win32con
    import heartopia_overlay.assist as module
    styles = []
    monkeypatch.setattr(module.win32gui,'GetWindowLong',lambda *args: win32con.WS_EX_TRANSPARENT)
    monkeypatch.setattr(module.win32gui,'SetWindowLong',lambda h,i,s: styles.append(s))
    app = Assist.__new__(Assist)
    app.handle = 123
    app.aligning = True
    app.set_style()
    assert not styles[-1] & win32con.WS_EX_TRANSPARENT
    app.aligning = False
    app.set_style()
    assert styles[-1] & win32con.WS_EX_TRANSPARENT
    assert styles[-1] & win32con.WS_EX_NOACTIVATE


def test_minimap_navigation_preserves_fine_alignment_and_clamps_edges():
    p = Placement(12.25,-3.5,163.3,163.2)
    before = (p.left,p.top)
    clip = (0,0,1000,600)
    p.navigate(70,80,clip,150,150)
    x0,y0,x1,y1 = p.viewport(clip)
    assert x0 == pytest.approx(70,abs=.5)
    assert y0 == pytest.approx(80,abs=.5)
    assert (p.left-before[0])/p.step_x == pytest.approx(round((p.left-before[0])/p.step_x))
    assert (p.top-before[1])/p.step_y == pytest.approx(round((p.top-before[1])/p.step_y))
    p.navigate(10000,-10000,clip,150,150)
    x0,y0,x1,y1 = p.viewport(clip)
    assert x1 == pytest.approx(150,abs=.5)
    assert y0 == pytest.approx(0,abs=.5)


def test_minimap_drag_retains_grab_offset_and_click_jumps():
    app = Assist.__new__(Assist)
    app.target = SimpleNamespace(w=150,h=100)
    app.position = Placement(-200,-300,20,30)
    app.clip = (0,0,200,150)
    # 以非正方形圖片驗證帶留白的小地圖座標換算。
    app.map_transform = (10,20,2,2)
    app.render = lambda: None
    app.map_drag = None
    # 可見區(10,10)-(20,15)，在第12欄12列處抓取，按下時位置不變。
    app.map_start(SimpleNamespace(x=34,y=44))
    assert app.map_drag == (2,2)
    assert (app.position.left,app.position.top) == (-200,-300)
    app.map_move(SimpleNamespace(x=54,y=64))
    assert app.position.viewport(app.clip)[:2] == (20,20)
    app.map_end(SimpleNamespace(x=54,y=64))
    assert app.map_drag is None
    # 點另一個區域會以點選處為可見區中心，而不是色彩選取。
    app.map_start(SimpleNamespace(x=170,y=120))
    x0,y0,x1,y1 = app.position.viewport(app.clip)
    assert (x0+x1)/2 == pytest.approx(80,abs=.5)
    assert (y0+y1)/2 == pytest.approx(50,abs=.5)


def test_cell_size_and_gap_are_independent_and_clipped():
    p = Placement(0,0,100,100,80)
    assert p.cell_box(0,0,(0,0,200,200)) == (10,10,90,90)
    assert p.cell_box(1,1,(0,0,160,160)) == (110,110,160,160)
    assert p.viewport((0,0,200,200)) == (0,0,2,2)


def test_apply_gap_and_square_size_updates_navigation_pitch():
    app = Assist.__new__(Assist)
    app.position = Placement(10,20,163.3,163.2)
    app.set_cell_geometry(12,80)
    assert app.position.step_x == app.position.step_y == 92
    assert app.position.cell_size == 80
    assert (app.position.left,app.position.top) == (10,20)
