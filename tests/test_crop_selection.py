import pytest
from heartopia_overlay.crop_selection import CropSelection


def test_moving_selection_clamps_to_source_and_preserves_size():
    crop = CropSelection(200,100)
    crop.box = (20,10,100,70)
    crop.move(crop.box,1000,-1000)
    assert crop.box==(120,0,200,60)


def test_resizing_keeps_opposite_corner_and_output_ratio():
    crop = CropSelection(200,100)
    crop.box = (20,10,100,70)
    crop.resize(crop.box,'se',180,95,2)
    x0,y0,x1,y1 = crop.box
    assert (x0,y0)==(20,10)
    assert (x1-x0)/(y1-y0)==pytest.approx(2)
    assert x1<=200 and y1<=100


def test_new_selection_in_reverse_direction_and_extreme_ratio():
    crop = CropSelection(1,100)
    crop.from_anchor(1,100,0,0,-1,-1,100)
    x0,y0,x1,y1 = crop.box
    assert 0<=x0<x1<=1 and 0<=y0<y1<=100
    assert (x1-x0)/(y1-y0)==pytest.approx(100)


def test_ratio_change_keeps_center_when_space_available():
    crop = CropSelection(200,200)
    crop.box = (50,60,150,140)
    crop.fit_ratio(2)
    x0,y0,x1,y1 = crop.box
    assert (x0+x1)/2==100 and (y0+y1)/2==100
    assert (x1-x0)/(y1-y0)==pytest.approx(2)
