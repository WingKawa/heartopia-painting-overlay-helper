"""手動疊圖工作階段：包含轉圖後像素快照，原始圖片搬走也可還原。"""
import base64
import json
import math
import os
import pathlib
import tempfile
import zlib
from .target import TargetGrid


def pack_grid(grid):
    pixels = bytes(255 if value is None else value for row in grid.cells for value in row)
    return {'width':grid.w,'height':grid.h,
            'pixels':base64.b64encode(zlib.compress(pixels,6)).decode('ascii')}


def unpack_grid(data):
    w,h = data['width'],data['height']
    if type(w) is not int or type(h) is not int or w<1 or h<1:
        raise ValueError('保存的圖片尺寸無效')
    compressed = base64.b64decode(data['pixels'],validate=True)
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(compressed,w*h+1)
    if len(pixels)!=w*h or not decoder.eof or decoder.unused_data:
        raise ValueError('保存的像素資料不完整')
    if any(value!=255 and value>=125 for value in pixels):
        raise ValueError('保存的像素顏色無效')
    return TargetGrid(w,h,[[None if value==255 else value for value in pixels[y*w:(y+1)*w]] for y in range(h)])


def validate(state):
    if not isinstance(state,dict) or state.get('version')!=1:
        raise ValueError('不支援的工作階段格式')
    def number(key,minimum=None,maximum=None):
        value = state[key]
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError(f'保存的 {key} 無效')
        if minimum is not None and value<minimum or maximum is not None and value>maximum:
            raise ValueError(f'保存的 {key} 超出範圍')
    number('gap',0,1000)
    number('cell_size',1,1000)
    number('left')
    number('top')
    number('opacity',.15,.85)
    for key in ('canvas_width','canvas_height'):
        if type(state[key]) is not int or state[key]<1:
            raise ValueError('保存的畫布尺寸無效')
    for key in ('offset_x','offset_y'):
        if type(state[key]) is not int:
            raise ValueError('保存的圖片位置無效')
    if state['ui_scale'] not in ('100%','125%','150%','175%','200%'):
        raise ValueError('保存的介面倍率無效')
    if state['map_mode'] not in ('瀏覽範圍','擺放圖片'):
        raise ValueError('保存的小地圖模式無效')
    color = state['selected_color']
    if color is not None and (type(color) is not int or not 0<=color<125):
        raise ValueError('保存的選色無效')
    clip = state['clip']
    if not isinstance(clip,list) or len(clip)!=4 or not all(type(v) in (int,float) and math.isfinite(v) for v in clip):
        raise ValueError('保存的觀看範圍無效')
    if clip[2]<clip[0] or clip[3]<clip[1]:
        raise ValueError('保存的觀看範圍無效')
    for key in ('canvas_custom','sync_drag','enabled','aligning'):
        if type(state[key]) is not bool:
            raise ValueError(f'保存的 {key} 無效')
    if 'arrow_nudge' in state and type(state['arrow_nudge']) is not bool:
        raise ValueError('保存的方向鍵微調開關無效')
    if 'intro_seen' in state and type(state['intro_seen']) is not bool:
        raise ValueError('保存的教學狀態無效')
    if 'auto_color_enabled' in state and type(state['auto_color_enabled']) is not bool:
        raise ValueError('保存的自動選色開關無效')
    if 'auto_color_notice_version' in state and (type(state['auto_color_notice_version']) is not int or state['auto_color_notice_version']<0):
        raise ValueError('保存的自動選色說明版本無效')
    if state.get('palette_calibration') is not None:
        from .palette_calibration import PaletteCalibration
        PaletteCalibration.load(state['palette_calibration'])
    if state.get('stage_tab','作品設定') not in ('作品設定','疊層設定','繪畫工具'):
        raise ValueError('保存的工作階段頁籤無效')
    return state


class SessionStore:
    def __init__(self,path):
        self.path = pathlib.Path(path)

    def load(self):
        if not self.path.exists():
            return None
        try:
            state = validate(json.loads(self.path.read_text(encoding='utf-8')))
            source = unpack_grid(state['source']) if state.get('source') else None
        except (KeyError,TypeError,zlib.error,OverflowError) as e:
            raise ValueError('保存的工作階段無法讀取') from e
        return state,source

    def save(self,state):
        validate(state)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.path.parent,
                                             prefix='assist-session-',suffix='.tmp',delete=False) as stream:
                temporary = pathlib.Path(stream.name)
                json.dump(state,stream,ensure_ascii=False,allow_nan=False,separators=(',',':'))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary,self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
