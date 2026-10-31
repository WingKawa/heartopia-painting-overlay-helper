"""色盤校正資料與貼圖量測；座標相對遊戲client area。"""
from dataclasses import dataclass,asdict
import math
import numpy as np
from PIL import Image,ImageDraw
from .game_color import SelectionError
from .swatch_detection import find_swatch


@dataclass(frozen=True)
class PaletteCalibration:
    width: int
    height: int
    left_x: float
    right_x: float
    y0: float
    dy: float
    strip: tuple
    chip_width: float
    chip_height: float

    def record(self):
        return asdict(self)

    @classmethod
    def load(cls,data):
        try:
            result = cls(**data)
            result.validate()
            return result
        except (TypeError,KeyError,OverflowError) as error:
            raise ValueError('色盤校正資料無效。') from error

    def validate(self):
        if type(self.width) is not int or type(self.height) is not int or min(self.width,self.height)<=0:
            raise ValueError('色盤校正解析度無效。')
        values = (self.left_x,self.right_x,self.y0,self.dy,self.chip_width,self.chip_height,*self.strip)
        if len(self.strip)!=4 or not all(type(v) in (float,int) and math.isfinite(v) for v in values):
            raise ValueError('色盤校正座標無效。')
        x0,y0,x1,y1 = self.strip
        if not (0<=self.left_x<self.right_x<self.width and self.dy>2
                and 0<self.y0<self.y0+4*self.dy<self.height
                and 0<=x0<x1<=self.width and 0<=y0<y1<self.y0
                and 4<self.chip_width<x1-x0 and 4<self.chip_height<=y1-y0):
            raise ValueError('色盤校正範圍超出截圖，或欄列位置不正確。')

    def point(self,slot):
        return round(self.left_x if slot%2 else self.right_x),round(self.y0+self.dy*((slot-1)//2))

    def resized(self,width,height):
        sx,sy = width/self.width,height/self.height
        return PaletteCalibration(width,height,self.left_x*sx,self.right_x*sx,self.y0*sy,self.dy*sy,
                                  tuple(v*(sx if i%2==0 else sy) for i,v in enumerate(self.strip)),
                                  self.chip_width*sx,self.chip_height*sy)


def selected_chip(image,band,expected=None):
    h,w = image.shape[:2]
    x0,y0,x1,y1 = map(round,band)
    if not (0<=x0<x1<=w and 0<=y0<y1<=h):
        raise SelectionError('主色色帶範圍無效。')
    ys,xs = np.nonzero(image[y0:y1,x0:x1,:3].min(axis=2)>=245)
    if len(xs)<20:
        raise SelectionError('找不到主色色帶的選取白框。')
    left,right,top,bottom = int(xs.min()),int(xs.max())+1,int(ys.min()),int(ys.max())+1
    cw,ch = right-left,bottom-top
    if cw<5 or ch<5 or (expected and
            (abs(cw-expected[0])>max(3,expected[0]*.20) or abs(ch-expected[1])>max(3,expected[1]*.20))):
        raise SelectionError('主色色帶的白框尺寸與校正不符。')
    return (x0+(left+right)/2,y0+(top+bottom)/2,cw),ch


def verify_calibration(image,calibration,palette):
    calibration.validate()
    if image.shape[1::-1]!=(calibration.width,calibration.height):
        raise SelectionError('遊戲解析度與色盤校正不同，請重新校正或恢復預設。')
    samples = []
    for slot in range(1,11):
        x,y = calibration.point(slot)
        samples.append(np.median(image[max(0,y-1):y+2,max(0,x-1):x+2,:3],axis=(0,1)))
    groups = [g for g in range(1,14) if all(
        np.linalg.norm(samples[c.slot-1]-np.asarray(c.rgb))<=4 for c in palette.by_group(g))]
    if len(groups)!=1:
        raise SelectionError('校正位置對不上展開的色盤，請重新校正或確認色盤未被遮住。')
    chip,_ = selected_chip(image,calibration.strip,(calibration.chip_width,calibration.chip_height))
    # 每個可點擊位置必須位於色帶範圍；端點只允許向內切組。
    if not calibration.strip[0]<chip[0]<calibration.strip[2]:
        raise SelectionError('色帶白框位置無效。')
    return groups[0],chip


def _color_center(image,rgb,k):
    point,fill = find_swatch(image,rgb,k=k)
    if point is None or fill<.90:
        return None
    mask = np.linalg.norm(image.astype(np.int16)-np.asarray(rgb),axis=2)<3
    # 取實心色塊的連通區域中心，避免主色色帶或白色選取邊框拉偏。
    component = Image.fromarray(mask.astype(np.uint8)*255).copy()
    ImageDraw.floodfill(component,tuple(map(round,point)),128)
    ys,xs = np.nonzero(np.asarray(component)==128)
    if len(xs)<k*k:
        return None
    return float((xs.min()+xs.max())/2),float((ys.min()+ys.max())/2)


def calibrate_palette(image,roi,client_size,palette):
    image = image.convert('RGB')
    w,h = image.size
    cw,ch = client_size
    if abs(w/h-cw/ch)>.01:
        raise ValueError('請貼上比例與遊戲一致、未裁切的完整遊戲截圖。')
    x0,y0,x1,y1 = map(round,roi)
    if not (0<=x0<x1<=w and 0<=y0<y1<=h):
        raise ValueError('請框選包含主色色帶和下方兩欄色塊的區域。')
    # 限制運算量；最後仍以原始截圖驗證所有實際點擊位置。
    scale = min(1,1600/w)
    small = np.asarray(image.resize((round(w*scale),round(h*scale)),Image.Resampling.NEAREST))
    sx0,sy0,sx1,sy1 = map(lambda v:round(v*scale),(x0,y0,x1,y1))
    region = small[sy0:sy1,sx0:sx1]
    k = max(6,round(min(region.shape[:2])*.045))
    candidates = []
    for group in range(1,14):
        colors = palette.by_group(group)
        first = _color_center(region,colors[0].rgb,k)
        if first is None:
            continue
        points = [first]+[_color_center(region,c.rgb,k) for c in colors[1:]]
        if any(p is None for p in points):
            continue
        rows = np.array([(c.slot-1)//2 for c in colors])
        ys = np.array([p[1] for p in points])
        dy,top = np.polyfit(rows,ys,1)
        dy,top = float(dy),float(top)
        left = float(np.median([p[0] for c,p in zip(colors,points) if c.slot%2]))
        right = float(np.median([p[0] for c,p in zip(colors,points) if not c.slot%2]))
        if dy<5 or left>=right or max(abs(ys-(top+rows*dy)))>3:
            continue
        if any(abs(p[0]-(left if c.slot%2 else right))>3 for c,p in zip(colors,points)):
            continue
        left,right,top,dy = ((left+sx0)/scale,(right+sx0)/scale,(top+sy0)/scale,dy/scale)
        dx = right-left
        band = (max(x0,left-dx*.5),max(y0,top-dy*1.4),min(x1,right+dx*.3),top-dy*.5)
        try:
            chip,chip_height = selected_chip(np.asarray(image),band)
            fx,fy = cw/w,ch/h
            result = PaletteCalibration(cw,ch,left*fx,right*fx,top*fy,dy*fy,
                                        tuple(v*(fx if i%2==0 else fy) for i,v in enumerate(band)),
                                        chip[2]*fx,chip_height*fy)
            result.validate()
            # 在截圖座標驗證（解析度可不同）。
            original = PaletteCalibration(w,h,left,right,top,dy,band,chip[2],chip_height)
            found,_ = verify_calibration(np.asarray(image),original,palette)
            if found==group:
                candidates.append((result,group))
        except ValueError:
            continue
    if len(candidates)!=1:
        raise ValueError('無法唯一辨識色盤，請重新框選：須包含主色色帶與下方全部色塊，避開左側調色盤圖示。')
    return candidates[0]
