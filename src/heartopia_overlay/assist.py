"""手動繪畫疊層：拖曳、微調、取色與繪畫模式的滑鼠穿透。"""
import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import win32api
import win32con
import win32gui
from .errors import OverlayError, TargetError
from .manual_overlay import Placement
from .drag_sync import RightDragSync
from .composition import Composition
from .color_picker import ColorPicker
from .conversion_dialog import ConversionDialog
from .session import SessionStore, pack_grid
from .paths import userdata
from .palette import Palette
from .target import load_target
from .win.dpi import ensure_dpi_aware
from .win.window import find_game_hwnd, get_client_rect, screenshot_frames

KEY = "#010203"


def visible_cells(target, index, cx, cy, step, clip):
    """依圖片中心與格距，列出指定顏色在裁切範圍內的格子矩形。"""
    p = Placement(cx-target.w*step/2,cy-target.h*step/2,step,step)
    for col,row,box in p.visible(target.w,target.h,clip):
        if target.cells[row][col] == index:
            yield box


class Assist:
    def __init__(self, root, *, persist=True, session_path=None, log=None):
        self.root = root
        from .diagnostic_log import DiagnosticLog
        self.log = log or DiagnosticLog(userdata('logs') if persist else None)
        root.assist_log = self.log
        root.assist_app = self
        from .interaction_metrics import InteractionMetrics
        self.interaction_metrics = InteractionMetrics(self.record_event)
        from .version import VERSION, APP_NAME
        root.title(f"{APP_NAME} · {VERSION}")
        root.attributes("-topmost",False)
        self.palette = Palette.load()
        self.target = None
        self.image_path = None
        self.geometry_configured = False
        self.session_store = SessionStore(session_path or userdata('config','assist_state.json')) if persist else None
        self.session_timer = None
        self.session_source = None
        self.session_payload = None
        self.last_session = None
        self.canvas_custom = False
        self.canvas_dimensions = (150,150)
        self.selected_color = None
        self.pick_mode = False
        self.pick_held = False
        self.game_selection = None
        self.auto_color_notice_version = 0
        self.palette_calibration = None
        self.hwnd = None
        self.manual_hwnd = None
        self.link_waiting = False
        self.intro_seen = False
        self.last_shortcut = '尚未收到 F5～F9'
        self.right_seen = False
        self.rect = None
        self.enabled = False
        self.aligning = True
        self.drag = None
        self.last_keys = {}
        self.right_drag = RightDragSync()
        self.map_drag = None
        self.map_photo = None
        self.map_cache = None
        self.map_transform = None
        self.shown_geometry = None
        self.position = Placement(0,0,163.3,163.2)
        self.clip = (0,0,0,0)
        self.overlay = tk.Toplevel(root)
        self.overlay.withdraw()
        self.overlay.overrideredirect(True)
        self.overlay.configure(bg=KEY)
        self.overlay.attributes("-topmost",True)
        self.overlay.attributes("-transparentcolor",KEY)
        self.overlay.attributes("-alpha",.45)
        self.canvas = tk.Canvas(self.overlay,bg=KEY,highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<ButtonPress-1>",self.drag_start)
        self.canvas.bind("<B1-Motion>",self.drag_move)
        self.canvas.bind("<ButtonRelease-1>",self.drag_end)
        self.overlay.update_idletasks()
        self.handle = win32gui.GetAncestor(self.overlay.winfo_id(),win32con.GA_ROOT)
        self._build()
        self.set_style()
        self.picker = ColorPicker()
        if not self.picker.start():
            self.status.set('快捷取色／方向鍵微調無法啟用，取色請使用「取色模式」。')
        self.record_event('input_hook',error=getattr(self.picker,'error',None))
        self.record_event('display',dpi=root.winfo_fpixels('1i'),screen_width=root.winfo_screenwidth(),screen_height=root.winfo_screenheight(),
                          monitors=len(win32api.EnumDisplayMonitors()))
        self.status.trace_add('write',lambda *args:self.record_state('status',message=self.status.get()))
        self.connection_text.trace_add('write',lambda *args:self.record_state('connection',message=self.connection_text.get()))
        previous_report = root.report_callback_exception
        def report_exception(kind,error,tb):
            self.log.exception('ui_exception',error,tb)
            if not persist:
                previous_report(kind,error,tb)
            else:
                self.status.set('介面操作發生錯誤，請從「功能檢查」匯出診斷紀錄。')
        root.report_callback_exception = report_exception
        root.after_idle(self.initialize_session)
        root.protocol("WM_DELETE_WINDOW",self.close)
        root.after(100,self.poll)
        root.after(20,self.poll_inputs)
        root.after(16,self.poll_drag)
        root.after(20,self.poll_picker)

    def _build(self):
        from .assist_ui import build_assist_ui
        build_assist_ui(self)

    def record_event(self,event,**fields):
        if getattr(self,'log',None):
            self.log.record(event,**fields)

    def record_state(self,event,**fields):
        if getattr(self,'log',None):
            self.log.state(event,**fields)

    def current_stage(self):
        return self.work_tabs.tab(self.work_tabs.select(),'text')

    def stage_changed(self,event=None):
        selected = self.work_tabs.select()
        if not selected:
            return
        page = self.root.nametowidget(selected)
        self.record_state('stage',name=self.current_stage())
        height = max(1,page.winfo_reqheight())
        if int(self.work_tabs.cget('height') or 0)!=height:
            self.work_tabs.configure(height=height)
        self.root.after_idle(self.layout.refresh)

    def opacity_changed(self,*args):
        value = float(self.opacity.get())
        self.opacity_text.set(f'{value:.0%}')
        self.overlay.attributes('-alpha',value)

    def arrange_image(self):
        self.map_mode.set('擺放圖片')
        self.map_mode_changed()

    def resize_ui(self,event=None):
        percent = int(self.ui_scale.get().rstrip("%"))
        self.minimap.configure(height=round(320*self.layout.dpi*percent/100))
        self.layout.scale(percent)

    def change_theme(self,event=None):
        from .assist_theme import apply_theme
        apply_theme(self,self.theme_name.get())
        self.stage_changed()

    def set_style(self):
        style = win32gui.GetWindowLong(self.handle,win32con.GWL_EXSTYLE)
        style |= win32con.WS_EX_LAYERED | win32con.WS_EX_NOACTIVATE
        if self.aligning or getattr(self,'pick_mode',False):
            style &= ~win32con.WS_EX_TRANSPARENT
        else:
            style |= win32con.WS_EX_TRANSPARENT
        win32gui.SetWindowLong(self.handle,win32con.GWL_EXSTYLE,style)

    def check_passthrough(self):
        """繪畫時驗證實際樣式；修復當次取消拖曳，等待重新按右鍵。"""
        if self.aligning or self.pick_mode:
            return True
        required = win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE
        style = win32gui.GetWindowLong(self.handle,win32con.GWL_EXSTYLE)
        if style & required == required:
            self.record_state('overlay_passthrough',valid=True)
            return True
        self.record_event('overlay_passthrough_repair',before=style,required=required)
        self.set_style()
        actual = win32gui.GetWindowLong(self.handle,win32con.GWL_EXSTYLE)
        valid = actual & required == required
        self.record_state('overlay_passthrough',valid=valid)
        self.reset_drag_sync()
        if not valid:
            self.status.set('疊層穿透設定未能恢復，已暫停同步拖曳；請匯出診斷紀錄。')
        return False

    def attach(self):
        self.hwnd = self.resolve_game()
        rect = get_client_rect(self.hwnd)
        previous_clip = self.clip
        if self.rect is None and not self.geometry_configured:
            scale = min(rect.width/3840,rect.height/2160)
            self.gap.set(f"{16*scale:.4f}")
            self.cell_size.set(f"{147.25*scale:.4f}")
            self.set_cell_geometry(float(self.gap.get()),float(self.cell_size.get()))
        self.rect = rect
        self.clip = (round(rect.width*.194),round(rect.height*.232),
                     round(rect.width*.785),round(rect.height*.841))
        if self.target is not None and previous_clip[2]>previous_clip[0] and previous_clip!=self.clip:
            view_x = (previous_clip[0]-self.position.left)/self.position.step_x
            view_y = (previous_clip[1]-self.position.top)/self.position.step_y
            self.position.left = self.clip[0]-view_x*self.position.step_x
            self.position.top = self.clip[1]-view_y*self.position.step_y
        if self.target is not None:
            self.render()

    def resolve_game(self):
        manual = getattr(self,'manual_hwnd',None)
        return manual if manual and win32gui.IsWindow(manual) else find_game_hwnd()

    def begin_game_link(self):
        self.link_waiting = not self.link_waiting
        self.record_event('manual_link',waiting=self.link_waiting)
        self.link_button.configure(text='取消連接' if self.link_waiting else '連接遊戲視窗')
        self.status.set('請自行切回遊戲視窗，工具將連接該視窗；Esc 取消。' if self.link_waiting else '已取消連接。')

    def save_image(self):
        if self.target is None:
            self.status.set('請先載入圖片。')
            return
        from pathlib import Path
        from .image_conversion import target_image
        source = Path(self.image_path) if self.image_path else Path('作品.png')
        path = filedialog.asksaveasfilename(parent=self.root,title='另存作品圖片（全部顏色）',
                initialfile=source.stem+'_作品.png',defaultextension='.png',
                filetypes=[('PNG圖片','*.png')],confirmoverwrite=True)
        if not path:
            return
        try:
            image = self.target.export_image(self.palette) if isinstance(self.target,Composition) else target_image(self.target,self.palette)
            image.save(path,format='PNG')
            self.status.set(f'已儲存 {Path(path).name}（全部顏色，作品畫布 {image.width}×{image.height} 像素）')
        except (OSError,ValueError) as error:
            self.status.set(f'儲存失敗：{error}')

    def show_tutorial(self):
        from .assist_help import open_guide
        if open_guide(self):
            self.intro_seen = True

    def show_diagnostics(self):
        from .assist_help import Diagnostics
        Diagnostics(self)

    def pick(self):
        path = filedialog.askopenfilename(parent=self.root,filetypes=[('圖片','*.png *.jpg *.jpeg *.webp *.bmp'),('所有檔案','*.*')])
        if not path:
            return
        try:
            from pathlib import Path
            if Path(path).suffix.lower()!='.png':
                ConversionDialog(self.root,path,lambda target:self.adopt_target(target,path))
                return
            target = load_target(path,unrestricted=True)
        except TargetError:
            ConversionDialog(self.root,path,lambda target:self.adopt_target(target,path))
            return
        except (OverlayError,OSError) as e:
            messagebox.showerror("載入失敗",str(e),parent=self.root)
            return
        self.adopt_target(target,path)

    def convert_pick(self):
        path = filedialog.askopenfilename(parent=self.root,filetypes=[('圖片','*.png *.jpg *.jpeg *.webp *.bmp'),('所有檔案','*.*')])
        if path:
            ConversionDialog(self.root,path,lambda target:self.adopt_target(target,path))

    def adopt_target(self,target,path=None):
        self.record_event('image_loaded',width=target.w,height=target.h)
        try:
            self.attach()
        except (OverlayError,win32gui.error):
            width,height = self.root.winfo_screenwidth(),self.root.winfo_screenheight()
            self.clip = (round(width*.194),round(height*.232),round(width*.785),round(height*.841))
        if self.canvas_custom:
            w,h = self.canvas_dimensions
        else:
            w,h = target.w,target.h
        self.canvas_width.set(str(w))
        self.canvas_height.set(str(h))
        self.target = Composition(target,w,h)
        self.image_path = str(path) if path is not None else None
        self.selected_color = None
        self.pick_mode = False
        self.pick_button.configure(text='從疊層取色（F5）')
        self.update_color_label()
        self.map_drag = None
        self.map_cache = None
        colors = {v for row in target.cells for v in row if v is not None}
        from pathlib import Path
        name = Path(path).name if path else '圖片'
        self.info.set(f"{name} · {target.w}×{target.h} · {len(colors)} 色；畫布 {w}×{h}。")
        self.row_var.set("1")
        self.col_var.set("1")
        self.jump()
        self.enabled,self.aligning = True,True
        self.update_mode()
        self.status.set("圖片已載入，請拖曳疊層對齊。")

    def switch_mode(self):
        self.reset_drag_sync()
        self.aligning = not self.aligning
        self.drag = None
        self.pick_mode = False
        self.pick_button.configure(text='從疊層取色（F5）')
        self.update_mode()

    def update_mode(self):
        self.record_state('mode',aligning=self.aligning,overlay=self.enabled)
        self.set_style()
        current,next_mode = ("對齊","繪畫") if self.aligning else ("繪畫","對齊")
        self.mode_button.configure(text=f"{current}模式 → 切換{next_mode}（F9）")
        self.mode_text.set("對齊模式：按住左鍵拖曳疊層。" if self.aligning else
                           "繪畫模式：位置已鎖定，滑鼠直接操作遊戲；F9 解鎖。")
        self.render()

    def toggle(self):
        if self.target is None:
            self.status.set("請先載入圖片。")
            return
        self.enabled = not self.enabled
        self.record_event('overlay_toggle',enabled=self.enabled)
        self.reset_drag_sync()
        if not self.enabled:
            self.overlay.withdraw()
            self.shown_geometry = None

    def reset_drag_sync(self):
        held = bool(win32api.GetAsyncKeyState(win32con.VK_RBUTTON)&0x8000)
        self.right_drag.reset(held)
        observer = getattr(getattr(self,'picker',None),'right_drag_events',None)
        if observer is not None:
            observer.cancel()

    def close(self):
        if hasattr(self,'interaction_metrics'):
            self.interaction_metrics.flush()
        if getattr(self,'render_timer',None):
            self.root.after_cancel(self.render_timer)
            self.render_timer = None
        if self.game_selection is not None:
            self.game_selection.finish('已取消選色。')
        if self.session_timer:
            self.root.after_cancel(self.session_timer)
            self.session_timer = None
        if not self.save_session():
            messagebox.showwarning('狀態未保存','目前狀態未能寫入設定檔，這次變更不會在下次還原。',parent=self.root)
        self.picker.close()
        self.record_event('shutdown')
        self.log.close()
        self.root.destroy()

    def initialize_session(self):
        self.layout.fit()
        if self.session_store is None:
            return
        try:
            loaded = self.session_store.load()
            if loaded:
                state,source = loaded
                self.restore_session(state,source)
        except (OSError,ValueError,KeyError,TypeError,OverflowError) as e:
            self.status.set(f'無法還原上次狀態：{e}')
        self.session_timer = self.root.after(1500,self.autosave_session)
        if not self.intro_seen and self.root.winfo_viewable():
            self.show_tutorial()

    def capture_session(self):
        source = self.target.source if isinstance(self.target,Composition) else self.target
        if source is not self.session_source:
            self.session_source = source
            self.session_payload = pack_grid(source) if source else None
        size = self.position.cell_size or self.position.step_x
        target = self.target
        return {'version':1,'source':self.session_payload,'image_path':self.image_path,
                'canvas_width':target.w if target else self.canvas_dimensions[0],
                'canvas_height':target.h if target else self.canvas_dimensions[1],
                'offset_x':target.offset_x if isinstance(target,Composition) else 0,
                'offset_y':target.offset_y if isinstance(target,Composition) else 0,
                'canvas_custom':self.canvas_custom,'left':self.position.left,'top':self.position.top,
                'gap':max(0,self.position.step_x-size),'cell_size':size,'clip':list(self.clip),
                'sync_drag':self.sync_drag.get(),'enabled':self.enabled,'aligning':self.aligning,
                'arrow_nudge':self.arrow_nudge.get(),
                'auto_color_enabled':self.auto_color_enabled.get(),
                'auto_color_notice_version':self.auto_color_notice_version,
                'stage_tab':self.current_stage(),
                'intro_seen':self.intro_seen,
                'theme':self.theme_name.get(),
                'palette_calibration':self.palette_calibration.record() if self.palette_calibration else None,
                'selected_color':self.selected_color,'map_mode':self.map_mode.get(),
                'opacity':float(self.opacity.get()),'ui_scale':self.ui_scale.get(),
                'window_geometry':self.root.geometry(),'row':self.row_var.get(),'col':self.col_var.get(),
                'panel_x':self.layout.view.xview()[0],'panel_y':self.layout.view.yview()[0]}

    def restore_session(self,state,source):
        from .auto_color_notice import NOTICE_VERSION
        if self.game_selection is not None:
            self.game_selection.finish('已還原設定，已取消選色。')
        saved_notice = state.get('auto_color_notice_version',0)
        self.auto_color_notice_version = saved_notice if type(saved_notice) is int and saved_notice==NOTICE_VERSION else 0
        self.auto_color_enabled.set(state.get('auto_color_enabled') is True and self.auto_color_notice_version==NOTICE_VERSION)
        self.intro_seen = bool(state.get('intro_seen',False))
        from .assist_theme import DEFAULT_THEME, apply_theme
        apply_theme(self,state.get('theme',DEFAULT_THEME))
        self.canvas_custom = state['canvas_custom']
        self.canvas_dimensions = (state['canvas_width'],state['canvas_height'])
        self.canvas_width.set(str(state['canvas_width']))
        self.canvas_height.set(str(state['canvas_height']))
        self.target = Composition(source,*self.canvas_dimensions) if source else None
        if self.target:
            self.target.move_image(state['offset_x'],state['offset_y'])
            from pathlib import Path
            path = state.get('image_path')
            name = Path(path).name if isinstance(path,str) and path else '圖片'
            self.info.set(f'已還原 {name} · {source.w}×{source.h}；畫布 {self.target.w}×{self.target.h}。')
        self.image_path = state.get('image_path')
        self.gap.set(f"{state['gap']:g}")
        self.cell_size.set(f"{state['cell_size']:g}")
        self.set_cell_geometry(state['gap'],state['cell_size'])
        self.position.left,self.position.top = state['left'],state['top']
        self.clip = tuple(state['clip'])
        self.sync_drag.set(state['sync_drag'])
        self.arrow_nudge.set(state.get('arrow_nudge',True))
        from .palette_calibration import PaletteCalibration
        saved_palette = state.get('palette_calibration')
        self.palette_calibration = PaletteCalibration.load(saved_palette) if saved_palette else None
        self.update_palette_calibration_label()
        self.opacity.set(state['opacity'])
        self.overlay.attributes('-alpha',state['opacity'])
        self.selected_color = state['selected_color']
        self.map_mode.set(state['map_mode'])
        self.row_var.set(str(state.get('row','1')))
        self.col_var.set(str(state.get('col','1')))
        self.aligning,self.enabled = state['aligning'],state['enabled']
        tab = state.get('stage_tab','疊層設定' if self.aligning else '繪畫工具')
        if tab in self.stage_pages:
            self.work_tabs.select(self.stage_pages[tab])
        self.map_mode_changed()
        self.ui_scale.set(state['ui_scale'])
        self.resize_ui()
        # 已保存的視窗大小可還原；位置仍限制在目前螢幕工作區。
        import re
        geometry = state.get('window_geometry','')
        match = re.fullmatch(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)',geometry) if isinstance(geometry,str) else None
        if match:
            monitor = win32api.MonitorFromWindow(self.root.winfo_id(),win32con.MONITOR_DEFAULTTONEAREST)
            x0,y0,x1,y1 = win32api.GetMonitorInfo(monitor)['Work']
            w,h = min(max(320,int(match[1])),x1-x0-40),min(max(240,int(match[2])),y1-y0-80)
            x,y = max(x0+10,min(int(match[3]),x1-w-20)),max(y0+10,min(int(match[4]),y1-h-45))
            self.root.geometry(f'{w}x{h}{x:+d}{y:+d}')
        self.map_cache = None
        self.root.update_idletasks()
        for key,command in [('panel_x',self.layout.view.xview_moveto),('panel_y',self.layout.view.yview_moveto)]:
            value = state.get(key,0)
            if type(value) in (int,float) and math.isfinite(value):
                command(max(0,min(1,value)))
        self.update_color_label()
        self.update_mode()
        self.status.set('已還原上次的圖片、畫布與操作設定。')

    def save_session(self):
        if self.session_store is None:
            return True
        try:
            state = self.capture_session()
            if state!=self.last_session:
                self.session_store.save(state)
                self.last_session = state
            return True
        except (OSError,ValueError,TypeError) as e:
            self.status.set(f'無法保存目前狀態：{e}')
            return False

    def autosave_session(self):
        self.save_session()
        self.session_timer = self.root.after(1500,self.autosave_session)

    def update_color_label(self):
        self.record_state('selected_color',index=self.selected_color)
        self.update_game_color_button()
        if self.selected_color is None:
            self.color_text.set('顯示全部顏色')
            from .assist_theme import THEMES, DEFAULT_THEME
            colors = getattr(self,'theme_colors',THEMES[DEFAULT_THEME])
            self.swatch.configure(bg=colors['soft'],fg=colors['text'])
        else:
            color = self.palette.by_index(self.selected_color)
            self.color_text.set(f'{color.label}（第{color.group}組第{color.slot}個顏色）')
            self.swatch.configure(bg=color.hex,fg='white' if sum(color.rgb)<380 else 'black')

    def auto_color_allowed(self):
        from .auto_color_notice import NOTICE_VERSION
        setting = getattr(self,'auto_color_enabled',None)
        version = getattr(self,'auto_color_notice_version',0)
        return bool(setting is not None and setting.get() and type(version) is int and version==NOTICE_VERSION)

    def update_game_color_button(self):
        busy = getattr(self,'game_selection',None) is not None
        enabled = busy or (self.auto_color_allowed() and getattr(self,'selected_color',None) is not None)
        self.game_color_button.configure(state='normal' if enabled else 'disabled',
                                         text='取消等待切換' if busy else '自動切換畫筆顏色（F7）')

    def show_usage_policy(self):
        from .assist_help import open_guide
        open_guide(self,'rules-and-privacy')

    def change_auto_color(self):
        from .auto_color_notice import NOTICE_VERSION, ask_auto_color_consent
        requested = bool(self.auto_color_enabled.get())
        self.auto_color_enabled.set(False)
        if self.game_selection is not None:
            self.game_selection.finish('已停用自動選色，已取消選色。')
        if requested and self.auto_color_notice_version!=NOTICE_VERSION:
            requested = ask_auto_color_consent(self.root,self.show_usage_policy)
            if requested:
                self.auto_color_notice_version = NOTICE_VERSION
        self.auto_color_enabled.set(requested)
        self.update_game_color_button()
        self.record_event('auto_color_setting',enabled=requested,notice_version=self.auto_color_notice_version)
        saved = self.save_session()
        self.status.set(('已啟用自動選色。' if requested else '自動選色已關閉；可在遊戲內手動選色。')
                        +('' if saved else ' 本次設定未能保存。'))

    def select_game_color(self):
        if self.game_selection is not None:
            self.game_selection.finish('已取消選色。')
            return
        if not self.auto_color_allowed():
            self.status.set('自動選色尚未啟用；可在「繪畫工具」查看說明並選擇是否啟用。')
            return
        if self.selected_color is None:
            return
        from .game_color_control import GameColorControl
        try:
            hwnd = self.resolve_game()
            control = GameColorControl(self.root,hwnd,self.palette.by_index(self.selected_color),
                                       self.palette,self.game_color_finished,
                                       calibration=self.palette_calibration)
            self.game_selection = control
            self.picker.context = None
            self.overlay.withdraw()
            self.shown_geometry = None
            self.game_color_button.configure(text='取消等待切換')
            color = self.palette.by_index(self.selected_color)
            self.status.set(f'等待切回遊戲，將畫筆切換為 {color.label}。Esc 可取消。')
            control.activate()
        except Exception as error:
            if self.game_selection is not None:
                self.game_selection.finish(f'無法開始選色：{error}')
            else:
                self.status.set(f'無法開始選色：{error}')

    def calibrate_palette(self):
        from .palette_calibration_dialog import PaletteCalibrationDialog
        from .win.dpi import physical_coordinates
        try:
            with physical_coordinates():
                hwnd = self.resolve_game()
                rect = get_client_rect(hwnd)
                frames = screenshot_frames(hwnd)
            PaletteCalibrationDialog(self.root,(rect.width,rect.height),self.palette,
                                     self.apply_palette_calibration,frames=frames)
        except (OverlayError,win32gui.error) as error:
            self.status.set(f'無法開啟色盤校正：{error}')

    def update_palette_calibration_label(self):
        result = self.palette_calibration
        self.palette_calibration_text.set(f'色盤位置：已校正 {result.width}×{result.height}' if result
                                          else '色盤位置：預設16:9版面')

    def apply_palette_calibration(self,result):
        from .win.dpi import physical_coordinates
        try:
            result.validate()
            with physical_coordinates():
                rect = get_client_rect(self.resolve_game())
            if (rect.width,rect.height)!=(result.width,result.height):
                raise ValueError('遊戲解析度已改變，請重新開啟色盤校正。')
            self.palette_calibration = result
            self.update_palette_calibration_label()
            saved = self.save_session()
            self.status.set('色盤校正已套用，自動選色將使用這組位置。' if saved
                            else '色盤校正已套用，但設定未能保存；關閉前請確認設定檔可寫入。')
        except (OverlayError,win32gui.error,ValueError) as error:
            self.status.set(f'未套用色盤校正：{error}')

    def reset_palette_calibration(self):
        self.palette_calibration = None
        self.update_palette_calibration_label()
        saved = self.save_session()
        self.status.set('已恢復預設16:9色盤位置。' if saved else '已恢復預設色盤位置，但設定未能保存。')

    def game_color_finished(self,message):
        self.game_selection = None
        self.update_game_color_button()
        self.status.set(message)
        self.record_event('game_color_finished',message=message)

    def show_all(self):
        self.selected_color = None
        self.update_color_label()
        self.render()

    def toggle_picker(self):
        if self.target is None:
            self.status.set('請先載入圖片。')
            return
        if self.pick_held:
            return
        self.pick_mode = not self.pick_mode
        self.pick_button.configure(text=('取消取色' if self.pick_mode else '從疊層取色')+'（F5）')
        self.set_style()
        self.render()
        self.status.set('請點疊層上的有色格子。' if self.pick_mode else '已退出取色模式。')

    def value_at(self,col,row):
        if isinstance(self.target,Composition):
            return self.target.cell(col,row)
        return self.target.cells[row][col]

    def pick_at(self,x,y):
        if self.target is None:
            return
        cell = self.position.cell_at(x,y,self.target.w,self.target.h)
        if cell is None:
            return
        box = self.position.cell_box(*cell,self.clip)
        if not (box[0]<=x<box[2] and box[1]<=y<box[3]):
            self.status.set('格間留白不取色。')
            return
        value = self.value_at(*cell)
        if value is None:
            self.status.set('空白或透明格不取色。')
            return
        self.selected_color = value
        self.update_color_label()
        self.render()

    def poll_picker(self):
        try:
            nudge_active = (self.arrow_nudge.get() and self.game_selection is None
                            and self.enabled and not self.aligning and not self.pick_mode
                            and self.target is not None and self.hwnd
                            and not self.root.grab_current()
                            and win32gui.IsWindow(self.hwnd) and not win32gui.IsIconic(self.hwnd))
            context = (self.hwnd,id(self.target)) if nudge_active else None
            self.picker.nudge_context = context
            nudges = getattr(self.picker,'nudges',None)
            dx,dy = 0,0
            while nudges is not None and not nudges.empty():
                stamp,delta = nudges.get_nowait()
                if stamp==context and context and win32gui.GetForegroundWindow()==self.hwnd:
                    dx += delta[0]
                    dy += delta[1]
            if dx or dy:
                self.position.move(dx,dy)
                self.render()
            if (self.game_selection is None and self.target is not None and self.enabled and not self.aligning and not self.pick_mode
                    and self.hwnd and win32gui.IsWindow(self.hwnd) and not win32gui.IsIconic(self.hwnd)):
                rect = get_client_rect(self.hwnd)
                x0,y0,x1,y1 = self.clip
                stamp = (id(self.target),getattr(self.target,'revision',0),self.position.left,self.position.top,
                         self.position.step_x,self.position.step_y,self.position.cell_size)
                self.picker.context = (self.hwnd,(rect.left+x0,rect.top+y0,rect.left+x1,rect.top+y1),self.handle,stamp)
            else:
                self.picker.context = None
            while not self.picker.points.empty():
                context,point = self.picker.points.get_nowait()
                if context==self.picker.context and context is not None:
                    self.pick_at(point[0]-rect.left,point[1]-rect.top)
        except (OverlayError,win32gui.error):
            self.picker.context = None
            self.picker.nudge_context = None
            self.record_state('picker_state',available=False)
        finally:
            self.root.after(20,self.poll_picker)

    def poll_drag(self):
        try:
            down = bool(win32api.GetAsyncKeyState(win32con.VK_RBUTTON)&0x8000)
            if down:
                self.right_seen = True
            available = (self.game_selection is None and self.sync_drag.get() and self.enabled and not self.aligning
                      and not self.pick_mode
                      and self.target is not None and self.hwnd is not None
                      and win32gui.IsWindow(self.hwnd)
                      and not win32gui.IsIconic(self.hwnd))
            active = available and win32gui.GetForegroundWindow()==self.hwnd
            self.interaction_metrics.sample((down and active) or self.drag is not None)
            observer = getattr(self.picker,'right_drag_events',None)
            if observer is not None and not self.picker.error and self.picker.thread.is_alive():
                self.poll_event_drag(observer,available and not getattr(self,'overlay_dialogs',None))
                return
            self.record_state('drag_input_source',source='poll')
            if not active:
                self.right_drag.reset(down)
                self.record_state('drag_state',active=False,enabled=self.enabled,sync=self.sync_drag.get(),aligning=self.aligning,
                                  game_present=bool(self.hwnd),picker=self.pick_mode)
            else:
                if not self.check_passthrough():
                    return
                rect = get_client_rect(self.hwnd)
                point = win32api.GetCursorPos()
                x0,y0,x1,y1 = self.clip
                bounds = (rect.left+x0,rect.top+y0,rect.left+x1,rect.top+y1)
                hit = win32gui.WindowFromPoint(point)
                hit_root = win32gui.GetAncestor(hit,win32con.GA_ROOT)
                # 控制面板或其他視窗遮住繪畫區時，不當成遊戲拖曳。
                unobstructed = hit_root in (self.hwnd,self.handle)
                context = (self.hwnd,rect.left,rect.top,rect.width,rect.height)
                stable_size = self.rect and (rect.width,rect.height)==(self.rect.width,self.rect.height)
                self.record_state('drag_state',active=True,unobstructed=unobstructed,stable_size=bool(stable_size))
                if down and not getattr(self,'logged_drag',False):
                    self.logged_drag = True
                    self.drag_total = [0,0]
                    self.record_event('right_drag_start',unobstructed=unobstructed,stable_size=bool(stable_size))
                dx,dy = self.right_drag.sample(bool(unobstructed and stable_size),down,
                                                point,bounds,context)
                if dx or dy:
                    total = getattr(self,'drag_total',[0,0])
                    total[0] += dx
                    total[1] += dy
                    self.drag_total = total
                    self.position.move(dx,dy)
                    self.request_drag_render()
        except (OverlayError,win32gui.error,win32api.error) as error:
            self.record_state('drag_error',error=str(error))
            self.right_drag.reset(True)
        finally:
            if getattr(self,'logged_drag',False) and not locals().get('down',False):
                self.record_event('right_drag_end',movement=getattr(self,'drag_total',[0,0]))
                self.logged_drag = False
            self.root.after(16,self.poll_drag)

    def poll_event_drag(self,observer,active):
        self.record_state('drag_input_source',source='mouse_events')
        context = None
        if active and self.check_passthrough():
            rect = get_client_rect(self.hwnd)
            if self.rect and (rect.width,rect.height)==(self.rect.width,self.rect.height):
                x0,y0,x1,y1 = self.clip
                context = (self.hwnd,(rect.left+x0,rect.top+y0,rect.left+x1,rect.top+y1),self.handle,
                           (rect.left,rect.top,rect.width,rect.height),id(self.target))
        observer.configure(context)
        updates,overflow = observer.drain()
        if overflow:
            self.record_event('drag_event_overflow',discarded_gestures=overflow)
            observer.cancel()
            self.status.set('拖曳事件累積過多，已停止這次同步；請放開右鍵後重新拖曳。')
            return
        total_x,total_y = 0,0
        for update in updates:
            self.right_seen = True
            valid = context is not None and update['context']==context
            fields = {key:update[key] for key in ('events','event_gap_max_ms','event_duration_ms','queue_age_ms')}
            if update['started']:
                self.record_event('right_drag_start',source='mouse_events',accepted=valid,**fields)
            if valid:
                dx,dy = update['delta']
                total_x += dx
                total_y += dy
            if update['ended']:
                self.record_event('right_drag_end',source='mouse_events',accepted=valid,
                                  reason=update['reason'],movement=update['total'],**fields)
        if total_x or total_y:
            self.position.move(total_x,total_y)
            self.request_drag_render()

    def drag_start(self,event):
        if getattr(self,'pick_mode',False):
            self.pick_held = True
            self.pick_at(event.x+self.clip[0],event.y+self.clip[1])
            return
        if self.aligning:
            self.drag = (event.x_root,event.y_root,self.position.left,self.position.top)

    def drag_move(self,event):
        if self.drag and self.aligning:
            x,y,left,top = self.drag
            self.position.left,self.position.top = left+event.x_root-x,top+event.y_root-y
            self.request_drag_render()

    def drag_end(self,event):
        self.drag = None
        if getattr(self,'pick_held',False):
            self.pick_held = False
            self.pick_mode = False
            self.pick_button.configure(text='從疊層取色（F5）')
            self.set_style()
            self.render()

    def jump(self):
        if not self.target:
            return
        try:
            row,col = int(self.row_var.get())-1,int(self.col_var.get())-1
            if not 0<=row<self.target.h or not 0<=col<self.target.w:
                raise ValueError("列／欄超出圖片範圍")
            self.position.left = self.clip[0]+40-col*self.position.step_x
            self.position.top = self.clip[1]+40-row*self.position.step_y
            self.render()
        except ValueError as e:
            self.status.set(f"無法跳轉：{e}")

    def calibrate_grid(self):
        from .grid_calibration_dialog import GridCalibrationDialog
        from .win.dpi import physical_coordinates
        try:
            with physical_coordinates():
                hwnd = self.resolve_game()
                rect = get_client_rect(hwnd)
                frames = screenshot_frames(hwnd)
            dimensions = rect.width,rect.height
            GridCalibrationDialog(self.root,dimensions,
                                  lambda result:self.apply_grid_measurement(result,dimensions),frames=frames)
        except (OverlayError,win32gui.error) as error:
            self.status.set(f'無法開啟格線校正：{error}')

    def apply_grid_measurement(self,result,client_size=None):
        if client_size is not None:
            from .win.dpi import physical_coordinates
            try:
                with physical_coordinates():
                    rect = get_client_rect(self.resolve_game())
                if (rect.width,rect.height)!=client_size:
                    self.status.set('遊戲解析度已改變，未套用校正；請重新開啟校正視窗。')
                    return
            except (OverlayError,win32gui.error) as error:
                self.status.set(f'未套用校正：{error}')
                return
        self.gap.set(f'{result.gap:.4f}')
        self.cell_size.set(f'{result.size:.4f}')
        self.apply_pitch()
        self.status.set('格線量測已套用；請拖曳或使用方向鍵確認疊層位置。')

    def apply_pitch(self):
        try:
            gap,size = float(self.gap.get()),float(self.cell_size.get())
            if not math.isfinite(gap) or not 0<=gap<=1000:
                raise ValueError("格距須介於 0～1000")
            if not math.isfinite(size) or not 1<=size<=1000:
                raise ValueError("格子寬高須介於 1～1000")
            self.set_cell_geometry(gap,size)
            self.size_guard = True
            self.size_slider.set(size)
            self.size_guard = False
            self.render()
            self.status.set("格子尺寸已套用，請確認疊層對齊。")
        except ValueError as e:
            self.status.set(f"格距無效：{e}")

    def set_cell_geometry(self,gap,size):
        self.geometry_configured = True
        self.position.step_x = self.position.step_y = gap+size
        self.position.cell_size = size

    def size_entry_changed(self,*args):
        if getattr(self,'size_guard',False):
            return
        try:
            value = float(self.cell_size.get())
            if math.isfinite(value) and 1<=value<=1000:
                self.size_guard = True
                self.size_slider.set(value)
                self.size_guard = False
        except ValueError:
            pass

    def slide_size(self,value):
        if getattr(self,'size_guard',False):
            return
        try:
            gap = float(self.gap.get())
            if not math.isfinite(gap) or not 0<=gap<=1000:
                return
            size = round(float(value),2)
            self.size_guard = True
            self.cell_size.set(f'{size:g}')
            self.size_guard = False
            self.set_cell_geometry(gap,size)
            self.render()
        except ValueError:
            pass

    def apply_canvas(self):
        try:
            w,h = int(self.canvas_width.get()),int(self.canvas_height.get())
            if w<1 or h<1:
                raise ValueError('畫布寬高必須是正整數')
            self.canvas_custom = True
            self.canvas_dimensions = (w,h)
            if self.target is not None:
                self.target.resize(w,h)
                self.map_drag = None
                self.map_cache = None
                self.render()
            self.status.set(f'畫布已設為 {w}×{h} 格。')
        except ValueError as e:
            self.status.set(str(e))

    def center_image(self):
        if isinstance(self.target,Composition):
            self.target.center()
            self.render()

    def reset_image(self):
        if isinstance(self.target,Composition):
            self.target.move_image(0,0)
            self.render()

    def map_mode_changed(self):
        self.map_drag = None
        if self.map_mode.get()=='擺放圖片':
            self.image_actions.pack(fill='x',pady=4,before=self.map_jump)
            self.map_help.set('拖曳圖片調整構圖；觀看框的位置保持不變。')
        else:
            self.image_actions.pack_forget()
            self.map_help.set('拖曳青色框或點選小地圖，移動觀看範圍。')
        self.render_minimap()

    def request_drag_render(self):
        if getattr(self,'render_timer',None) is None:
            self.render_requested_at = time.perf_counter()
            self.render_timer = self.root.after(16,self.flush_drag_render)

    def flush_drag_render(self):
        self.render_timer = None
        if hasattr(self,'interaction_metrics'):
            self.interaction_metrics.wait((time.perf_counter()-self.render_requested_at)*1000)
        self.render()

    def render(self):
        started = time.perf_counter()
        self.render_visible_cells = 0
        self.render_backend = 'none'
        try:
            self._render_overlay()
        finally:
            if hasattr(self,'interaction_metrics'):
                self.interaction_metrics.render((time.perf_counter()-started)*1000,
                                                self.render_visible_cells,self.render_backend)

    def _render_overlay(self):
        if getattr(self,'render_timer',None):
            self.root.after_cancel(self.render_timer)
            self.render_timer = None
        if hasattr(self,'save_image_button'):
            self.save_image_button.configure(state='normal' if self.target is not None else 'disabled')
        if hasattr(self,'overlay_button'):
            self.overlay_button.configure(text='隱藏疊層（F8）' if getattr(self,'enabled',False) else '顯示疊層（F8）')
        if not self.target:
            self.canvas.delete('all')
            self._overlay_cache = None
            return
        x0,y0,x1,y1 = self.clip
        signature = (id(self.target),getattr(self.target,'revision',0),self.clip,
                     self.position.step_x,self.position.step_y,self.position.cell_size,
                     self.aligning,self.pick_mode,self.selected_color,
                     self.ui_scale.get() if hasattr(self,'ui_scale') else None)
        cache = getattr(self,'_overlay_cache',None)
        if cache and cache['signature']==signature:
            dx,dy = self.position.left-cache['origin'][0],self.position.top-cache['origin'][1]
            if abs(dx)<=cache['margin'] and abs(dy)<=cache['margin']:
                self.canvas.move('all',dx-cache['shift'][0],dy-cache['shift'][1])
                cache['shift'] = dx,dy
                self.render_backend = 'translate'
                self.render_visible_cells = self.count_visible_cells()
                self.render_minimap()
                return
        self.canvas.delete('all')
        margin = min(256,max(128,round(2*max(self.position.step_x,self.position.step_y))))
        draw_clip = x0-margin,y0-margin,x1+margin,y1+margin
        self._overlay_cache = dict(signature=signature,origin=(self.position.left,self.position.top),
                                   margin=margin,shift=(0,0))
        # 對齊模式的背景提供可抓取區域；透明格與空白區也能拖曳。
        self.canvas.configure(bg="#303030" if self.aligning or getattr(self,'pick_mode',False) else KEY)
        cells = list(self.position.visible(self.target.w,self.target.h,draw_clip))
        self.render_visible_cells = self.count_visible_cells()
        from .overlay_raster import use_raster
        raster = use_raster(len(cells),draw_clip,self.aligning,
                            self.selected_color is not None and not self.pick_mode)
        self.render_backend = 'raster' if raster else 'canvas'
        if raster:
            from PIL import ImageTk
            from .overlay_raster import render_overlay
            image = render_overlay(self.position,draw_clip,cells,self.value_at,self.palette,self.aligning,
                                   self.pick_mode,self.selected_color,KEY)
            self.overlay_photo = ImageTk.PhotoImage(image,master=self.root)
            self.canvas.create_image(-margin,-margin,image=self.overlay_photo,anchor='nw',tags='raster_overlay')
            self.render_minimap()
            return
        self.overlay_photo = None
        for col,row,box in cells:
            value = self.value_at(col,row)
            show = value is not None and (getattr(self,'selected_color',None) is None
                    or self.aligning or getattr(self,'pick_mode',False) or value==self.selected_color)
            coords = (box[0]-x0,box[1]-y0,box[2]-x0,box[3]-y0)
            if show:
                color = self.palette.by_index(value).hex
                block = self.position.cell_box(col,row,draw_clip)
                if block[0]<block[2] and block[1]<block[3]:
                    self.canvas.create_rectangle(block[0]-x0,block[1]-y0,block[2]-x0,block[3]-y0,
                                                 fill=color,outline=color,width=0)
                    if (value==getattr(self,'selected_color',None) and not self.aligning
                            and not getattr(self,'pick_mode',False)):
                        self.draw_selected_marker(col,row)
            if self.aligning:
                self.canvas.create_rectangle(*coords,outline="#aaaaaa",width=1)
            if self.aligning:
                label_color = "white"
                if show and sum(self.palette.by_index(value).rgb)>420:
                    label_color = "black"
                self.canvas.create_text(self.position.left+(col+.5)*self.position.step_x-x0,
                                        self.position.top+(row+.5)*self.position.step_y-y0,
                                        text=f"{row+1},{col+1}",fill=label_color)
        self.render_minimap()

    def count_visible_cells(self):
        x0,y0,x1,y1 = self.clip
        p = self.position
        cols = max(0,min(self.target.w,math.ceil((x1-p.left)/p.step_x))-max(0,math.floor((x0-p.left)/p.step_x)))
        rows = max(0,min(self.target.h,math.ceil((y1-p.top)/p.step_y))-max(0,math.floor((y0-p.top)/p.step_y)))
        return cols*rows

    def draw_selected_marker(self,col,row):
        # 依完整格子定位；由Canvas裁切邊緣，避免半格出現假的邊框或中心點。
        size = self.position.cell_size or min(self.position.step_x,self.position.step_y)
        left = self.position.left+col*self.position.step_x+(self.position.step_x-size)/2-self.clip[0]
        top = self.position.top+row*self.position.step_y+(self.position.step_y-size)/2-self.clip[1]
        if size>=8:
            width = min(4,max(1,size*.025))
            inset = width+1
            box = left+inset,top+inset,left+size-inset,top+size-inset
            self.canvas.create_rectangle(*box,outline='#111111',width=width+2,tags='selected_hint')
            self.canvas.create_rectangle(*box,outline='white',width=width,tags='selected_hint')
        if size>=8:
            cx,cy = left+size/2,top+size/2
            radius = min(size*.30,max(5,min(7,size*.10)))
            self.canvas.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
                                    fill='white',outline='#111111',width=2 if size>=16 else 1,
                                    tags='selected_hint')

    def render_minimap(self):
        if not self.target:
            return
        from PIL import Image, ImageTk
        width,height = max(1,self.minimap.winfo_width()),max(1,self.minimap.winfo_height())
        if width < 10 or height < 10:
            return
        scale = min((width-12)/self.target.w,(height-12)/self.target.h)
        iw,ih = max(1,round(self.target.w*scale)),max(1,round(self.target.h*scale))
        # 四邊留白；非正方形原圖維持比例，拖曳座標使用同一個換算。
        sx,sy = iw/self.target.w,ih/self.target.h
        ox,oy = (width-iw)/2,(height-ih)/2
        self.map_transform = (ox,oy,sx,sy)
        selected = getattr(self,'selected_color',None)
        cache = (id(self.target),getattr(self.target,'revision',0),selected,iw,ih,width,height)
        if self.map_cache != cache:
            composition = self.target if isinstance(self.target,Composition) else Composition(self.target,self.target.w,self.target.h)
            image = composition.preview(self.palette,(iw,ih),selected_color=selected)
            self.map_photo = ImageTk.PhotoImage(image,master=self.root)
            self.minimap.delete("all")
            self.minimap.create_image(ox,oy,image=self.map_photo,anchor="nw")
            self.map_cache = cache
        self.minimap.delete('image_bounds')
        if isinstance(self.target,Composition) and self.map_mode.get()=='擺放圖片':
            p = self.target
            left,top = max(0,p.offset_x),max(0,p.offset_y)
            right,bottom = min(p.w,p.offset_x+p.source.w),min(p.h,p.offset_y+p.source.h)
            if left<right and top<bottom:
                self.minimap.create_rectangle(ox+left*sx,oy+top*sy,ox+right*sx,oy+bottom*sy,
                                               outline='#ff9b25',width=2,tags='image_bounds')
        self.minimap.delete("viewport")
        x0,y0,x1,y1 = self.position.viewport(self.clip)
        left,top,right,bottom = max(0,x0),max(0,y0),min(self.target.w,x1),min(self.target.h,y1)
        if left < right and top < bottom:
            box = (ox+left*sx,oy+top*sy,ox+right*sx,oy+bottom*sy)
            self.minimap.create_rectangle(*box,outline="black",width=5,tags="viewport")
            self.minimap.create_rectangle(*box,outline="#00ffff",width=2,tags="viewport")
            self.map_text.set(f"疊層可見範圍：\n第 {math.floor(top)+1}～{math.ceil(bottom)} 列\n"
                              f"第 {math.floor(left)+1}～{math.ceil(right)} 欄\n青色框線＝目前顯示區域")
        else:
            self.map_text.set("疊層目前在圖片外；點小地圖可找回。")

    def map_point(self,event):
        if not self.target or not self.map_transform:
            return None
        ox,oy,sx,sy = self.map_transform
        return ((event.x-ox)/sx,(event.y-oy)/sy)

    def map_start(self,event):
        point = self.map_point(event)
        if point is None:
            return
        col,row = point
        if not (0 <= col <= self.target.w and 0 <= row <= self.target.h):
            return
        if isinstance(self.target,Composition) and self.map_mode.get()=='擺放圖片':
            self.map_drag = ('image',col,row,self.target.offset_x,self.target.offset_y)
            return
        x0,y0,x1,y1 = self.position.viewport(self.clip)
        if x0 <= col <= x1 and y0 <= row <= y1:
            self.map_drag = (col-x0,row-y0)
        else:
            self.map_drag = ((x1-x0)/2,(y1-y0)/2)
            self.map_move(event)

    def map_move(self,event):
        point = self.map_point(event)
        if point is None or self.map_drag is None:
            return
        col,row = point
        if self.map_drag[0]=='image':
            _,start_x,start_y,left,top = self.map_drag
            self.target.move_image(left+round(col-start_x),top+round(row-start_y))
            self.render()
            return
        self.position.navigate(col-self.map_drag[0],row-self.map_drag[1],self.clip,
                               self.target.w,self.target.h)
        self.render()

    def map_end(self,event):
        if self.map_drag is not None:
            self.map_move(event)
        self.map_drag = None

    def poll_shortcuts(self,relevant):
        for key,action in [(win32con.VK_F5,self.toggle_picker),(win32con.VK_F6,self.show_all),
                           (win32con.VK_F7,self.select_game_color),
                           (win32con.VK_F8,self.toggle),(win32con.VK_F9,self.switch_mode)]:
            down = bool(win32api.GetAsyncKeyState(key)&0x8000)
            if relevant and down and not self.last_keys.get(key,False):
                self.record_event('shortcut',key=f'F{key-win32con.VK_F1+1}',source='poll')
                self.last_shortcut = f'已收到 F{key-win32con.VK_F1+1}'
                action()
            self.last_keys[key] = down

    def read_shortcut_events(self,handles,relevant):
        """讀取攔截器記下的短按；GetAsyncKeyState 仍作為攔截器失效時的備援。"""
        picker = self.picker
        picker.shortcut_context = handles if relevant else None
        events = getattr(picker,'shortcuts',None)
        actions = {win32con.VK_F5:self.toggle_picker,win32con.VK_F6:self.show_all,
                   win32con.VK_F7:self.select_game_color,win32con.VK_F8:self.toggle,win32con.VK_F9:self.switch_mode}
        while events is not None and not events.empty():
            context,key,down = events.get_nowait()
            if relevant and context==handles and key in actions:
                if down and not self.last_keys.get(key,False):
                    self.record_event('shortcut',key=f'F{key-win32con.VK_F1+1}',source='hook')
                    self.last_shortcut = f'已收到 F{key-win32con.VK_F1+1}'
                    self.last_keys[key] = True
                    actions[key]()
                    if self.game_selection is not None:
                        break
                else:
                    self.last_keys[key] = down

    def poll_inputs(self):
        """快捷鍵獨立於遊戲偵測，20ms 檢查，避免短按被100ms視窗更新漏掉。"""
        try:
            if self.game_selection is not None or self.root.tk.call('grab','current',self.root._w):
                if hasattr(self,'picker'):
                    self.read_shortcut_events((),False)
                self.poll_shortcuts(False)
                return
            foreground = win32gui.GetForegroundWindow()
            own = win32gui.GetAncestor(self.root.winfo_id(),win32con.GA_ROOT)
            if self.link_waiting:
                if hasattr(self,'picker'):
                    self.read_shortcut_events((),False)
                if win32api.GetAsyncKeyState(win32con.VK_ESCAPE)&0x8000:
                    self.begin_game_link()
                elif foreground and foreground not in (own,self.handle):
                    candidate = get_client_rect(foreground)
                    kind = win32gui.GetClassName(foreground)
                    if candidate.width>=320 and candidate.height>=240 and kind not in ('Progman','WorkerW','Shell_TrayWnd'):
                        previous = self.manual_hwnd
                        self.manual_hwnd = foreground
                        try:
                            self.attach()
                        except (OverlayError,win32gui.error):
                            self.manual_hwnd = previous
                            raise
                        self.link_waiting = False
                        self.link_button.configure(text='連接遊戲視窗')
                        self.status.set('已連接遊戲視窗：'+win32gui.GetWindowText(foreground))
                self.poll_shortcuts(False)
                return
            relevant = foreground in (own,self.handle,self.hwnd)
            if hasattr(self,'picker'):
                self.read_shortcut_events(tuple(handle for handle in (own,self.handle,self.hwnd) if handle),relevant)
            self.poll_shortcuts(relevant and self.game_selection is None)
        except (OverlayError,win32gui.error,win32api.error) as error:
            self.connection_text.set(f'輸入檢查失敗：{error}')
        finally:
            self.root.after(20,self.poll_inputs)

    def poll(self):
        if getattr(self,'game_selection',None) is not None:
            self.root.after(100,self.poll)
            return
        try:
            if getattr(self,'overlay_dialogs',None):
                self.overlay.withdraw()
                self.shown_geometry = None
                self.record_state('overlay_visibility',visible=False,reason='dialog_open')
                self.root.after(100,self.poll)
                return
            # Combobox 的下拉清單會取得 Tk grab；期間不得重排原生視窗堆疊，
            # 否則清單可能被蓋住或立即收起。也涵蓋其他 Tk 模態選單。
            if self.root.tk.call("grab","current",self.root._w):
                self.root.after(100,self.poll)
                return
            if self.hwnd is None or not win32gui.IsWindow(self.hwnd):
                self.attach()
            current = get_client_rect(self.hwnd)
            foreground = win32gui.GetForegroundWindow()
            own = win32gui.GetAncestor(self.root.winfo_id(),win32con.GA_ROOT)
            relevant = foreground in (self.hwnd,own,self.handle)
            self.connection_text.set('已連接：'+win32gui.GetWindowText(self.hwnd)+('（遊戲前景）' if foreground==self.hwnd else ''))
            if self.game_selection is not None:
                self.root.after(100,self.poll)
                return
            if self.rect and (current.width,current.height)!=(self.rect.width,self.rect.height):
                self.enabled = False
                self.attach()
                self.render()
                self.status.set("解析度改變；請調整格距並對齊後再顯示。")
            else:
                self.rect = current
            if self.enabled and relevant and not win32gui.IsIconic(self.hwnd):
                x0,y0,x1,y1 = self.clip
                geometry = (current.left+x0,current.top+y0,x1-x0,y1-y0)
                covers_controls = False
                if foreground==own:
                    left,top,right,bottom = win32gui.GetWindowRect(own)
                    gx,gy,gw,gh = geometry
                    covers_controls = left<gx+gw and right>gx and top<gy+gh and bottom>gy
                if covers_controls:
                    self.overlay.withdraw()
                    self.shown_geometry = None
                    self.record_state('overlay_visibility',visible=False,reason='main_window_overlap')
                elif geometry != self.shown_geometry:
                    self.overlay.geometry(f"{geometry[2]}x{geometry[3]}{geometry[0]:+d}{geometry[1]:+d}")
                    win32gui.SetWindowPos(self.handle,win32con.HWND_TOPMOST,*geometry,
                                          win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
                    self.shown_geometry = geometry
                    self.record_state('overlay_visibility',visible=True,reason='game_or_separate_controls')
            else:
                self.overlay.withdraw()
                self.shown_geometry = None
                self.record_state('overlay_visibility',visible=False,reason='disabled_or_unrelated_window')
        except (OverlayError,win32gui.error) as error:
            self.connection_text.set(f'尚未連接遊戲：{error}；可按「連接遊戲視窗」。')
            self.overlay.withdraw()
            self.shown_geometry = None
        self.root.after(100,self.poll)


def main(log=None):
    ensure_dpi_aware()
    root = tk.Tk()
    root.tk.call("tk","scaling",root.winfo_fpixels("1i")/72)
    Assist(root,log=log)
    root.mainloop()
