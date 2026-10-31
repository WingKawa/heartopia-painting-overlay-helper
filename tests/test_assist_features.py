import queue
from types import SimpleNamespace
import tkinter as tk
import pytest
from heartopia_overlay.assist import Assist
from heartopia_overlay.errors import GameWindowError
from heartopia_overlay.target import TargetGrid
from heartopia_overlay.palette import Palette
from heartopia_overlay.win.dpi import ensure_dpi_aware


@pytest.mark.parametrize('fields,expected',[
    ({},False),
    ({'auto_color_enabled':True},False),
    ({'auto_color_enabled':True,'auto_color_notice_version':0},False),
    ({'auto_color_enabled':True,'auto_color_notice_version':1},True),
    ({'auto_color_enabled':False,'auto_color_notice_version':1},False),
])
def test_restore_requires_saved_consent(app,fields,expected):
    original=app.capture_session()
    source=app.target.source
    state=dict(original)
    state.pop('auto_color_enabled',None)
    state.pop('auto_color_notice_version',None)
    state.update(fields)
    try:
        app.restore_session(state,source)
        assert app.auto_color_allowed() is expected
        assert app.capture_session()['auto_color_enabled'] is expected
    finally:
        app.restore_session(original,source)


@pytest.fixture(scope='module')
def app():
    monkeypatch = pytest.MonkeyPatch()
    import heartopia_overlay.assist as module
    class SilentPicker:
        context = None
        def __init__(self):
            self.points = queue.Queue()
        def start(self):
            return True
        def close(self):
            pass
    monkeypatch.setattr(module,'ColorPicker',SilentPicker)
    def no_game():
        raise GameWindowError('test without game')
    monkeypatch.setattr(module,'find_game_hwnd',no_game)
    ensure_dpi_aware()
    root = tk.Tk()
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    instance = Assist(root,persist=False)
    instance.adopt_target(TargetGrid(4,3,[[0,1,0,None],[1,None,0,1],[None,1,None,0]]))
    root.update_idletasks()
    yield instance
    instance.close()
    monkeypatch.undo()
    assert not errors


def test_slider_keeps_gap_and_entry_synchronized(app):
    app.gap.set('16')
    app.slide_size('80')
    assert app.gap.get()=='16'
    assert float(app.cell_size.get())==80
    assert app.position.cell_size==80
    assert app.position.step_x==96
    app.cell_size.set('120')
    app.apply_pitch()
    assert app.size_slider.get()==120
    assert app.position.step_x==136


def test_canvas_preset_requires_apply_and_keeps_manual_dimensions(app):
    before = app.target.w,app.target.h
    app.canvas_presets.choice.set('3:4　76×100')
    app.canvas_presets.select()
    assert (app.canvas_width.get(),app.canvas_height.get())==('76','100')
    assert (app.target.w,app.target.h)==before
    app.apply_canvas()
    assert (app.target.w,app.target.h)==(76,100)
    app.canvas_width.set('317')
    app.canvas_height.set('83')
    app.apply_canvas()
    assert (app.target.w,app.target.h)==(317,83)
    assert app.canvas_presets.choice.get()=='自訂尺寸'


def test_overlay_pan_reuses_items_and_rebuilds_before_cache_runs_out(app):
    original_source=app.target.source
    app.canvas_custom=False
    app.adopt_target(TargetGrid(100,100,[[0]*100 for _ in range(100)]))
    app.aligning,app.pick_mode,app.selected_color=False,False,None
    app.clip=(0,0,500,300)
    app.position.left=app.position.top=0
    app.set_cell_geometry(4,36)
    app.render()
    items=app.canvas.find_all()
    first=app.canvas.coords(items[0])
    app.position.move(-25,15)
    app.render()
    assert app.render_backend=='translate' and app.canvas.find_all()==items
    moved=app.canvas.coords(items[0])
    assert moved[0]==first[0]-25 and moved[1]==first[1]+15
    app.position.move(-500,0)
    app.render()
    assert app.render_backend!='translate' and app.canvas.find_all()!=items
    app.selected_color=0
    app.render()
    assert app.canvas.find_withtag('selected_hint')
    app.adopt_target(original_source)


def test_event_drag_applies_queued_motion_once_and_discards_old_geometry(app,monkeypatch):
    from heartopia_overlay.right_drag_events import RightDragEvents
    from heartopia_overlay.win.window import ClientRect
    import heartopia_overlay.assist as module
    observer=RightDragEvents()
    rect=[ClientRect(0,0,1200,800)]
    app.hwnd=42;app.rect=rect[0];app.clip=(0,0,1000,700)
    monkeypatch.setattr(module,'get_client_rect',lambda hwnd:rect[0])
    monkeypatch.setattr(app,'check_passthrough',lambda:True)
    monkeypatch.setattr(app,'request_drag_render',lambda:None)
    app.poll_event_drag(observer,True)
    context=observer.context
    origin=app.position.left,app.position.top
    observer.event(0x204,(200,200),0,True,context)
    observer.event(0x205,(500,400),10,True,context)
    app.poll_event_drag(observer,True)
    assert (app.position.left,app.position.top)==(origin[0]+300,origin[1]+200)
    app.poll_event_drag(observer,True)
    assert (app.position.left,app.position.top)==(origin[0]+300,origin[1]+200)
    observer.event(0x204,(200,200),20,True,context)
    observer.event(0x205,(500,400),30,True,context)
    rect[0]=ClientRect(20,0,1200,800)
    app.poll_event_drag(observer,True)
    assert (app.position.left,app.position.top)==(origin[0]+300,origin[1]+200)
    app.hwnd=app.rect=None


def test_canvas_composition_and_viewport_drag_do_not_conflict(app):
    app.canvas_width.set('10')
    app.canvas_height.set('8')
    app.apply_canvas()
    app.center_image()
    assert (app.target.offset_x,app.target.offset_y)==(3,2)
    original = (app.position.left,app.position.top)
    def point(col,row):
        ox,oy,sx,sy = app.map_transform
        return SimpleNamespace(x=ox+col*sx,y=oy+row*sy)
    app.map_mode.set('擺放圖片')
    app.map_start(point(5,4))
    app.map_move(point(7,5))
    assert (app.target.offset_x,app.target.offset_y)==(5,3)
    assert (app.position.left,app.position.top)==original
    app.map_end(point(7,5))
    app.map_mode.set('瀏覽範圍')
    app.map_start(point(2,2))
    app.map_end(point(3,3))
    assert (app.target.offset_x,app.target.offset_y)==(5,3)


def test_picking_uses_canvas_offset_and_filters_all_same_color(app):
    app.target.move_image(1,1)
    app.target.resize(8,8)
    app.position.left=app.position.top=0
    app.set_cell_geometry(20,80)
    app.clip=(0,0,800,800)
    app.aligning=False
    app.pick_at(150,150)
    assert app.selected_color==0
    c = Palette.load().by_index(0)
    assert app.color_text.get()==f'{c.label}（第{c.group}組第{c.slot}個顏色）'
    assert len([item for item in app.canvas.find_all()
                if 'selected_hint' not in app.canvas.gettags(item)])==4
    # 格間留白與透明格不會改變選色。
    app.pick_at(100,100)
    assert app.selected_color==0
    app.show_all()
    assert app.selected_color is None
    assert len(app.canvas.find_all())==8


def test_explicit_canvas_survives_loading_another_image(app):
    app.canvas_width.set('12')
    app.canvas_height.set('9')
    app.apply_canvas()
    app.adopt_target(TargetGrid(1,1,[[0]]))
    assert (app.target.w,app.target.h)==(12,9)
    assert (app.target.source.w,app.target.source.h)==(1,1)


def test_explicit_picker_keeps_click_until_release_then_restores_passthrough(app):
    import win32gui
    import win32con
    app.adopt_target(TargetGrid(1,1,[[5]]))
    app.position.left=app.position.top=0
    app.clip=(0,0,800,600)
    app.set_cell_geometry(20,80)
    app.aligning=False
    app.toggle_picker()
    assert app.pick_mode
    assert not win32gui.GetWindowLong(app.handle,win32con.GWL_EXSTYLE)&win32con.WS_EX_TRANSPARENT
    event = SimpleNamespace(x=50,y=50,x_root=50,y_root=50)
    app.drag_start(event)
    assert app.selected_color==5 and app.pick_held
    assert app.pick_mode  # 按下後不可立刻穿透，放開事件也必須由疊層接住。
    app.drag_end(event)
    assert not app.pick_mode and not app.pick_held
    assert win32gui.GetWindowLong(app.handle,win32con.GWL_EXSTYLE)&win32con.WS_EX_TRANSPARENT


def test_shift_pick_queue_selects_color_without_entering_f5_mode(app,monkeypatch):
    import heartopia_overlay.assist as module
    from heartopia_overlay.win.window import ClientRect
    app.canvas_custom=False
    app.adopt_target(TargetGrid(1,1,[[5]]))
    monkeypatch.setattr(module.win32gui,'IsWindow',lambda hwnd:True)
    monkeypatch.setattr(module.win32gui,'IsIconic',lambda hwnd:False)
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda:42)
    monkeypatch.setattr(module,'get_client_rect',lambda hwnd:ClientRect(0,0,1200,800))
    app.hwnd,app.enabled,app.aligning,app.pick_mode=42,True,False,False
    app.position.left=app.position.top=0
    app.clip=(0,0,1000,700)
    app.set_cell_geometry(20,80)
    app.poll_picker()
    context=app.picker.context
    assert context is not None
    app.picker.points.put((context,(50,50)))
    app.poll_picker()
    assert app.selected_color==5 and not app.pick_mode
    app.hwnd=None


def test_invalid_canvas_does_not_change_applied_canvas(app):
    before = (app.target.w,app.target.h,app.canvas_dimensions)
    app.canvas_width.set('0')
    app.apply_canvas()
    assert (app.target.w,app.target.h,app.canvas_dimensions)==before


def test_session_restores_composition_viewport_and_controls(app,tmp_path):
    from heartopia_overlay.session import SessionStore
    app.canvas_custom=False
    app.adopt_target(TargetGrid(3,2,[[0,1,None],[1,None,0]]),'D:/missing/original.jpg')
    app.target.resize(20,10)
    app.target.move_image(-2,4)
    app.position.left,app.position.top=-1234.5,678.25
    app.set_cell_geometry(12,80)
    app.sync_drag.set(True)
    app.arrow_nudge.set(True)
    app.selected_color=1
    app.opacity.set(.65)
    app.map_mode.set('擺放圖片')
    app.theme_name.set('純黑')
    app.change_theme()
    state=app.capture_session()
    assert state['arrow_nudge'] is True
    store=SessionStore(tmp_path/'state.json')
    store.save(state)
    state,grid=store.load()
    app.target=None
    app.arrow_nudge.set(False)
    app.theme_name.set('純白')
    app.change_theme()
    app.restore_session(state,grid)
    assert (app.target.w,app.target.h)==(20,10)
    assert (app.target.offset_x,app.target.offset_y)==(-2,4)
    assert (app.position.left,app.position.top)==(-1234.5,678.25)
    assert app.position.cell_size==80 and app.position.step_x==92
    assert app.sync_drag.get() and app.selected_color==1
    assert app.opacity.get()==.65
    assert app.image_path=='D:/missing/original.jpg'
    assert app.arrow_nudge.get()
    assert app.theme_name.get()=='純黑'


def test_arrow_queue_moves_only_enabled_drawing_overlay(app,monkeypatch):
    import heartopia_overlay.assist as module
    from heartopia_overlay.win.window import ClientRect
    monkeypatch.setattr(module.win32gui,'IsWindow',lambda hwnd: True)
    monkeypatch.setattr(module.win32gui,'IsIconic',lambda hwnd: False)
    monkeypatch.setattr(module.win32gui,'GetForegroundWindow',lambda:42)
    monkeypatch.setattr(module,'get_client_rect',lambda hwnd:ClientRect(0,0,3840,2160))
    app.picker.nudges = queue.Queue()
    original = app.position.left,app.position.top
    app.hwnd,app.enabled,app.aligning,app.pick_mode = 42,True,False,False
    app.arrow_nudge.set(True)
    app.picker.nudges.put(((42,id(app.target)),(10,-1)))
    app.poll_picker()
    assert (app.position.left,app.position.top)==(original[0]+10,original[1]-1)
    app.arrow_nudge.set(False)
    app.picker.nudges.put(((42,id(app.target)),(10,-1)))
    app.poll_picker()
    assert (app.position.left,app.position.top)==(original[0]+10,original[1]-1)
    app.hwnd=None


def test_measured_grid_updates_controls_and_keeps_position(app):
    from heartopia_overlay.grid_calibration import GridMeasurement
    original = app.position.left,app.position.top
    app.apply_grid_measurement(GridMeasurement(4,36,40,10,10))
    assert float(app.gap.get())==4
    assert float(app.cell_size.get())==36
    assert app.position.step_x==app.position.step_y==40
    assert app.size_slider.get()==36
    assert (app.position.left,app.position.top)==original


def test_selected_color_has_contrast_border_and_center_dot(app):
    app.adopt_target(TargetGrid(2,1,[[0,1]]))
    app.position.left,app.position.top = 0,0
    app.clip = (0,0,200,100)
    app.set_cell_geometry(4,60)
    app.aligning,app.pick_mode = False,False
    for index in (0,1):
        app.selected_color = index
        app.render()
        markers = app.canvas.find_withtag('selected_hint')
        assert len(markers)==3
        assert [app.canvas.type(item) for item in markers]==['rectangle','rectangle','oval']
        center = app.canvas.coords(markers[-1])
        assert (center[0]+center[2])/2==32+index*64
    app.show_all()
    assert not app.canvas.find_withtag('selected_hint')
    app.aligning = True
    app.selected_color = 0
    app.render()
    assert not app.canvas.find_withtag('selected_hint')


def test_palette_calibration_saved_restored_and_reset(app,monkeypatch):
    from heartopia_overlay.palette_calibration import PaletteCalibration
    from heartopia_overlay.session import validate
    from heartopia_overlay.win.window import ClientRect
    import heartopia_overlay.assist as module
    monkeypatch.setattr(module,'find_game_hwnd',lambda:42)
    monkeypatch.setattr(module,'get_client_rect',lambda hwnd:ClientRect(0,0,3840,2160))
    result = PaletteCalibration(3840,2160,3454,3699,821,181,(3360,569,3773,731),82,125)
    app.apply_palette_calibration(result)
    assert app.palette_calibration is result
    state = validate(app.capture_session())
    source = app.target.source
    app.reset_palette_calibration()
    assert app.palette_calibration is None
    app.restore_session(state,source)
    assert app.palette_calibration.record()==result.record()
    assert '3840' in app.palette_calibration_text.get()
    app.reset_palette_calibration()


def test_stage_navigation_and_saved_opt_out_do_not_change_game_mode(app):
    original = app.aligning,app.enabled
    for page in app.stage_pages.values():
        app.work_tabs.select(page)
        app.root.update_idletasks()
        assert (app.aligning,app.enabled)==original
    app.work_tabs.select(app.stage_pages['疊層設定'])
    state = app.capture_session()
    source = app.target.source
    state['sync_drag']=False
    state['arrow_nudge']=False
    app.restore_session(state,source)
    assert app.current_stage()=='疊層設定'
    assert not app.sync_drag.get() and not app.arrow_nudge.get()
    del state['arrow_nudge']
    app.restore_session(state,source)
    assert app.arrow_nudge.get() and not app.sync_drag.get()


def test_theme_switch_preserves_artwork_and_selected_swatch(app):
    from tkinter import ttk
    from heartopia_overlay.assist_theme import THEMES, DEFAULT_THEME
    app.selected_color=1
    app.update_color_label()
    original = (app.position.left,app.position.top,app.position.step_x,
                app.aligning,app.enabled,app.target.source.cells)
    swatch = app.swatch.cget('background')
    popdown = app.root.tk.call('ttk::combobox::PopdownWindow', str(app.theme_menu))
    for name,colors in THEMES.items():
        app.theme_name.set(name)
        app.change_theme()
        app.root.update_idletasks()
        assert app.root.cget('background')==colors['bg']
        assert ttk.Style(app.root).lookup('TLabel','foreground')==colors['text']
        assert app.layout.view.cget('background')==colors['bg']
        assert app.swatch.cget('background')==swatch
        assert app.root.tk.call(str(popdown)+'.f.l','cget','-background')==colors['panel']
        assert (app.position.left,app.position.top,app.position.step_x,
                app.aligning,app.enabled,app.target.source.cells)==original
        app.selected_color=None
        app.update_color_label()
        assert app.swatch.cget('foreground')==colors['text']
        app.selected_color=1
        app.update_color_label()
    state=app.capture_session()
    del state['theme']
    app.restore_session(state,app.target.source)
    assert app.theme_name.get()==DEFAULT_THEME


def test_main_export_ignores_color_filter_and_viewport(app,tmp_path,monkeypatch):
    import heartopia_overlay.assist as module
    from heartopia_overlay.target import load_target
    app.canvas_custom = False
    app.adopt_target(TargetGrid(2,1,[[0,1]]),'picture.png')
    app.target.resize(4,3)
    app.target.move_image(1,1)
    app.selected_color = 0
    app.position.left,app.position.top = -5000,-5000
    output = tmp_path/'all.png'
    monkeypatch.setattr(module.filedialog,'asksaveasfilename',lambda **kwargs:str(output))
    app.save_image()
    saved = load_target(output,unrestricted=True)
    assert (saved.w,saved.h)==(4,3)
    assert saved.cells==[[None]*4,[None,0,1,None],[None]*4]
    assert app.selected_color==0 and app.position.left==-5000
    before = app.status.get()
    monkeypatch.setattr(module.filedialog,'asksaveasfilename',lambda **kwargs:'')
    app.save_image()
    assert app.status.get()==before


def test_html_tutorial_and_diagnostics_export_are_read_only(app,tmp_path,monkeypatch):
    import webbrowser
    from heartopia_overlay.assist_help import Diagnostics
    from heartopia_overlay import assist_help
    import zipfile
    before = app.enabled,app.aligning,app.selected_color,app.position.left,app.target.revision
    opened = []
    def open_page(url,**kwargs):
        opened.append(url)
        return True
    monkeypatch.setattr(webbrowser,'open',open_page)
    app.show_tutorial()
    assert opened[0].startswith('file:') and opened[0].endswith('/docs/guide/index.html')
    assert app.capture_session()['intro_seen'] is True
    diagnostics = Diagnostics(app)
    diagnostics.window.withdraw()
    app.root.update_idletasks()
    assert '快捷鍵' in diagnostics.text.get('1.0','end')
    output = tmp_path/'diagnostics.zip'
    monkeypatch.setattr(assist_help.filedialog,'asksaveasfilename',lambda **kwargs:str(output))
    diagnostics.export()
    with zipfile.ZipFile(output) as archive:
        assert '快捷鍵' in archive.read('diagnostics.txt').decode('utf-8')
        assert 'diagnostics_export' in archive.read('current-session.jsonl').decode('utf-8')
    diagnostics.close()
    assert (app.enabled,app.aligning,app.selected_color,app.position.left,app.target.revision)==before
