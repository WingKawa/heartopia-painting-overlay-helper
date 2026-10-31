import numpy as np
import pytest
from PIL import Image
from heartopia_overlay.image_conversion import convert_image, open_image, target_image
from heartopia_overlay.palette import Palette
from heartopia_overlay.image_conversion import ColorAdjustments, adjust_colors


def test_adjustments_neutral_and_tonal_direction():
    source = np.array([[30,30,30],[128,128,128],[225,225,225]],dtype=np.uint8)
    assert np.array_equal(adjust_colors(source,ColorAdjustments()),source)
    assert adjust_colors(source,ColorAdjustments(whites=60))[2,0]>source[2,0]
    assert adjust_colors(source,ColorAdjustments(blacks=60))[0,0]<source[0,0]
    assert adjust_colors(source,ColorAdjustments(brightness=30))[1,0]>source[1,0]
    contrast = adjust_colors(source,ColorAdjustments(contrast=60))
    assert contrast[2,0]-contrast[0,0]>source[2,0]-source[0,0]
    cool = adjust_colors(source,ColorAdjustments(temperature=-50))
    assert cool[1,2]>cool[1,0]
    neutral = adjust_colors(np.array([[200,50,30]]),ColorAdjustments(saturation=-100))
    assert neutral[0,0]==neutral[0,1]==neutral[0,2]


@pytest.mark.parametrize('value',[float('nan'),float('inf'),101,-101,True,'10'])
def test_invalid_adjustment_rejected(value):
    with pytest.raises(ValueError):
        ColorAdjustments(brightness=value)


def test_adjusted_conversion_keeps_transparency_palette_and_original():
    source = Image.new('RGBA',(3,1))
    source.putdata([(230,230,230,255),(25,25,25,255),(200,0,0,0)])
    before = source.tobytes()
    result = convert_image(source,3,1,'拉伸',adjustments=ColorAdjustments(whites=100,blacks=100))
    palette = Palette.load()
    assert result.cells[0][:2]==[palette.by_label('1-5').index,palette.by_label('1-1').index]
    assert result.cells[0][2] is None
    assert source.tobytes()==before
    assert convert_image(source,3,1,'拉伸').cells==convert_image(source,3,1,'拉伸',adjustments=ColorAdjustments()).cells


def test_all_125_exact_colors_round_trip_without_changes():
    palette = Palette.load()
    source = Image.new('RGB',(125,1))
    source.putdata([color.rgb for color in palette.colors])
    target = convert_image(source,125,1,'拉伸')
    assert target.cells[0]==list(range(125))
    assert np.asarray(target_image(target).convert('RGB'))[0].tolist()==[list(c.rgb) for c in palette.colors]


def test_fit_padding_is_transparent_and_crop_fills_canvas():
    source = Image.new('RGBA',(20,10),(240,80,20,255))
    target = convert_image(source,10,10,'完整保留')
    assert all(v is None for v in target.cells[0])
    assert all(v is not None for v in target.cells[4])
    crop = convert_image(source,10,10,'裁切填滿')
    assert all(v is not None for row in crop.cells for v in row)


def test_transparent_rgb_does_not_turn_into_black_fringe():
    source = Image.new('RGBA',(10,10),(0,0,0,0))
    for y in range(3,7):
        for x in range(3,7):
            source.putpixel((x,y),(255,255,255,255))
    target = convert_image(source,30,30,'拉伸')
    white = Palette.load().by_label('1-5').index
    assert {v for row in target.cells for v in row if v is not None}=={white}


def test_real_jpeg_can_be_opened_and_converted(tmp_path):
    path = tmp_path/'photo.jpg'
    Image.new('RGB',(40,30),(123,46,211)).save(path)
    source = open_image(path)
    target = convert_image(source,13,7,'拉伸')
    assert (target.w,target.h)==(13,7)
    assert all(0<=v<125 for row in target.cells for v in row)


@pytest.mark.parametrize('w,h',[(0,3),(-1,3),(3,0)])
def test_rejects_invalid_pixel_dimensions(w,h):
    with pytest.raises(ValueError):
        convert_image(Image.new('RGB',(2,2)),w,h)


def test_manual_crop_uses_chosen_region_instead_of_center():
    palette = Palette.load()
    source = Image.new('RGB',(20,10),palette.by_index(0).rgb)
    source.paste(palette.by_index(1).rgb,(10,0,20,10))
    left = convert_image(source,10,10,'拉伸',crop=(0,0,10,10))
    right = convert_image(source,10,10,'拉伸',crop=(10,0,20,10))
    assert {v for row in left.cells for v in row}=={0}
    assert {v for row in right.cells for v in row}=={1}
    tiny = convert_image(source,5,5,'拉伸',crop=(1,.2,1.1,.3))
    assert (tiny.w,tiny.h)==(5,5)


@pytest.mark.parametrize('crop',[(-1,0,10,10),(0,0,0,10),(0,0,21,10)])
def test_invalid_crop_is_not_silently_padded(crop):
    with pytest.raises(ValueError):
        convert_image(Image.new('RGB',(20,10)),10,10,crop=crop)
