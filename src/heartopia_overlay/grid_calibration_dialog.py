"""貼上完整截圖、框選格線、檢查結果後套用。"""
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image,ImageGrab,ImageTk
from .assist_layout import fit_dialog, pause_overlay_for_dialog
from .grid_calibration import measure_grid, normalize_screenshot


class GridCalibrationDialog:
    def __init__(self,root,client_size,apply,frames=()):
        self.log = getattr(root,'assist_log',None)
        self.client_size,self.apply = client_size,apply
        self.frames = frames
        self.image,self.photo,self.roi,self.result = None,None,None,None
        self.drag = None
        self.window = tk.Toplevel(root)
        pause_overlay_for_dialog(root,self.window)
        self.window.title('貼上截圖並校正格子寬高與格距')
        self.window.transient(root)
        pane = ttk.Frame(self.window,padding=12)
        pane.pack(fill='both',expand=True)
        ttk.Label(pane,text='先隱藏疊層，複製完整遊戲截圖，再按「貼上截圖」（Ctrl+V）。\n'
                  '可在預覽上拖曳框選畫布內部；每個方向至少包含4條完整格線。').pack(anchor='w')
        tools = ttk.Frame(pane)
        tools.pack(fill='x',pady=8)
        ttk.Button(tools,text='貼上截圖（Ctrl+V）',command=self.paste).pack(side='left')
        ttk.Button(tools,text='量測格線',command=self.measure).pack(side='left',padx=8)
        self.apply_button = ttk.Button(tools,text='套用量測結果',command=self.accept,state='disabled')
        self.apply_button.pack(side='left')
        self.canvas = tk.Canvas(pane,width=900,height=500,bg='#222222',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.text = tk.StringVar(value='尚未貼上截圖。')
        ttk.Label(pane,textvariable=self.text,wraplength=850).pack(anchor='w',pady=8)
        self.canvas.bind('<Configure>',lambda e:self.render())
        self.canvas.bind('<ButtonPress-1>',self.begin)
        self.canvas.bind('<B1-Motion>',self.move)
        self.canvas.bind('<ButtonRelease-1>',self.end)
        self.window.bind('<Control-v>',self.paste)
        self.window.bind('<Control-V>',self.paste)
        dpi = root.winfo_fpixels('1i')/96
        fit_dialog(self.window,root,round(1000*dpi),round(760*dpi))
        self.window.grab_set()

    def invalidate(self):
        self.result = None
        self.apply_button.configure(state='disabled')

    def record(self,event,**fields):
        if self.log:
            self.log.record(event,dialog=type(self).__name__,**fields)

    def paste(self,event=None):
        self.invalidate()
        try:
            image = ImageGrab.grabclipboard()
            if not isinstance(image,Image.Image):
                raise ValueError('剪貼簿中沒有圖片，請先複製遊戲截圖。')
            self.image,trimmed = normalize_screenshot(image.convert('RGB'),self.client_size,self.frames)
            self.record('screenshot_pasted',original_size=image.size,normalized_size=self.image.size,trimmed=trimmed,client_size=self.client_size)
            w,h = self.image.size
            self.roi = (w*.205,h*.245,w*.775,h*.825)
            self.invalidate()
            self.text.set(f'遊戲畫面 {w}×{h}'+('（已移除標題列與邊框）' if trimmed else '')+'；請檢查青框範圍，或拖曳重新框選後量測。')
            self.render()
        except (OSError,ValueError) as error:
            self.record('screenshot_error',error=str(error),client_size=self.client_size)
            messagebox.showerror('無法貼上',str(error),parent=self.window)
        return 'break'

    def render(self):
        self.canvas.delete('all')
        if self.image is None:
            return
        w,h = self.image.size
        scale = min(max(1,self.canvas.winfo_width())/w,max(1,self.canvas.winfo_height())/h)
        dw,dh = max(1,round(w*scale)),max(1,round(h*scale))
        ox,oy = (self.canvas.winfo_width()-dw)/2,(self.canvas.winfo_height()-dh)/2
        self.transform = ox,oy,scale
        self.photo = ImageTk.PhotoImage(self.image.resize((dw,dh)),master=self.window)
        self.canvas.create_image(ox,oy,image=self.photo,anchor='nw')
        if self.roi:
            x0,y0,x1,y1 = self.roi
            self.canvas.create_rectangle(ox+x0*scale,oy+y0*scale,ox+x1*scale,oy+y1*scale,
                                         outline='#00ffff',width=2)

    def point(self,event):
        ox,oy,scale = self.transform
        return (min(self.image.width,max(0,(event.x-ox)/scale)),
                min(self.image.height,max(0,(event.y-oy)/scale)))

    def begin(self,event):
        if self.image is None:
            return
        self.drag = self.point(event)
        self.invalidate()

    def move(self,event):
        if self.drag is None:
            return
        x,y = self.point(event)
        sx,sy = self.drag
        self.roi = min(x,sx),min(y,sy),max(x,sx),max(y,sy)
        self.render()

    def end(self,event):
        if self.drag is not None:
            self.move(event)
            self.drag = None
            self.text.set('已更新框選範圍，請按「量測格線」。')

    def measure(self):
        self.invalidate()
        if self.image is None:
            self.text.set('請先貼上完整遊戲截圖。')
            return
        try:
            self.record('grid_measure_start',roi=self.roi,client_size=self.client_size)
            self.result = measure_grid(self.image,self.roi,self.client_size)
            self.record('grid_measure_result',**vars(self.result))
            r = self.result
            self.text.set(f'格距 {r.gap:.2f}px；格子寬高 {r.size:.2f}px；排列間距 {r.pitch:.2f}px。\n'
                          f'偵測到 {r.vertical_lines} 條直線、{r.horizontal_lines} 條橫線。尚未套用。')
            self.apply_button.configure(state='normal')
        except ValueError as error:
            self.record('grid_measure_error',error=str(error),roi=self.roi)
            self.text.set(f'無法校正：{error} 原設定未變更。')

    def accept(self):
        if self.result is not None:
            self.apply(self.result)
            self.window.destroy()
