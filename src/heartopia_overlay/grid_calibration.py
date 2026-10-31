"""從截圖中的規則灰色格線量測格距；純影像運算。"""
from dataclasses import dataclass
import numpy as np


def normalize_screenshot(image,client_size,frames=()):
    """移除已知遊戲視窗外框；也接受只含客戶區或等比例縮放的截圖。"""
    w,h = image.size
    cw,ch = client_size
    if min(w,h,cw,ch)<=0:
        raise ValueError('遊戲或截圖尺寸無效。')
    candidates = [(cw,ch,0,0,cw,ch),*frames]
    scored = []
    for fw,fh,x0,y0,x1,y1 in candidates:
        if min(fw,fh)<=0 or not (0<=x0<x1<=fw and 0<=y0<y1<=fh):
            continue
        sx,sy = w/fw,h/fh
        error = abs(sx-sy)/max(sx,sy)
        scored.append((error,(fw,fh,x0,y0,x1,y1)))
    error,frame = min(scored,key=lambda entry:entry[0])
    if error>.006:
        raise ValueError('截圖比例不符：請貼上完整遊戲視窗截圖（可含標題列），不要裁切或使用整個桌面的截圖。')
    fw,fh,x0,y0,x1,y1 = frame
    box = tuple(round(value*scale) for value,scale in zip((x0,y0,x1,y1),(w/fw,h/fh,w/fw,h/fh)))
    return image.crop(box),box!=(0,0,w,h)


@dataclass(frozen=True)
class GridMeasurement:
    gap: float
    size: float
    pitch: float
    vertical_lines: int
    horizontal_lines: int


def measure_axis(profile):
    indices = np.flatnonzero(profile>=.55)
    if not len(indices):
        raise ValueError('找不到清楚格線，請提高遊戲倍率或重新框選畫布內部。')
    bands = np.split(indices,np.flatnonzero(np.diff(indices)>1)+1)
    # 排除選區邊緣截到的半條格線。
    bands = [b for b in bands if b[0]>0 and b[-1]<len(profile)-1]
    if len(bands)<4:
        raise ValueError('每個方向至少需要4條完整格線，請擴大選取範圍。')
    centers = np.array([(b[0]+b[-1])/2 for b in bands])
    widths = np.array([len(b) for b in bands])
    thin_mask = widths<=np.median(widths)*1.4
    thin_indices = np.flatnonzero(thin_mask)
    if len(thin_indices)<3:
        raise ValueError('可辨識的一般格線不足。')
    differences = np.diff(centers[thin_mask])/np.diff(thin_indices)
    initial = float(np.median(differences))
    if initial<5 or initial>1000 or widths.max()>initial*.45:
        raise ValueError('線條太粗或格子太小，無法可靠校正。')
    # 不猜漏線的數量：不規則或畫面被遮擋時請玩家改選區。
    if np.max(np.abs(differences-initial))>max(2,initial*.045):
        raise ValueError('格線間距不規則，請避開工具列、疊層及已遮擋的區域。')
    # 遊戲每5格的粗線可能往單側加粗，不能把粗線中心拿來擬合。
    pitch,offset = np.polyfit(thin_indices,centers[thin_mask],1)
    if np.max(np.abs(centers[thin_mask]-(offset+thin_indices*pitch)))>max(1.5,pitch*.02):
        raise ValueError('格線排列不規則，無法可靠校正。')
    # 每5格的粗線不當成一般格距；取較細格線的典型寬度。
    thin = widths[thin_mask]
    gap = float(np.median(thin))
    return float(pitch),gap,len(bands)


def measure_grid(image,roi,client_size):
    image = np.asarray(image.convert('RGB')) if hasattr(image,'convert') else np.asarray(image)
    h,w = image.shape[:2]
    cw,ch = client_size
    if min(w,h,cw,ch)<=0 or abs(w/h-cw/ch)>.01:
        raise ValueError('請貼上與遊戲比例一致、未裁切的完整遊戲截圖。')
    x0,y0,x1,y1 = map(lambda v:int(round(v)),roi)
    if not (0<=x0<x1<=w and 0<=y0<y1<=h) or min(x1-x0,y1-y0)<32:
        raise ValueError('請在截圖中框選足夠大的格線區域。')
    pixels = image[y0:y1,x0:x1,:3].astype(np.int16)
    low,high = pixels.min(axis=2),pixels.max(axis=2)
    gray = (high-low<=15)&(low>=65)&(high<=210)
    px,gx,nx = measure_axis(gray.mean(axis=0))
    py,gy,ny = measure_axis(gray.mean(axis=1))
    px,gx,py,gy = px*cw/w,gx*cw/w,py*ch/h,gy*ch/h
    if abs(px-py)>max(1.5,max(px,py)*.02) or abs(gx-gy)>max(2,max(gx,gy)*.3):
        raise ValueError('水平與垂直格線不一致，請確認框選範圍只有遊戲畫布。')
    pitch,gap = (px+py)/2,(gx+gy)/2
    if not (0<=gap<=1000 and 1<=pitch-gap<=1000):
        raise ValueError('量測結果超出可用範圍。')
    return GridMeasurement(gap,pitch-gap,pitch,nx,ny)
