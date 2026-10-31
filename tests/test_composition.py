from heartopia_overlay.composition import Composition
from heartopia_overlay.target import TargetGrid
from heartopia_overlay.palette import Palette


def test_image_offset_and_canvas_clipping_leave_source_unchanged():
    source = TargetGrid(3,2,[[0,1,2],[3,None,4]])
    c = Composition(source,2,2)
    c.move_image(-1,1)
    assert c.cell(0,0) is None
    assert c.cell(0,1)==1
    assert c.cell(1,1)==2
    assert c.cell(-1,1) is None
    assert source.cells==[[0,1,2],[3,None,4]]
    c.resize(6,4)
    c.center()
    assert (c.offset_x,c.offset_y)==(1,1)
    assert c.cell(1,1)==0


def test_preview_crops_outside_and_preserves_transparent_background():
    palette = Palette.load()
    c = Composition(TargetGrid(2,1,[[0,None]]),4,2)
    c.move_image(1,1)
    image = c.preview(palette,(40,20))
    assert image.size==(40,20)
    assert image.getpixel((15,15))==palette.by_index(0).rgb
    assert image.getpixel((25,15))!=palette.by_index(0).rgb
    c.move_image(100,100)
    assert c.preview(palette,(40,20)).getpixel((15,15))!=palette.by_index(0).rgb


def test_large_canvas_preview_does_not_allocate_full_canvas():
    c = Composition(TargetGrid(1,1,[[0]]),1000000,1000000)
    assert c.preview(Palette.load(),(50,50)).size==(50,50)


def test_minimap_filters_only_selected_color_and_can_restore_all():
    palette = Palette.load()
    c = Composition(TargetGrid(2,1,[[0,1]]),2,1)
    selected = c.preview(palette,(20,10),selected_color=0)
    assert selected.getpixel((5,5))==palette.by_index(0).rgb
    assert selected.getpixel((15,5))!=palette.by_index(1).rgb
    all_colors = c.preview(palette,(20,10))
    assert all_colors.getpixel((15,5))==palette.by_index(1).rgb


def test_export_keeps_full_canvas_all_colors_and_transparency():
    from heartopia_overlay.target import load_target
    from heartopia_overlay.image_conversion import convert_image
    palette = Palette.load()
    c = Composition(TargetGrid(3,2,[[0,1,2],[3,None,4]]),3,3)
    c.move_image(-1,1)
    exported = c.export_image(palette)
    assert exported.size==(3,3)
    assert exported.getpixel((0,0))[3]==0
    assert exported.getpixel((2,1))[3]==0
    assert exported.getpixel((0,1))==(*palette.by_index(1).rgb,255)
    assert exported.getpixel((1,1))==(*palette.by_index(2).rgb,255)
    assert exported.getpixel((0,2))[3]==0
    assert convert_image(exported,3,3,'拉伸').cells==[[None,None,None],[1,2,None],[None,4,None]]
