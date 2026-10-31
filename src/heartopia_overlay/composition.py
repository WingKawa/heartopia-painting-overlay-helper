"""原圖、作品畫布與圖片位置；疊層觀看位置由 Placement 獨立管理。"""
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageChops
from .target import TargetGrid


@dataclass
class Composition:
    source: TargetGrid
    w: int
    h: int
    offset_x: int = 0
    offset_y: int = 0
    revision: int = 0

    def __post_init__(self):
        self.resize(self.w,self.h)
        self._image = None

    def resize(self,w,h):
        if not isinstance(w,int) or not isinstance(h,int) or w<1 or h<1:
            raise ValueError('畫布寬高必須是正整數')
        self.w,self.h = w,h
        self.revision += 1

    def move_image(self,x,y):
        point = (int(round(x)),int(round(y)))
        if point != (self.offset_x,self.offset_y):
            self.offset_x,self.offset_y = point
            self.revision += 1

    def center(self):
        self.move_image((self.w-self.source.w)//2,(self.h-self.source.h)//2)

    def cell(self,col,row):
        if not (0<=col<self.w and 0<=row<self.h):
            return None
        x,y = col-self.offset_x,row-self.offset_y
        return self.source.cells[y][x] if 0<=x<self.source.w and 0<=y<self.source.h else None

    def export_image(self,palette=None):
        """輸出完整作品畫布，不套用逐色篩選或小地圖觀看框。"""
        from .image_conversion import target_image
        image = Image.new('RGBA',(self.w,self.h))
        image.paste(target_image(self.source,palette),(self.offset_x,self.offset_y))
        return image

    def preview(self,palette,size,selected_color=None):
        """直接繪製縮圖，不建立畫布寬×高的大型格子陣列。"""
        width,height = size
        result = Image.new('RGB',size,(248,248,248))
        draw = ImageDraw.Draw(result)
        for y in range(0,height,10):
            for x in range(0,width,10):
                if (x//10+y//10)%2:
                    draw.rectangle((x,y,x+9,y+9),fill=(222,222,222))
        if self._image is None:
            self._image = Image.new('RGBA',(self.source.w,self.source.h))
            self._image.putdata([(*palette.by_index(v).rgb,255) if v is not None else (0,0,0,0)
                                 for row in self.source.cells for v in row])
        left,top = max(0,self.offset_x),max(0,self.offset_y)
        right,bottom = min(self.w,self.offset_x+self.source.w),min(self.h,self.offset_y+self.source.h)
        if left<right and top<bottom:
            box = (round(left*width/self.w),round(top*height/self.h),
                   round(right*width/self.w),round(bottom*height/self.h))
            if box[0]<box[2] and box[1]<box[3]:
                crop = self._image.crop((left-self.offset_x,top-self.offset_y,
                                         right-self.offset_x,bottom-self.offset_y))
                if selected_color is not None:
                    # 小地圖與疊層使用同一色號篩選；透明／未選中色回到棋盤背景。
                    rgb = palette.by_index(selected_color).rgb
                    channels = crop.split()
                    mask = channels[3]
                    for channel,value in zip(channels[:3],rgb):
                        mask = ImageChops.multiply(mask,channel.point(lambda v,c=value:255 if v==c else 0))
                    crop.putalpha(mask)
                crop = crop.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.NEAREST)
                result.paste(crop,box[:2],crop)
        return result
