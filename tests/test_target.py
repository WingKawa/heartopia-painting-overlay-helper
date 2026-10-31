import numpy as np
import pytest
from PIL import Image

from heartopia_overlay.errors import TargetError
from heartopia_overlay.palette import Palette
from heartopia_overlay.target import SNAP_TOLERANCE, TRANSPARENT, VALID_SIZES, load_target

PAL = Palette.load()


def _write(tmp_path, arr, name="t.png"):
    path = tmp_path / name
    Image.fromarray(arr, mode="RGBA").save(path)
    return path


def _solid(w, h, rgb, alpha=255):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[:, :, :3] = rgb
    arr[:, :, 3] = alpha
    return arr


def test_valid_sizes_has_20_entries():
    assert len(VALID_SIZES) == 20
    assert (150, 150) in VALID_SIZES and (18, 30) in VALID_SIZES


def test_loads_1to1_image(tmp_path):
    idx = PAL.by_label("7-3").index
    grid = load_target(_write(tmp_path, _solid(30, 18, PAL.by_index(idx).rgb)))
    assert (grid.w, grid.h) == (30, 18)
    assert all(v == idx for row in grid.cells for v in row)


def test_downsamples_30x_upscaled_image(tmp_path):
    """『下載純淨像素圖』是 30 倍放大，必須無損還原。"""
    rgb_a, rgb_b = PAL.by_label("2-1").rgb, PAL.by_label("9-4").rgb
    arr = _solid(900, 540, rgb_a)        # 30x18 的 30 倍
    arr[:30, :30, :3] = rgb_b            # 左上角那一格換色
    grid = load_target(_write(tmp_path, arr))
    assert (grid.w, grid.h) == (30, 18)
    assert grid.cells[0][0] == PAL.by_label("9-4").index
    assert grid.cells[0][1] == PAL.by_label("2-1").index


def test_transparent_pixels_become_skip(tmp_path):
    arr = _solid(30, 18, PAL.by_label("5-2").rgb)
    arr[0, 0, 3] = 0
    grid = load_target(_write(tmp_path, arr))
    assert grid.cells[0][0] is TRANSPARENT
    assert grid.cells[0][1] == PAL.by_label("5-2").index


def test_rejects_illegal_color_with_coordinates(tmp_path):
    arr = _solid(30, 18, PAL.by_label("5-2").rgb)
    arr[3, 7, :3] = (1, 2, 3)
    with pytest.raises(TargetError) as e:
        load_target(_write(tmp_path, arr))
    assert "(7, 3)" in str(e.value)
    assert "1, 2, 3" in str(e.value)


def test_rejects_unknown_size_and_suggests_nearest(tmp_path):
    with pytest.raises(TargetError) as e:
        load_target(_write(tmp_path, _solid(31, 19, PAL.by_label("5-2").rgb)))
    msg = str(e.value)
    assert "31x19" in msg
    assert "30x18" in msg


def test_rejects_label_grid_image_with_specific_hint(tmp_path):
    """標號網格參考圖：30 倍放大但格線與標號文字讓中心取樣拿到非法色。"""
    arr = _solid(900, 540, PAL.by_label("5-2").rgb)
    arr[::30, :, :3] = (0, 0, 0)            # 格線
    arr[10:20, 10:20, :3] = (0, 0, 0)       # 中心的標號文字
    with pytest.raises(TargetError) as e:
        load_target(_write(tmp_path, arr))
    assert "1:1 像素" in str(e.value)


def test_snap_tolerance_guarantees_a_unique_match():
    """吸附必須是可證明唯一的，不是「選一個比較像的」。

    125 色兩兩最小距離 5.00，容許值 2.0 時 2*2.0 = 4.0 < 5.00，
    所以落在某合法色 2.0 以內的顏色不可能同時落在另一個合法色的 2.0 以內。
    這個不變量若被破壞（例如遊戲改版讓最小色距變小），吸附就變成猜測。
    """
    lo, _ = PAL.min_pairwise_distance()
    assert 2 * SNAP_TOLERANCE < lo


def test_snaps_off_by_one_channel_noise(tmp_path):
    """輸入圖像每通道 ±1 的微差應吸附至唯一的色盤顏色。"""
    c = PAL.by_label("10-1")
    arr = _solid(30, 18, c.rgb)
    arr[5, 5, :3] = (c.rgb[0] - 1, c.rgb[1], c.rgb[2] + 1)
    grid = load_target(_write(tmp_path, arr))
    assert grid.cells[5][5] == c.index
    assert grid.snapped == 1


def test_exact_colors_are_not_counted_as_snapped(tmp_path):
    grid = load_target(_write(tmp_path, _solid(30, 18, PAL.by_label("5-2").rgb)))
    assert grid.snapped == 0


def test_rejects_colors_beyond_snap_tolerance(tmp_path):
    c = PAL.by_label("10-1")
    arr = _solid(30, 18, c.rgb)
    arr[2, 3, :3] = (c.rgb[0] + 20, c.rgb[1], c.rgb[2])
    with pytest.raises(TargetError) as e:
        load_target(_write(tmp_path, arr))
    assert "(3, 2)" in str(e.value)


@pytest.mark.parametrize('w,h',[(120,120),(317,83),(1,231),(450,1)])
def test_manual_mode_accepts_arbitrary_pixel_dimensions(tmp_path,w,h):
    c = PAL.by_label('5-2')
    grid = load_target(_write(tmp_path,_solid(w,h,c.rgb)),unrestricted=True)
    assert (grid.w,grid.h)==(w,h)
    assert grid.cells[-1][-1]==c.index


def test_manual_mode_does_not_guess_upscale_factor(tmp_path):
    c = PAL.by_label('5-2')
    grid = load_target(_write(tmp_path,_solid(900,540,c.rgb)),unrestricted=True)
    assert (grid.w,grid.h)==(900,540)


def test_manual_mode_keeps_color_validation_and_transparency(tmp_path):
    image = _solid(31,19,PAL.by_label('5-2').rgb)
    image[0,0] = (1,2,3,0)
    grid = load_target(_write(tmp_path,image),unrestricted=True)
    assert grid.cells[0][0] is TRANSPARENT
    image[3,7] = (1,2,3,255)
    with pytest.raises(TargetError,match=r'\(7, 3\)'):
        load_target(_write(tmp_path,image),unrestricted=True)


def test_fully_transparent_arbitrary_image(tmp_path):
    grid = load_target(_write(tmp_path,_solid(7,9,(1,2,3),alpha=0)),unrestricted=True)
    assert all(value is TRANSPARENT for row in grid.cells for value in row)
