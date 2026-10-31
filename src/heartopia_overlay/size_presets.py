"""轉圖與作品畫布共用的常用尺寸；不限制手動輸入。"""
import tkinter as tk
from tkinter import ttk


SIZE_GROUPS = (
    ('16:9',((30,18),(50,28),(100,56),(150,84))),
    ('4:3',((30,24),(50,38),(100,76),(150,114))),
    ('1:1',((30,30),(50,50),(100,100),(150,150))),
    ('3:4',((24,30),(38,50),(76,100),(114,150))),
    ('9:16',((18,30),(28,50),(56,100),(84,150))),
)
PRESETS = {f'{ratio}　{w}×{h}':(w,h) for ratio,sizes in SIZE_GROUPS for w,h in sizes}


class SizePresets(ttk.Frame):
    def __init__(self,parent,width,height):
        super().__init__(parent)
        self.width,self.height = width,height
        self.choice = tk.StringVar(master=self,value='自訂尺寸')
        ttk.Label(self,text='常用尺寸').pack(side='left')
        self.menu = ttk.Combobox(self,textvariable=self.choice,state='readonly',
                                values=('自訂尺寸',*PRESETS),width=23,height=21)
        self.menu.pack(side='left',padx=6)
        self.menu.bind('<<ComboboxSelected>>',self.select)
        self.traces = [(variable,variable.trace_add('write',self.refresh)) for variable in (width,height)]
        self.bind('<Destroy>',self.cleanup,add='+')
        self.refresh()

    def select(self,event=None):
        dimensions = PRESETS.get(self.choice.get())
        if dimensions is not None:
            self.width.set(str(dimensions[0]))
            self.height.set(str(dimensions[1]))

    def refresh(self,*args):
        try:
            dimensions = int(self.width.get()),int(self.height.get())
        except ValueError:
            dimensions = None
        self.choice.set(next((name for name,size in PRESETS.items() if size==dimensions),'自訂尺寸'))

    def cleanup(self,event):
        if event.widget is self:
            for variable,token in self.traces:
                variable.trace_remove('write',token)
