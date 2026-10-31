"""手動疊圖的幾何，不推算遊戲畫布的位置。"""
from dataclasses import dataclass
import math


@dataclass
class Placement:
    left: float
    top: float
    step_x: float
    step_y: float
    cell_size: float | None = None

    def move(self, dx, dy):
        self.left += dx
        self.top += dy

    def viewport(self, clip):
        """可見區在原圖的格子座標，可超出圖片邊界。"""
        x0,y0,x1,y1 = clip
        return ((x0-self.left)/self.step_x,(y0-self.top)/self.step_y,
                (x1-self.left)/self.step_x,(y1-self.top)/self.step_y)

    def navigate(self, col, row, clip, w, h):
        """小地圖以整格換區，保留原先手動微調的對齊餘數。"""
        x0,y0,x1,y1 = self.viewport(clip)
        col = max(0,min(col,max(0,w-(x1-x0))))
        row = max(0,min(row,max(0,h-(y1-y0))))
        self.move(-round(col-x0)*self.step_x,-round(row-y0)*self.step_y)

    def cell_at(self, x, y, w, h):
        col = math.floor((x-self.left)/self.step_x)
        row = math.floor((y-self.top)/self.step_y)
        return (col,row) if 0 <= col < w and 0 <= row < h else None

    def cell_box(self, col, row, clip):
        """格距是格間留白；色塊置中於每格的排列範圍。"""
        width = self.step_x if self.cell_size is None else self.cell_size
        height = self.step_y if self.cell_size is None else self.cell_size
        left = self.left+col*self.step_x+(self.step_x-width)/2
        top = self.top+row*self.step_y+(self.step_y-height)/2
        return (max(left,clip[0]),max(top,clip[1]),
                min(left+width,clip[2]),min(top+height,clip[3]))

    def visible(self, w, h, clip):
        x0,y0,x1,y1 = clip
        cols = range(max(0,math.floor((x0-self.left)/self.step_x)),
                     min(w,math.ceil((x1-self.left)/self.step_x)))
        rows = range(max(0,math.floor((y0-self.top)/self.step_y)),
                     min(h,math.ceil((y1-self.top)/self.step_y)))
        for row in rows:
            for col in cols:
                left,top = self.left+col*self.step_x,self.top+row*self.step_y
                yield col,row,(max(left,x0),max(top,y0),min(left+self.step_x,x1),min(top+self.step_y,y1))
