"""大量可見格子以一張點陣影像繪製，避免建立數萬個 Tk 項目。"""
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont


def use_raster(cell_count,clip,aligning=False,selected=False):
    """整張影像的上傳成本隨面積增加；稀疏、大畫面維持 Canvas。"""
    pixels = max(1,(clip[2]-clip[0])*(clip[3]-clip[1]))
    items_per_cell = 3 if aligning else 4 if selected else 1
    return cell_count*items_per_cell>max(6000,pixels/150)


@lru_cache(maxsize=8)
def label_font(size):
    try:
        return ImageFont.truetype('segoeui.ttf',size)
    except OSError:
        return ImageFont.load_default()


def render_overlay(position,clip,cells,value_at,palette,aligning,picking,selected,key):
    x0,y0,x1,y1 = clip
    image = Image.new('RGB',(max(1,round(x1-x0)),max(1,round(y1-y0))),
                      '#303030' if aligning or picking else key)
    draw = ImageDraw.Draw(image)
    size = position.cell_size or min(position.step_x,position.step_y)
    for col,row,box in cells:
        value = value_at(col,row)
        show = value is not None and (selected is None or aligning or picking or value==selected)
        # Keep the full cell geometry; Pillow clips at the image edge.
        left = position.left+col*position.step_x+(position.step_x-size)/2-x0
        top = position.top+row*position.step_y+(position.step_y-size)/2-y0
        if show:
            draw.rectangle((math.ceil(left),math.ceil(top),math.ceil(left+size)-1,math.ceil(top+size)-1),
                           fill=palette.by_index(value).hex)
            if value==selected and not aligning and not picking and size>=8:
                width = min(4,max(1,size*.025))
                inset = width+1
                frame = (left+inset,top+inset,left+size-inset,top+size-inset)
                draw.rectangle(frame,outline='#111111',width=max(1,round(width+2)))
                draw.rectangle(frame,outline='white',width=max(1,round(width)))
                cx,cy = left+size/2,top+size/2
                radius = min(size*.30,max(5,min(7,size*.10)))
                draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill='white',
                             outline='#111111',width=2 if size>=16 else 1)
        if aligning:
            coords = (box[0]-x0,box[1]-y0,box[2]-x0,box[3]-y0)
            draw.rectangle(coords,outline='#aaaaaa')
            # At tiny scales coordinate labels overlap adjacent cells.
            if min(position.step_x,position.step_y)>=36:
                color = 'black' if show and sum(palette.by_index(value).rgb)>420 else 'white'
                draw.text((position.left+(col+.5)*position.step_x-x0,
                           position.top+(row+.5)*position.step_y-y0),f'{row+1},{col+1}',
                          fill=color,font=label_font(12),anchor='mm')
    return image
