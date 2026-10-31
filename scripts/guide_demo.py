"""製作教學截圖用的示範視窗：不連接遊戲、不安裝輸入攔截器、不讀寫個人設定。"""
from pathlib import Path
import queue
import sys
import tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import heartopia_overlay.assist as module
from heartopia_overlay.errors import GameWindowError
from heartopia_overlay.target import TargetGrid
from heartopia_overlay.image_conversion import target_image
from heartopia_overlay.conversion_dialog import ConversionDialog
from heartopia_overlay.win.dpi import ensure_dpi_aware


class SilentPicker:
    error = None
    def __init__(self):
        self.points,self.nudges = queue.Queue(),queue.Queue()
    def start(self):
        return True
    def close(self):
        pass


def no_game():
    raise GameWindowError('教學範例未連接遊戲')


class Demo(module.Assist):
    def poll(self):
        pass
    def poll_inputs(self):
        pass
    def poll_drag(self):
        pass
    def poll_picker(self):
        pass
    def initialize_session(self):
        self.root.geometry('1700x1150+60+60')
        self.layout.refresh()
    def convert_pick(self):
        ConversionDialog(self.root,self.sample_path,lambda target:None)


if __name__=='__main__':
    module.ColorPicker = SilentPicker
    module.find_game_hwnd = no_game
    ensure_dpi_aware()
    root = tk.Tk()
    root.tk.call('tk','scaling',root.winfo_fpixels('1i')/72)
    app = Demo(root,persist=False)
    palette = app.palette
    sky,water,grass,roof,wall = [palette.by_label(label).index for label in ('10-4','11-1','8-1','3-1','1-5')]
    cells = []
    for y in range(36):
        row = []
        for x in range(48):
            value = sky if y<16 else grass if y<27 else water
            if 19<=x<=30 and 19<=y<=29:
                value = wall
            if 16<=y<20 and abs(x-24)<=y-13:
                value = roof
            if 23<=x<=26 and 24<=y<=29:
                value = roof
            if 20<=x<=22 and 21<=y<=23:
                value = water
            row.append(value)
        cells.append(row)
    source = TargetGrid(48,36,cells)
    app.sample_path = Path(__file__).resolve().parents[1]/'build'/'guide-demo.png'
    target_image(source).save(app.sample_path)
    app.adopt_target(source,'教學範例.png')
    app.target.resize(64,48)
    app.target.center()
    app.canvas_width.set('64')
    app.canvas_height.set('48')
    app.info.set('教學範例.png · 圖片48×36；畫布64×48。')
    app.connection_text.set('教學範例：尚未連接遊戲')
    app.clip = (0,0,960,600)
    app.set_cell_geometry(6,48)
    app.position.left,app.position.top = -900,-600
    app.render()
    app.root.title('Heartopia 教學介面範例')
    root.mainloop()
