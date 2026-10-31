"""工作階段排版：固定操作列、小地圖、作品／疊層／繪畫頁籤。"""
import tkinter as tk
from tkinter import ttk, messagebox
from .assist_layout import AssistLayout
from .assist_theme import THEMES, DEFAULT_THEME, apply_theme
from .size_presets import SizePresets


class Disclosure(ttk.Frame):
    def __init__(self,parent,title,changed):
        super().__init__(parent)
        self.title,self.changed,self.expanded = title,changed,False
        self.button = ttk.Button(self,text='▸ '+title,command=self.toggle)
        self.button.pack(anchor='w')
        self.body = ttk.Frame(self,padding=(0,8,0,0))

    def toggle(self):
        self.expanded = not self.expanded
        self.button.configure(text=('▾ ' if self.expanded else '▸ ')+self.title)
        if self.expanded:
            self.body.pack(fill='x')
        else:
            self.body.pack_forget()
        self.after_idle(self.changed)


def build_assist_ui(app):
    app.theme_name = tk.StringVar(value=DEFAULT_THEME)
    apply_theme(app, DEFAULT_THEME)
    app.layout = AssistLayout(app.root)
    map_panel,panel = app.layout.panels
    def note(parent,text):
        label = ttk.Label(parent,text=text,wraplength=430,justify='left',style='Note.TLabel')
        label.pack(fill='x',anchor='w',pady=(5,7))
        return label
    def section(parent,title):
        frame = ttk.LabelFrame(parent,text=title,padding=12)
        frame.pack(fill='x',pady=(0,12))
        return frame
    def row(parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='x',pady=4)
        return frame
    def help_dialog():
        messagebox.showinfo('操作說明',
            '1. 載入圖片，在「作品設定」調整畫布與圖片位置。\n'
            '2. 切換對齊模式，拖曳疊層，在「疊層設定」調整格子。\n'
            '3. 切回繪畫模式，以 Shift＋左鍵從疊層取色。\n'
            '4. 先展開遊戲色盤，按 F7 後自行切回遊戲，自動切換畫筆顏色。\n\n'
            'F5 取色模式　F6 顯示全部顏色\nF7 自動切換畫筆顏色\n'
            'F8 顯示／隱藏疊層　F9 對齊／繪畫\nEsc 取消等待或執行中的畫筆顏色切換。',parent=app.root)

    files = row(app.layout.header)
    files.columnconfigure(0,weight=1)
    app.info = tk.StringVar(value='載入圖片後，設定畫布並對齊疊層。')
    file_info = ttk.Label(files,textvariable=app.info,wraplength=650)
    file_info.grid(row=0,column=0,sticky='ew',padx=(0,8))
    file_actions = ttk.Frame(files)
    file_actions.grid(row=0,column=1,sticky='w')
    ttk.Button(file_actions,text='載入圖片',command=app.pick).pack(side='left',padx=4)
    app.save_image_button = ttk.Button(file_actions,text='另存圖片…',command=app.save_image,state='disabled')
    app.save_image_button.pack(side='left',padx=4)
    ttk.Button(file_actions,text='轉為小鎮125色…',command=app.convert_pick).pack(side='left',padx=4)
    ttk.Button(file_actions,text='使用教學',command=app.show_tutorial).pack(side='left',padx=4)
    app.link_button = ttk.Button(file_actions,text='連接遊戲視窗',command=app.begin_game_link)
    app.link_button.pack(side='left',padx=4)
    ttk.Button(file_actions,text='功能檢查',command=app.show_diagnostics).pack(side='left',padx=4)
    file_buttons = file_actions.winfo_children()
    for button in file_buttons:
        button.pack_forget()
    for index,button in enumerate(file_buttons):
        button.grid(row=0,column=index,padx=4,pady=3,sticky='w')
    def file_resize(event):
        natural = sum(button.winfo_reqwidth()+8 for button in file_buttons)
        stacked = event.width<natural+250
        file_info.grid_configure(columnspan=2 if stacked else 1)
        file_actions.grid_configure(row=1 if stacked else 0,column=0 if stacked else 1,columnspan=2 if stacked else 1,sticky='ew' if stacked else 'w')
        row_index,column_index,used = 0,0,0
        available = max(100,event.width-20) if stacked else natural
        for button in file_buttons:
            button_width = button.winfo_reqwidth()+8
            if used and used+button_width>available:
                row_index,column_index,used = row_index+1,0,0
            button.grid_configure(row=row_index,column=column_index)
            used += button_width
            column_index += 1
        width = max(100,event.width-(0 if stacked else natural)-20)
        if int(file_info.cget('wraplength'))!=width:
            file_info.configure(wraplength=width)
    files.bind('<Configure>',file_resize)
    app.connection_text = tk.StringVar(value='等待連接遊戲；未找到時可按「連接遊戲視窗」。')
    note(app.layout.header,app.connection_text.get()).configure(textvariable=app.connection_text)
    controls = row(app.layout.header)
    app.overlay_button = ttk.Button(controls,text='顯示／隱藏疊層（F8）',command=app.toggle)
    app.overlay_button.pack(side='left',padx=(0,8))
    app.mode_button = ttk.Button(controls,text='對齊模式 → 切換繪畫（F9）',command=app.switch_mode)
    app.mode_button.pack(side='left',padx=(0,10))
    app.mode_text = tk.StringVar(value='按住左鍵拖曳疊層，對齊遊戲格子。')
    ttk.Label(controls,textvariable=app.mode_text,wraplength=430).pack(side='left',fill='x',expand=True)

    map_frame = section(map_panel,'作品小地圖')
    modes = row(map_frame)
    app.map_mode = tk.StringVar(value='瀏覽範圍')
    for text,value in [('移動觀看範圍','瀏覽範圍'),('調整圖片位置','擺放圖片')]:
        ttk.Radiobutton(modes,text=text,value=value,variable=app.map_mode,
                        command=app.map_mode_changed).pack(side='left',padx=(0,10))
    app.minimap = tk.Canvas(map_frame,width=320,height=320,bg='#222222',highlightthickness=0,cursor='hand2')
    app.minimap.pack(fill='x')
    app.minimap.bind('<Configure>',lambda e:app.render_minimap())
    app.minimap.bind('<ButtonPress-1>',app.map_start)
    app.minimap.bind('<B1-Motion>',app.map_move)
    app.minimap.bind('<ButtonRelease-1>',app.map_end)
    app.map_text = tk.StringVar(value='載入圖片後顯示參考圖與可見範圍。')
    ttk.Label(map_frame,textvariable=app.map_text,wraplength=400).pack(fill='x',pady=8)
    app.image_actions = row(map_frame)
    ttk.Button(app.image_actions,text='圖片置中',command=app.center_image).pack(side='left',padx=(0,6))
    ttk.Button(app.image_actions,text='重設圖片位置',command=app.reset_image).pack(side='left')
    app.image_actions.pack_forget()
    jump = row(map_frame)
    app.map_jump = jump
    ttk.Label(jump,text='移動可見範圍').pack(anchor='w')
    inputs = row(jump)
    app.row_var,app.col_var = tk.StringVar(value='1'),tk.StringVar(value='1')
    ttk.Label(inputs,text='列').pack(side='left')
    app.row_entry = ttk.Entry(inputs,width=6,textvariable=app.row_var)
    app.row_entry.pack(side='left',padx=(4,8))
    ttk.Label(inputs,text='欄').pack(side='left')
    app.col_entry = ttk.Entry(inputs,width=6,textvariable=app.col_var)
    app.col_entry.pack(side='left',padx=(4,8))
    for entry in (app.row_entry,app.col_entry):
        entry.bind('<Return>',lambda event:app.jump())
    ttk.Button(inputs,text='移至此格',command=app.jump).pack(side='left')
    note(jump,'將可見範圍的左上角移到指定格子。')
    app.map_help = tk.StringVar(value='拖曳青色框或點選小地圖，移動觀看範圍。')
    ttk.Label(map_frame,textvariable=app.map_help,wraplength=400).pack(fill='x',pady=4)

    app.work_tabs = ttk.Notebook(panel)
    app.work_tabs.pack(fill='x')
    app.stage_pages = {}
    for title in ('作品設定','疊層設定','繪畫工具'):
        page = ttk.Frame(app.work_tabs,padding=(8,12))
        app.work_tabs.add(page,text=title)
        app.stage_pages[title] = page
    prepare,align,draw = app.stage_pages.values()
    app.work_tabs.bind('<<NotebookTabChanged>>',app.stage_changed)
    for page in app.stage_pages.values():
        page.bind('<Configure>',app.stage_changed)

    canvas = section(prepare,'作品畫布')
    app.canvas_width,app.canvas_height = tk.StringVar(value='150'),tk.StringVar(value='150')
    app.canvas_presets = SizePresets(canvas,app.canvas_width,app.canvas_height)
    app.canvas_presets.pack(anchor='w',pady=(0,6))
    dims = row(canvas)
    for label,var in [('寬（格）',app.canvas_width),('高（格）',app.canvas_height)]:
        ttk.Label(dims,text=label).pack(side='left')
        ttk.Entry(dims,textvariable=var,width=7).pack(side='left',padx=(4,12))
    ttk.Button(canvas,text='套用畫布大小',command=app.apply_canvas).pack(anchor='w',pady=4)
    note(canvas,'超出作品畫布的圖片部分不會顯示。')
    composition = section(prepare,'圖片構圖')
    ttk.Button(composition,text='在小地圖調整圖片位置',command=app.arrange_image).pack(anchor='w')
    note(composition,'切換後拖曳圖片；觀看框的位置不受影響。')
    conversion = Disclosure(prepare,'轉為小鎮125色',app.stage_changed)
    conversion.pack(fill='x')
    note(conversion.body,'將一般圖片轉為小鎮可用的125色像素圖，可調整輸出尺寸與裁切範圍。')
    ttk.Button(conversion.body,text='開啟125色轉換…',command=app.convert_pick).pack(anchor='w')

    geometry = section(align,'格子大小與間距')
    app.gap,app.cell_size = tk.StringVar(value='16'),tk.StringVar(value='147.25')
    size_row = row(geometry)
    ttk.Label(size_row,text='格子寬高（px）').pack(side='left')
    ttk.Entry(size_row,textvariable=app.cell_size,width=10).pack(side='right')
    app.size_slider = tk.DoubleVar(value=147.25)
    app.size_bar = ttk.Scale(geometry,from_=1,to=1000,variable=app.size_slider,command=app.slide_size)
    app.size_bar.pack(fill='x',pady=6)
    app.size_guard = False
    app.cell_size.trace_add('write',app.size_entry_changed)
    gap_row = row(geometry)
    ttk.Label(gap_row,text='格距／格間留白（px）').pack(side='left')
    ttk.Entry(gap_row,textvariable=app.gap,width=10).pack(side='right')
    ttk.Button(geometry,text='套用尺寸',command=app.apply_pitch).pack(anchor='w',pady=6)
    ttk.Button(geometry,text='貼上截圖並校正格子寬高與格距…',command=app.calibrate_grid).pack(anchor='w',pady=4)
    note(geometry,'貼上有格線的完整遊戲截圖，量測格子寬高與格距後確認套用。')
    opacity = section(align,'疊層不透明度')
    app.opacity = tk.DoubleVar(value=.45)
    app.opacity_text = tk.StringVar(value='45%')
    opacity_row = row(opacity)
    ttk.Label(opacity_row,text='不透明度').pack(side='left')
    ttk.Label(opacity_row,textvariable=app.opacity_text).pack(side='right')
    ttk.Scale(opacity,variable=app.opacity,from_=.15,to=.85).pack(fill='x')
    app.opacity.trace_add('write',app.opacity_changed)
    note(opacity,'進入對齊模式後，按住左鍵拖曳疊層。')

    colors = section(draw,'取色與逐色繪畫')
    color_buttons = row(colors)
    app.pick_button = ttk.Button(color_buttons,text='從疊層取色（F5）',command=app.toggle_picker)
    app.pick_button.pack(side='left',padx=(0,8))
    ttk.Button(color_buttons,text='顯示全部顏色（F6）',command=app.show_all).pack(side='left')
    note(colors,'也可在繪畫模式按 Shift＋左鍵點選疊層格子。')
    app.color_text = tk.StringVar(value='顯示全部顏色')
    app.swatch = tk.Label(colors,textvariable=app.color_text,anchor='w',padx=8,pady=10)
    app.swatch.pack(fill='x',pady=8)
    app.auto_color_enabled = tk.BooleanVar(value=False)
    ttk.Checkbutton(colors,text='啟用自動選色（會操作滑鼠）',variable=app.auto_color_enabled,
                    command=app.change_auto_color).pack(anchor='w',pady=(4,0))
    note(colors,'預設關閉。請先閱讀使用說明與規章風險，再決定是否啟用。')
    ttk.Button(colors,text='官方規章與資料使用說明',command=app.show_usage_policy).pack(anchor='w',pady=4)
    app.game_color_button = ttk.Button(colors,text='自動切換畫筆顏色（F7）',command=app.select_game_color,state='disabled',style='Primary.TButton')
    app.game_color_button.pack(fill='x',pady=4)
    note(colors,'先展開遊戲色盤。按下後切回遊戲，畫筆會自動切換成取出的顏色。')
    palette = Disclosure(colors,'色盤位置與校正',app.stage_changed)
    palette.pack(fill='x',pady=(6,0))
    app.palette_calibration_text = tk.StringVar(value='色盤位置：預設16:9版面')
    ttk.Label(palette.body,textvariable=app.palette_calibration_text,wraplength=400).pack(fill='x')
    note(palette.body,'若自動切換畫筆顏色沒有反應或選錯顏色，可重新校正色盤位置。')
    ttk.Button(palette.body,text='貼上截圖並校正色盤位置…',command=app.calibrate_palette).pack(anchor='w',pady=4)
    ttk.Button(palette.body,text='恢復預設色盤位置',command=app.reset_palette_calibration).pack(anchor='w',pady=4)
    app.palette_disclosure = palette
    assist = section(draw,'繪畫輔助')
    app.sync_drag,app.arrow_nudge = tk.BooleanVar(value=True),tk.BooleanVar(value=True)
    ttk.Checkbutton(assist,text='右鍵拖畫布，同步移動疊層',variable=app.sync_drag,
                    command=app.reset_drag_sync).pack(anchor='w')
    note(assist,'從遊戲繪畫區開始拖曳，移動量為1:1。')
    note(assist,'拖曳後疊層可能偏移，請自行確認；有偏移時按 F9 切回對齊模式重新對齊。')
    ttk.Checkbutton(assist,text='方向鍵微調疊層',variable=app.arrow_nudge).pack(anchor='w')
    note(assist,'每次1px；Shift＋方向鍵每次10px。')

    app.status = tk.StringVar(value='載入圖片後，設定畫布並對齊疊層。')
    footer = app.layout.footer
    footer.columnconfigure(0,weight=1)
    status_label = ttk.Label(footer,textvariable=app.status,wraplength=430)
    status_label.grid(row=0,column=0,columnspan=2,sticky='ew',pady=(0,6))
    appearance = ttk.Frame(footer)
    appearance.grid(row=1,column=0,sticky='w')
    actions = ttk.Frame(footer)
    actions.grid(row=1,column=1,sticky='e')
    ttk.Label(appearance,text='介面').pack(side='left',padx=4)
    app.ui_scale = tk.StringVar(value='100%')
    zoom = ttk.Combobox(appearance,textvariable=app.ui_scale,state='readonly',width=7,
                        values=['100%','125%','150%','175%','200%'])
    zoom.pack(side='left',padx=4)
    zoom.bind('<<ComboboxSelected>>',app.resize_ui)
    ttk.Label(appearance,text='主題').pack(side='left',padx=(12,4))
    app.theme_menu = ttk.Combobox(appearance,textvariable=app.theme_name,state='readonly',width=10,
                                values=list(THEMES))
    app.theme_menu.pack(side='left',padx=4)
    app.theme_menu.bind('<<ComboboxSelected>>',app.change_theme)
    ttk.Button(actions,text='自動調整視窗大小',command=app.layout.fit).pack(side='left',padx=6)
    ttk.Label(actions,text='狀態自動保存').pack(side='left',padx=4)
    def footer_resize(event):
        stacked = event.width<appearance.winfo_reqwidth()+actions.winfo_reqwidth()+20
        actions.grid_configure(row=2 if stacked else 1,column=0 if stacked else 1,
                               columnspan=2 if stacked else 1,sticky='w' if stacked else 'e')
        width = max(100,event.width-24)
        if int(status_label.cget('wraplength'))!=width:
            status_label.configure(wraplength=width)
    footer.bind('<Configure>',footer_resize)
    # 卡片中的文字與列使用同一表面色；特殊按鈕樣式保留。
    def card_widgets(parent,inside=False):
        inside = inside or isinstance(parent,ttk.LabelFrame)
        if inside:
            if isinstance(parent,ttk.Frame):
                parent.configure(style='Card.TFrame')
            elif isinstance(parent,ttk.Label):
                parent.configure(style='CardNote.TLabel' if parent.cget('style')=='Note.TLabel' else 'Card.TLabel')
            elif isinstance(parent,ttk.Checkbutton):
                parent.configure(style='Card.TCheckbutton')
            elif isinstance(parent,ttk.Radiobutton):
                parent.configure(style='Card.TRadiobutton')
        for child in parent.winfo_children():
            card_widgets(child,inside)
    card_widgets(app.layout.host)
    apply_theme(app, app.theme_name.get())
    app.resize_ui()
