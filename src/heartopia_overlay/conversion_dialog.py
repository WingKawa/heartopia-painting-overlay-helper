"""轉圖預覽視窗：背景處理，確認套用後才變更目前作品。"""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from PIL import Image, ImageTk
from .image_conversion import open_image, convert_image, target_image, ColorAdjustments
from .assist_layout import fit_dialog, pause_overlay_for_dialog
from .crop_selection import CropSelection
from .size_presets import SizePresets


class ConversionDialog:
    def __init__(self,root,path,on_apply):
        self.log = getattr(root,'assist_log',None)
        self.window = tk.Toplevel(root)
        pause_overlay_for_dialog(root,self.window)
        self.window.withdraw()
        self.window.title('轉為小鎮可用的125色')
        self.window.transient(root)
        self.on_apply = on_apply
        self.path = path
        self.source = None
        self.result = None
        self.generation = 0
        self.running = False
        self.pending = None
        self.closed = False
        self.events = queue.Queue()
        self.photos = {}
        self.crop_model = None
        self.source_display = None
        self.crop_drag = None
        self.preview_timer = None
        self.preview_side = round(400*root.winfo_fpixels('1i')/96)
        outer = ttk.Frame(self.window)
        outer.pack(fill='both',expand=True)
        outer.rowconfigure(0,weight=1)
        outer.columnconfigure(0,weight=1)
        self.view = tk.Canvas(outer,highlightthickness=0)
        self.view.grid(row=0,column=0,sticky='nsew')
        vertical = ttk.Scrollbar(outer,orient='vertical',command=self.view.yview)
        horizontal = ttk.Scrollbar(outer,orient='horizontal',command=self.view.xview)
        vertical.grid(row=0,column=1,sticky='ns')
        horizontal.grid(row=1,column=0,sticky='ew')
        self.view.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        panel = ttk.Frame(self.view,padding=20)
        item = self.view.create_window(0,0,window=panel,anchor='nw')
        panel.bind('<Configure>',lambda e: self.view.configure(scrollregion=self.view.bbox('all')))
        self.view.bind('<Configure>',lambda e: self.view.itemconfigure(item,width=max(e.width,panel.winfo_reqwidth())))
        settings = ttk.Frame(panel)
        settings.pack(fill='x')
        self.width,self.height = tk.StringVar(value='150'),tk.StringVar(value='150')
        self.size_presets = SizePresets(panel,self.width,self.height)
        self.size_presets.pack(fill='x',before=settings,pady=(0,8))
        for label,var in [('像素寬',self.width),('像素高',self.height)]:
            ttk.Label(settings,text=label).pack(side='left')
            ttk.Entry(settings,textvariable=var,width=7).pack(side='left',padx=4)
        self.mode = tk.StringVar(value='完整保留')
        ttk.Combobox(settings,textvariable=self.mode,state='readonly',width=10,
                     values=['完整保留','裁切填滿','拉伸']).pack(side='left',padx=6)
        self.preview_button = ttk.Button(settings,text='更新預覽',command=self.request,state='disabled')
        self.preview_button.pack(side='left')
        previews = ttk.Frame(panel)
        previews.pack(fill='both',expand=True,pady=12)
        canvases = []
        for title in ('原圖','125 色預覽'):
            frame = ttk.Frame(previews)
            frame.pack(side='left',padx=8)
            ttk.Label(frame,text=title).pack(anchor='w',pady=4)
            canvas = tk.Canvas(frame,width=self.preview_side,height=self.preview_side,
                               bg='#dddddd',highlightthickness=0)
            canvas.pack()
            canvas.create_text(self.preview_side/2,self.preview_side/2,text='讀取圖片中…')
            canvases.append(canvas)
        self.original,self.converted = canvases
        self.original.bind('<ButtonPress-1>',self.crop_start)
        self.original.bind('<B1-Motion>',self.crop_move)
        self.original.bind('<ButtonRelease-1>',self.crop_end)
        self.original.configure(cursor='crosshair')
        crop_tools = ttk.Frame(panel)
        crop_tools.pack(fill='x',pady=5)
        self.crop_enabled = tk.BooleanVar(value=False)
        self.lock_ratio = tk.BooleanVar(value=True)
        ttk.Checkbutton(crop_tools,text='手動裁切',variable=self.crop_enabled,
                        command=self.crop_options_changed).pack(side='left')
        ttk.Checkbutton(crop_tools,text='鎖定輸出比例',variable=self.lock_ratio,
                        command=self.crop_options_changed).pack(side='left',padx=8)
        ttk.Button(crop_tools,text='重設裁切',command=self.reset_crop).pack(side='left')
        ttk.Label(panel,text='原圖：拖曳框內移動，拖曳四角調整範圍；在框外拖曳可重畫選區。',
                  wraplength=850).pack(anchor='w')
        color_panel = ttk.LabelFrame(panel,text='色彩微調',padding=12)
        color_panel.pack(fill='x',pady=10)
        self.adjustments = {}
        self.adjustment_labels = {}
        for index,(key,title) in enumerate([
                ('temperature','色溫（偏冷 ↔ 偏暖）'),('brightness','亮度（暗 ↔ 亮）'),
                ('contrast','對比（柔和 ↔ 強烈）'),('saturation','飽和度（淡 ↔ 鮮豔）'),
                ('whites','白位（壓低亮部 ↔ 白更亮）'),('blacks','黑位（提亮暗部 ↔ 黑更深）')]):
            cell = ttk.Frame(color_panel,padding=(8,4))
            cell.grid(row=index//2,column=index%2,sticky='ew')
            color_panel.columnconfigure(index%2,weight=1)
            label = ttk.Frame(cell)
            label.pack(fill='x')
            ttk.Label(label,text=title).pack(side='left')
            value = tk.DoubleVar(value=0)
            displayed = tk.StringVar(value='0')
            self.adjustments[key],self.adjustment_labels[key] = value,displayed
            ttk.Label(label,textvariable=displayed,width=5,anchor='e').pack(side='right')
            ttk.Scale(cell,from_=-100,to=100,variable=value).pack(fill='x',pady=4)
            value.trace_add('write',lambda *args,k=key:self.adjustment_changed(k))
        ttk.Button(color_panel,text='恢復色彩預設',command=self.reset_adjustments).grid(row=3,column=0,sticky='w',padx=8,pady=4)
        ttk.Label(color_panel,text='0 為原始設定；調整後自動更新右側 125 色預覽，原圖與裁切保持不變。',
                  wraplength=800).grid(row=4,column=0,columnspan=2,sticky='w',padx=8)
        self.status = tk.StringVar(value='正在讀取圖片…')
        ttk.Label(panel,textvariable=self.status,wraplength=650).pack(anchor='w')
        actions = ttk.Frame(panel)
        actions.pack(fill='x',pady=8)
        self.apply_button = ttk.Button(actions,text='使用轉換結果',state='disabled',command=self.apply)
        self.apply_button.pack(side='right')
        self.save_button = ttk.Button(actions,text='另存圖片…',state='disabled',command=self.save_as)
        self.save_button.pack(side='right',padx=6)
        ttk.Button(actions,text='取消',command=self.close).pack(side='right',padx=6)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        # Canvas 不會以內部內容作需求尺寸，先明確給出完整內容大小。
        panel.update_idletasks()
        self.view.configure(width=panel.winfo_reqwidth(),height=panel.winfo_reqheight())
        dpi = root.winfo_fpixels('1i')/96
        self.initial_geometry = fit_dialog(self.window,root,round(1000*dpi),round(760*dpi))
        if root.winfo_viewable():
            self.window.deiconify()
        self.window.grab_set()
        for var in (self.width,self.height,self.mode):
            var.trace_add('write',lambda *args: self.settings_changed())
        threading.Thread(target=self.read_source,daemon=True).start()
        self.timer = self.window.after(50,self.drain)

    def read_source(self):
        try:
            self.events.put(('source',open_image(self.path)))
        except Exception as e:
            self.events.put(('error',str(e)))

    def settings_changed(self):
        self.invalidate()
        self.schedule_preview()

    def adjustment_changed(self,key):
        self.adjustment_labels[key].set(f'{self.adjustments[key].get():+.0f}')
        self.settings_changed()

    def reset_adjustments(self):
        for variable in self.adjustments.values():
            variable.set(0)

    def schedule_preview(self):
        if self.preview_timer:
            self.window.after_cancel(self.preview_timer)
        self.preview_timer = self.window.after(220,self.request)

    def output_ratio(self):
        if not self.lock_ratio.get():
            return None
        try:
            w,h = int(self.width.get()),int(self.height.get())
            return w/h if w>0 and h>0 else None
        except ValueError:
            return None

    def fit_crop_ratio(self):
        ratio = self.output_ratio()
        if self.crop_model and self.crop_enabled.get() and ratio:
            self.crop_model.fit_ratio(ratio)
        self.draw_crop()

    def crop_options_changed(self):
        if self.crop_model is None:
            return
        self.fit_crop_ratio()
        self.invalidate()
        self.schedule_preview()

    def reset_crop(self):
        if self.crop_model is None:
            return
        self.crop_model.reset(self.output_ratio() if self.crop_enabled.get() else None)
        self.draw_crop()
        self.invalidate()
        self.schedule_preview()

    def source_point(self,event,clamp=False):
        if self.source_display is None:
            return None
        ox,oy,sx,sy = self.source_display
        x,y = (event.x-ox)/sx,(event.y-oy)/sy
        if not clamp and not (0<=x<=self.source.width and 0<=y<=self.source.height):
            return None
        return (max(0,min(x,self.source.width)),max(0,min(y,self.source.height)))

    def draw_crop(self):
        self.original.delete('crop')
        if self.crop_model is None or self.source_display is None:
            return
        ox,oy,sx,sy = self.source_display
        box = self.crop_model.box if self.crop_enabled.get() else (0,0,self.source.width,self.source.height)
        left,top,right,bottom = ox+box[0]*sx,oy+box[1]*sy,ox+box[2]*sx,oy+box[3]*sy
        ex,ey = ox+self.source.width*sx,oy+self.source.height*sy
        if self.crop_enabled.get():
            for rect in [(ox,oy,ex,top),(ox,bottom,ex,ey),(ox,top,left,bottom),(right,top,ex,bottom)]:
                if rect[0]<rect[2] and rect[1]<rect[3]:
                    self.original.create_rectangle(*rect,fill='black',stipple='gray50',outline='',tags='crop')
        self.original.create_rectangle(left,top,right,bottom,outline='#ffb000',width=2,tags='crop')
        if self.crop_enabled.get():
            handle = max(5,round(self.preview_side/100))
            for x,y in [(left,top),(right,top),(left,bottom),(right,bottom)]:
                self.original.create_rectangle(x-handle,y-handle,x+handle,y+handle,
                                               fill='white',outline='#005fbb',width=2,tags='crop')

    def crop_start(self,event):
        point = self.source_point(event)
        if point is None or self.crop_model is None:
            return
        x,y = point
        was_enabled = self.crop_enabled.get()
        self.crop_enabled.set(True)
        if not was_enabled:
            self.fit_crop_ratio()
        x0,y0,x1,y1 = self.crop_model.box
        _,_,sx,sy = self.source_display
        corner = None
        for name,cx,cy in [('nw',x0,y0),('ne',x1,y0),('sw',x0,y1),('se',x1,y1)]:
            if abs(x-cx)*sx<=14 and abs(y-cy)*sy<=14:
                corner = name
                break
        action = corner or ('move' if x0<=x<=x1 and y0<=y<=y1 else 'new')
        self.crop_drag = (action,x,y,self.crop_model.box)
        self.draw_crop()
        self.invalidate()

    def crop_move(self,event):
        if self.crop_drag is None:
            return
        x,y = self.source_point(event,clamp=True)
        action,start_x,start_y,original = self.crop_drag
        ratio = self.output_ratio()
        if action=='move':
            self.crop_model.move(original,x-start_x,y-start_y)
        elif action=='new':
            self.crop_model.from_anchor(start_x,start_y,x,y,
                                       -1 if x<start_x else 1,-1 if y<start_y else 1,ratio)
        else:
            self.crop_model.resize(original,action,x,y,ratio)
        self.draw_crop()
        self.invalidate()
        self.status.set('正在調整裁切範圍…')
        self.schedule_preview()

    def crop_end(self,event):
        if self.crop_drag is None:
            return
        self.crop_move(event)
        self.crop_drag = None
        self.request()

    def invalidate(self):
        self.generation += 1
        self.result = None
        self.pending = None
        self.apply_button.configure(state='disabled')
        self.save_button.configure(state='disabled')
        if self.source is not None:
            self.status.set('設定已變更，請更新預覽。')

    def request(self):
        if self.source is None:
            return
        if self.preview_timer:
            self.window.after_cancel(self.preview_timer)
            self.preview_timer = None
        self.invalidate()
        try:
            w,h = int(self.width.get()),int(self.height.get())
            if w<1 or h<1:
                raise ValueError('像素寬高必須是正整數')
        except ValueError as e:
            self.status.set(str(e))
            return
        self.fit_crop_ratio()
        crop = self.crop_model.box if self.crop_enabled.get() and self.crop_model else None
        settings = ColorAdjustments(**{key:value.get() for key,value in self.adjustments.items()})
        if self.log:
            self.log.record('conversion_request',width=w,height=h,mode=self.mode.get(),crop=crop,adjustments=vars(settings))
        self.pending = (self.generation,w,h,self.mode.get(),crop,settings)
        self.launch()

    def launch(self):
        if self.running or self.pending is None:
            return
        token,w,h,mode,crop,settings = self.pending
        self.pending = None
        self.running = True
        self.status.set('正在轉換…')
        def work():
            try:
                self.events.put(('result',token,convert_image(self.source,w,h,mode,crop=crop,adjustments=settings)))
            except Exception as e:
                self.events.put(('failed',token,str(e)))
        threading.Thread(target=work,daemon=True).start()

    def show_image(self,widget,image):
        image = image.copy()
        side = self.preview_side
        scale = min(side/image.width,side/image.height)
        image = image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.NEAREST)
        background = Image.new('RGBA',(side,side),(225,225,225,255))
        background.alpha_composite(image,((side-image.width)//2,(side-image.height)//2))
        photo = ImageTk.PhotoImage(background,master=self.window)
        self.photos[widget] = photo
        widget.delete('all')
        widget.create_image(side/2,side/2,image=photo)
        if widget is self.original and self.source is not None:
            self.source_display = ((side-image.width)/2,(side-image.height)/2,
                                   image.width/self.source.width,image.height/self.source.height)
            self.draw_crop()

    def drain(self):
        if self.closed:
            return
        while not self.events.empty():
            event = self.events.get_nowait()
            if event[0]=='source':
                self.source = event[1]
                self.crop_model = CropSelection(*self.source.size)
                factor = min(1,150/max(self.source.size))
                self.width.set(str(max(1,round(self.source.width*factor))))
                self.height.set(str(max(1,round(self.source.height*factor))))
                self.show_image(self.original,self.source)
                self.preview_button.configure(state='normal')
                self.request()
            elif event[0]=='error':
                self.status.set(f'讀取失敗：{event[1]}')
            else:
                self.running = False
                if event[1]==self.generation:
                    if event[0]=='result':
                        self.result = event[2]
                        self.show_image(self.converted,target_image(self.result))
                        colors = {v for row in self.result.cells for v in row if v is not None}
                        if self.log:
                            self.log.record('conversion_complete',width=self.result.w,height=self.result.h,colors=len(colors))
                        self.status.set(f'{self.result.w}×{self.result.h} 像素，{len(colors)} 種遊戲顏色')
                        self.apply_button.configure(state='normal')
                        self.save_button.configure(state='normal')
                    else:
                        if self.log:
                            self.log.record('conversion_error',error=event[2])
                        self.status.set(f'轉換失敗：{event[2]}')
                self.launch()
        self.timer = self.window.after(50,self.drain)

    def save_as(self):
        result = self.result
        if result is None:
            return
        source = Path(self.path)
        path = filedialog.asksaveasfilename(parent=self.window,title='另存125色圖片',
                initialdir=str(source.parent),initialfile=source.stem+'_125色.png',
                defaultextension='.png',filetypes=[('PNG圖片','*.png')],confirmoverwrite=True)
        if not path:
            return
        try:
            # 儲存實際像素結果，不包含預覽的放大、底色與裁切框。
            target_image(result).save(path,format='PNG')
        except OSError as error:
            self.status.set(f'儲存失敗：{error}')
            return
        self.status.set(f'已儲存 {Path(path).name}（{result.w}×{result.h} 像素）')

    def apply(self):
        if self.result is not None:
            result = self.result
            self.close()
            self.on_apply(result)

    def close(self):
        self.closed = True
        if self.preview_timer:
            self.window.after_cancel(self.preview_timer)
            self.preview_timer = None
        if self.timer:
            self.window.after_cancel(self.timer)
            self.timer = None
        self.window.grab_release()
        self.window.destroy()
