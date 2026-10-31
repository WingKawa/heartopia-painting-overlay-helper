"""單次色盤選色的畫面辨識與步驟規劃；不處理畫布填色。"""
from dataclasses import dataclass
import numpy as np


class SelectionError(ValueError):
    pass


@dataclass(frozen=True)
class PaletteView:
    group: int
    width: int
    height: int
    chip: tuple
    grid: tuple | None = None
    strip: tuple | None = None

    def point(self, slot):
        if self.grid is not None:
            left,right,y0,dy = self.grid
            return round(left if slot%2 else right),round(y0+dy*((slot-1)//2))
        return (round((1842 if slot % 2 else 1973)*self.width/2048),
                round((438+97*((slot-1)//2))*self.height/1152))

    def neighbor(self, target):
        x,y,width = self.chip
        point = round(x+(width if target>self.group else -width)),round(y)
        if self.strip and not (self.strip[0]<point[0]<self.strip[2] and self.strip[1]<point[1]<self.strip[3]):
            raise SelectionError('切換主色組的位置超出校正色帶，已停止。')
        return point


def observe_palette(image, palette, calibration=None):
    """依已驗證的16:9版面取樣完整色組；不符合時拒絕產生點擊座標。"""
    h,w = image.shape[:2]
    if calibration is not None:
        from .palette_calibration import verify_calibration
        group,chip = verify_calibration(image,calibration,palette)
        return PaletteView(group,w,h,chip,
                           (calibration.left_x,calibration.right_x,calibration.y0,calibration.dy),calibration.strip)
    if w<1280 or abs(w/h-16/9)>.015:
        raise SelectionError('目前選色支援16:9遊戲畫面，且寬度至少1280像素。')
    probe = PaletteView(0,w,h,())
    samples = []
    radius = max(1,round(w/2048*2))
    for slot in range(1,11):
        x,y = probe.point(slot)
        samples.append(np.median(image[y-radius:y+radius+1,x-radius:x+radius+1],axis=(0,1)))
    matches = []
    for group in range(1,14):
        colors = palette.by_group(group)
        errors = [np.linalg.norm(samples[c.slot-1]-np.asarray(c.rgb)) for c in colors]
        if max(errors)<=4:
            matches.append(group)
    if len(matches)!=1:
        raise SelectionError('無法辨識展開的色盤；請確認遊戲色盤已展開且未被遮住。')
    # 限制在主色長條內，排除上方返回鈕和下方色塊的選取白框。
    x0,x1 = round(w*1818/2048),round(w*2009/2048)
    y0,y1 = round(h*309/1152),round(h*386/1152)
    ys,xs = np.nonzero(image[y0:y1,x0:x1].min(axis=2)>=245)
    if len(xs)<30*w*h/(2048*1152):
        raise SelectionError('找不到主色色帶的選取白框。')
    left,right,top,bottom = xs.min(),xs.max()+1,ys.min(),ys.max()+1
    cw,ch = right-left,bottom-top
    if not (32*w/2048<=cw<=50*w/2048 and 55*h/1152<=ch<=75*h/1152):
        raise SelectionError('主色色帶的位置或尺寸不符，已停止選色。')
    return PaletteView(matches[0],w,h,(x0+(left+right)/2,y0+(top+bottom)/2,cw))


class SelectionPlan:
    """每次只產生一個經觀測確認的步驟，禁止盲目連點。"""
    def __init__(self,color):
        self.color = color
        self.previous = None
        self.steps = 0

    def next(self,view):
        if self.previous is not None:
            expected = self.previous+(1 if self.color.group>self.previous else -1)
            if view.group!=expected:
                raise SelectionError('主色組沒有依預期切換，已停止；請重新嘗試。')
        if view.group==self.color.group:
            return 'select',view.point(self.color.slot)
        if self.steps>=12:
            raise SelectionError('色盤切換次數超過上限，已停止。')
        self.previous = view.group
        self.steps += 1
        return 'navigate',view.neighbor(self.color.group)
