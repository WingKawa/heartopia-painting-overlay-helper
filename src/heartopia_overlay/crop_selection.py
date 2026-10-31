"""原圖座標中的裁切框，與預覽縮放及輸出像素尺寸分開。"""
from dataclasses import dataclass
import math


@dataclass
class CropSelection:
    width: int
    height: int
    box: tuple | None = None

    def __post_init__(self):
        self.reset()

    def reset(self,ratio=None):
        w,h = self.width,self.height
        if ratio:
            w = min(w,h*ratio)
            h = w/ratio
        self.box = ((self.width-w)/2,(self.height-h)/2,(self.width+w)/2,(self.height+h)/2)

    def move(self,original,dx,dy):
        x0,y0,x1,y1 = original
        dx = max(-x0,min(dx,self.width-x1))
        dy = max(-y0,min(dy,self.height-y1))
        self.box = (x0+dx,y0+dy,x1+dx,y1+dy)

    def fit_ratio(self,ratio):
        x0,y0,x1,y1 = self.box
        cx,cy = (x0+x1)/2,(y0+y1)/2
        w = math.sqrt((x1-x0)*(y1-y0)*ratio)
        h = w/ratio
        factor = min(1,self.width/w,self.height/h)
        w,h = w*factor,h*factor
        left = max(0,min(cx-w/2,self.width-w))
        top = max(0,min(cy-h/2,self.height-h))
        self.box = (left,top,min(self.width,left+w),min(self.height,top+h))

    def resize(self,original,corner,x,y,ratio=None):
        x0,y0,x1,y1 = original
        ax,ay = (x1 if 'w' in corner else x0),(y1 if 'n' in corner else y0)
        sx,sy = (-1 if 'w' in corner else 1),(-1 if 'n' in corner else 1)
        self.from_anchor(ax,ay,x,y,sx,sy,ratio)

    def from_anchor(self,ax,ay,x,y,sx,sy,ratio=None):
        max_w = ax if sx<0 else self.width-ax
        max_h = ay if sy<0 else self.height-ay
        if max_w<=0 or max_h<=0:
            return
        w = min(max_w,max(min(1,max_w),sx*(x-ax)))
        h = min(max_h,max(min(1,max_h),sy*(y-ay)))
        if ratio:
            w = min(max(w,h*ratio),max_w,max_h*ratio)
            h = w/ratio
        bx,by = ax+sx*w,ay+sy*h
        self.box = (max(0,min(ax,bx)),max(0,min(ay,by)),
                    min(self.width,max(ax,bx)),min(self.height,max(ay,by)))
