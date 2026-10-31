"""重用貼上截圖視窗，預覽與修正色盤點擊位置。"""
import tkinter as tk
from tkinter import ttk
import numpy as np
from .grid_calibration_dialog import GridCalibrationDialog
from .palette_calibration import PaletteCalibration,calibrate_palette,verify_calibration


class PaletteCalibrationDialog(GridCalibrationDialog):
    labels = [('left_x','左欄X'),('right_x','右欄X'),('y0','首列Y'),('dy','列距'),
              ('x0','色帶左'),('y1','色帶上'),('x1','色帶右'),('y1b','色帶下'),
              ('chip_width','白框寬'),('chip_height','白框高')]

    def __init__(self,root,client_size,palette,apply,frames=()):
        self.palette = palette
        self.fields = {}
        self.editing = False
        self.group = None
        super().__init__(root,client_size,apply,frames=frames)
        self.window.title('貼上截圖並校正色盤位置')
        pane = self.canvas.master
        pane.winfo_children()[0].configure(text='展開遊戲色盤，貼上完整遊戲截圖（Ctrl+V）。\n'
            '框選主色色帶與下方兩欄色塊，避開左側調色盤圖示；辨識後檢查編號點的位置。')
        toolbar = pane.winfo_children()[1]
        toolbar.winfo_children()[1].configure(text='辨識色盤')
        self.apply_button.configure(text='保存色盤校正')
        controls = ttk.Frame(pane)
        controls.pack(fill='x',before=self.canvas,pady=4)
        for i,(key,label) in enumerate(self.labels):
            row,col = divmod(i,3)
            ttk.Label(controls,text=label).grid(row=row,column=col*2,sticky='w',padx=4)
            var = tk.StringVar()
            ttk.Entry(controls,textvariable=var,width=9).grid(row=row,column=col*2+1,padx=4,pady=2)
            self.fields[key] = var
            var.trace_add('write',self.edited)
        ttk.Button(controls,text='檢查手動修正',command=self.check_fields).grid(row=3,column=2,columnspan=2,padx=8)
        ttk.Label(controls,text='數值單位：目前遊戲的實體像素').grid(row=4,column=0,columnspan=6,sticky='w')
        self.text.set('尚未貼上截圖；辨識後才可保存。')
        from .assist_layout import fit_dialog
        dpi = root.winfo_fpixels('1i')/96
        fit_dialog(self.window,root,round(1100*dpi),round(900*dpi))

    def paste(self,event=None):
        previous = self.image
        result = super().paste(event)
        if self.image is not None and self.image is not previous:
            w,h = self.image.size
            self.roi = w*.875,h*.26,w*.999,h*.80
            self.group = None
            self.render()
            self.text.set('已貼上截圖，請確認青框包含主色色帶與下方全部色塊，再按「辨識色盤」。')
        return result

    def edited(self,*args):
        if not self.editing:
            self.invalidate()
            self.render()
            self.text.set('數值已修改，請按「檢查手動修正」確認點擊位置。')

    def set_result(self,result,group):
        self.editing = True
        data = result.record()
        data.update(dict(zip(('x0','y1','x1','y1b'),result.strip)))
        for key,var in self.fields.items():
            var.set(f'{data[key]:.4f}')
        self.editing = False
        self.result,self.group = result,group
        self.apply_button.configure(state='normal')
        self.text.set(f'已辨識第{group}組。編號點為組內點擊位置；黃色框為主色色帶搜尋範圍。\n'
                      f'確認後按「保存色盤校正」。對應遊戲解析度：{result.width}×{result.height}。')
        self.render()

    def measure(self):
        self.invalidate()
        if self.image is None:
            self.text.set('請先貼上完整遊戲截圖。')
            return
        self.window.configure(cursor='watch')
        self.window.update_idletasks()
        try:
            self.record('palette_measure_start',roi=self.roi,client_size=self.client_size)
            result,group = calibrate_palette(self.image,self.roi,self.client_size,self.palette)
            self.record('palette_measure_result',group=group,width=result.width,height=result.height)
            self.set_result(result,group)
        except ValueError as error:
            self.record('palette_measure_error',error=str(error),roi=self.roi)
            self.text.set(f'無法校正：{error} 原設定未變更。')
            self.render()
        finally:
            self.window.configure(cursor='')

    def check_fields(self):
        self.invalidate()
        try:
            if self.image is None:
                raise ValueError('請先貼上完整遊戲截圖。')
            data = {key:float(var.get()) for key,var in self.fields.items()}
            band = tuple(data.pop(key) for key in ('x0','y1','x1','y1b'))
            result = PaletteCalibration(*self.client_size,strip=band,**data)
            result.validate()
            group,_ = verify_calibration(np.asarray(self.image),result.resized(*self.image.size),self.palette)
            self.set_result(result,group)
        except ValueError as error:
            self.text.set(f'修正位置無法通過色塊／白框檢查：{error}')
            self.render()

    def render(self):
        super().render()
        if self.image is None or self.result is None:
            return
        ox,oy,scale = self.transform
        result = self.result.resized(*self.image.size)
        for slot in range(1,6 if self.group==1 else 11):
            x,y = result.point(slot)
            x,y = ox+x*scale,oy+y*scale
            self.canvas.create_oval(x-7,y-7,x+7,y+7,fill='#00ffff',outline='black',width=2)
            self.canvas.create_text(x+11,y,text=str(slot),fill='white',anchor='w',font=('',12,'bold'))
        x0,y0,x1,y1 = result.strip
        self.canvas.create_rectangle(ox+x0*scale,oy+y0*scale,ox+x1*scale,oy+y1*scale,
                                     outline='yellow',width=2)
