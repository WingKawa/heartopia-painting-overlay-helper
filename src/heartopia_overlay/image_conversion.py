"""一般圖片轉為遊戲色盤；縮圖／裁切後以 Lab 色距配色。"""
import io
from dataclasses import dataclass
import numpy as np
from PIL import Image, ImageCms, ImageOps
from .palette import Palette
from .target import TargetGrid


@dataclass(frozen=True)
class ColorAdjustments:
    temperature: float = 0
    brightness: float = 0
    contrast: float = 0
    whites: float = 0
    blacks: float = 0
    saturation: float = 0

    def __post_init__(self):
        for value in vars(self).values():
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or not -100<=value<=100:
                raise ValueError('色彩調整必須介於 -100 與 100')


def adjust_colors(rgb, settings):
    """調整縮圖後的 RGB，最後才配對遊戲色盤；零值維持原始像素。"""
    if not any(vars(settings).values()):
        return rgb
    values = np.asarray(rgb,dtype=np.float64)/255
    warmth = settings.temperature/100*.12
    values = values+np.array([warmth,0,-warmth])
    luminance = values @ np.array([.2126,.7152,.0722])
    values = luminance[...,None]+(values-luminance[...,None])*(1+settings.saturation/100)
    values = (values-.5)*2**(settings.contrast/100)+.5
    values += settings.brightness/100*.5
    luminance = np.clip(values @ np.array([.2126,.7152,.0722]),0,1)
    # 白位與黑位分別偏重亮部、暗部；正值讓白更亮、黑更深。
    values += (settings.whites/100*.65*luminance**2-settings.blacks/100*.65*(1-luminance)**2)[...,None]
    return np.rint(np.clip(values,0,1)*255).astype(np.uint8)


def open_image(path):
    with Image.open(path) as image:
        image.load()
        image = ImageOps.exif_transpose(image)
        profile = image.info.get('icc_profile')
        rgba = image.convert('RGBA')
        if profile:
            try:
                rgb = ImageCms.profileToProfile(image.convert('RGB'),
                        ImageCms.ImageCmsProfile(io.BytesIO(profile)),ImageCms.createProfile('sRGB'),outputMode='RGB')
                rgb.putalpha(rgba.getchannel('A'))
                rgba = rgb
            except (OSError,ValueError,ImageCms.PyCMSError):
                pass
        return rgba


def _lab(rgb):
    rgb = np.asarray(rgb,dtype=np.float64)/255
    linear = np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    xyz = linear @ np.array([[.4124564,.3575761,.1804375],
                             [.2126729,.7151522,.0721750],
                             [.0193339,.1191920,.9503041]]).T
    xyz /= np.array([.95047,1,1.08883])
    f = np.where(xyz>(6/29)**3,np.cbrt(xyz),xyz/(3*(6/29)**2)+4/29)
    return np.stack((116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])),axis=-1)


def convert_image(source,w,h,mode='完整保留',crop=None,adjustments=None):
    adjustments = adjustments or ColorAdjustments()
    if not isinstance(adjustments,ColorAdjustments):
        raise ValueError('色彩調整設定無效')
    if not isinstance(w,int) or not isinstance(h,int) or w<1 or h<1:
        raise ValueError('像素寬高必須是正整數')
    # 預乘透明度縮放，避免透明邊緣產生黑色暈邊。
    image = source.convert('RGBA').convert('RGBa')
    if crop is not None:
        x0,y0,x1,y1 = crop
        if not (np.isfinite(crop).all() and 0<=x0<x1<=source.width and 0<=y0<y1<=source.height):
            raise ValueError('裁切範圍必須位於原圖內，且寬高大於零')
        # EXTENT 支援小數像素，框線與實際取樣一致，不把極窄選區四捨五入成空圖。
        image = image.transform((max(1,round(x1-x0)),max(1,round(y1-y0))),
                                Image.Transform.EXTENT,tuple(crop),Image.Resampling.BICUBIC)
    if mode=='裁切填滿':
        image = ImageOps.fit(image,(w,h),method=Image.Resampling.LANCZOS)
    elif mode=='完整保留':
        image = ImageOps.contain(image,(w,h),method=Image.Resampling.LANCZOS)
        padded = Image.new('RGBa',(w,h))
        padded.paste(image,((w-image.width)//2,(h-image.height)//2))
        image = padded
    elif mode=='拉伸':
        image = image.resize((w,h),Image.Resampling.LANCZOS)
    else:
        raise ValueError('未知的縮放方式')
    arr = np.asarray(image.convert('RGBA'))
    opaque = arr[:,:,3]>=128
    adjusted = adjust_colors(arr[:,:,:3][opaque],adjustments)
    colors,inverse = np.unique(adjusted,axis=0,return_inverse=True)
    palette = Palette.load()
    reference = _lab([c.rgb for c in palette.colors])
    matched = np.empty(len(colors),dtype=np.int16)
    for start in range(0,len(colors),4096):
        batch = _lab(colors[start:start+4096])
        distances = ((batch[:,None,:]-reference[None,:,:])**2).sum(axis=2)
        matched[start:start+len(batch)] = distances.argmin(axis=1)
    grid = np.full((h,w),-1,dtype=np.int16)
    grid[opaque] = matched[inverse]
    return TargetGrid(w,h,[[int(v) if v>=0 else None for v in row] for row in grid])


def target_image(target,palette=None):
    palette = palette or Palette.load()
    image = Image.new('RGBA',(target.w,target.h))
    image.putdata([(*palette.by_index(v).rgb,255) if v is not None else (0,0,0,0)
                   for row in target.cells for v in row])
    return image
