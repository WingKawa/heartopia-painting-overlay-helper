"""可縮放、可捲動的雙欄面板，避免文字變化擠動小地圖。"""
import tkinter as tk
from tkinter import font, ttk
import win32api
import win32con


class AssistLayout:
    def __init__(self, root):
        self.root = root
        self.factor = 1.0
        self.dpi = root.winfo_fpixels("1i")/96
        self.fonts = {name: font.nametofont(name).cget("size") for name in font.names()}
        self.header = ttk.Frame(root,padding=(12,8))
        self.header.pack(fill='x',side='top')
        self.footer = ttk.Frame(root,padding=(12,8))
        self.footer.pack(fill='x',side='bottom')
        frame = ttk.Frame(root)
        frame.pack(fill="both",expand=True)
        frame.rowconfigure(0,weight=1)
        frame.columnconfigure(0,weight=1)
        self.view = tk.Canvas(frame,highlightthickness=0)
        self.view.grid(row=0,column=0,sticky="nsew")
        vertical = ttk.Scrollbar(frame,orient="vertical",command=self.view.yview)
        horizontal = ttk.Scrollbar(frame,orient="horizontal",command=self.view.xview)
        vertical.grid(row=0,column=1,sticky="ns")
        horizontal.grid(row=1,column=0,sticky="ew")
        self.view.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.host = ttk.Frame(self.view)
        self.window = self.view.create_window(0,0,window=self.host,anchor="nw")
        self.shells = [ttk.Frame(self.host),ttk.Frame(self.host)]
        self.panels = []
        for col,shell in enumerate(self.shells):
            shell.grid(row=0,column=col,sticky="new")
            shell.pack_propagate(False)
            inner = ttk.Frame(shell,padding=12)
            inner.pack(fill="both",expand=True)
            self.panels.append(inner)
        self.view.bind("<Configure>",lambda e: self.refresh())
        self.host.bind("<Configure>",lambda e: self.view.configure(scrollregion=self.view.bbox("all")))
        # 只在本程式面板內處理滾輪，不讀取或轉送遊戲輸入。
        root.bind("<MouseWheel>",self.wheel,add="+")
        root.resizable(True,True)

    def wheel(self,event):
        if event.widget.winfo_toplevel() == self.root:
            self.view.yview_scroll(-int(event.delta/120),"units")

    def refresh(self):
        unit = self.dpi*self.factor
        widths = (round(480*unit),round(560*unit))
        for col,(shell,inner,width) in enumerate(zip(self.shells,self.panels,widths)):
            self.host.columnconfigure(col,minsize=width,weight=3 if col==0 else 2)
            shell.configure(width=width,height=max(1,inner.winfo_reqheight()))
        self.view.itemconfigure(self.window,width=max(sum(widths),self.view.winfo_width()))
        self.view.configure(scrollregion=self.view.bbox("all"))
        def wrap_notes(parent):
            for child in parent.winfo_children():
                if isinstance(child,ttk.Label) and int(child.cget('wraplength') or 0)>0:
                    width = max(100,parent.winfo_width()-24)
                    if parent.winfo_width()>100 and int(child.cget('wraplength'))!=width:
                        child.configure(wraplength=width)
                wrap_notes(child)
        for panel in self.panels:
            wrap_notes(panel)

    def fit(self):
        # 寬度改變後，換行文字會再次改變內容高度，待版面穩定再取尺寸。
        for _ in range(3):
            self.root.update_idletasks()
            self.refresh()
        self.root.update_idletasks()
        hwnd = self.root.winfo_id()
        monitor = win32api.MonitorFromWindow(hwnd,win32con.MONITOR_DEFAULTTONEAREST)
        x0,y0,x1,y1 = win32api.GetMonitorInfo(monitor)["Work"]
        width = min(max(self.host.winfo_reqwidth()+65,self.header.winfo_reqwidth()+30,
                        self.footer.winfo_reqwidth()+30),x1-x0-40)
        height = min(self.host.winfo_reqheight()+self.header.winfo_reqheight()+self.footer.winfo_reqheight()+80,y1-y0-80)
        width,height = max(320,width),max(240,height)
        left = max(x0+10,min(self.root.winfo_x(),x1-width-20))
        top = max(y0+10,min(self.root.winfo_y(),y1-height-45))
        self.root.geometry(f"{width}x{height}{left:+d}{top:+d}")
        self.root.minsize(min(640,width),min(360,height))

    def scale(self, percent):
        self.factor = percent/100
        for name,size in self.fonts.items():
            font.nametofont(name).configure(size=(1 if size>=0 else -1)*max(1,round(abs(size)*self.factor)))
        from .assist_theme import configure_controls, THEMES, DEFAULT_THEME
        configure_controls(self.root,getattr(self.root,'_assist_theme_colors',THEMES[DEFAULT_THEME]),self.factor)
        self.fit()


def pause_overlay_for_dialog(root,window):
    """一般彈窗不置頂；開啟時先收起疊層，避免遊戲疊層蓋住操作介面。"""
    app = getattr(root,'assist_app',None)
    if app is not None:
        if not hasattr(app,'overlay_dialogs'):
            app.overlay_dialogs = set()
        app.overlay_dialogs.add(window)
        app.overlay.withdraw()
        app.shown_geometry = None
        app.record_event('overlay_dialog_open',dialog=type(window).__name__)
        def closed(event):
            if event.widget is window:
                app.overlay_dialogs.discard(window)
                app.shown_geometry = None
                app.reset_drag_sync()
                app.record_event('overlay_dialog_closed',remaining=len(app.overlay_dialogs))
        window.bind('<Destroy>',closed,add='+')


def fit_dialog(window,parent,minimum_width,minimum_height):
    """彈窗從主視窗左上角開啟，尺寸容納內容且不超出同一螢幕。"""
    parent.update_idletasks()
    window.update_idletasks()
    monitor = win32api.MonitorFromWindow(parent.winfo_id(),win32con.MONITOR_DEFAULTTONEAREST)
    x0,y0,x1,y1 = win32api.GetMonitorInfo(monitor)['Work']
    width = min(max(minimum_width,window.winfo_reqwidth()+60),x1-x0-40)
    height = min(max(minimum_height,window.winfo_reqheight()+90),y1-y0-80)
    left = max(x0+10,min(parent.winfo_x(),x1-width-20))
    top = max(y0+10,min(parent.winfo_y(),y1-height-45))
    window.geometry(f'{width}x{height}{left:+d}{top:+d}')
    window.resizable(True,True)
    return width,height,left,top
