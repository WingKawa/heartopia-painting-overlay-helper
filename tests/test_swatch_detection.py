import numpy as np
import pytest
from heartopia_overlay.palette import Palette
from heartopia_overlay.swatch_detection import find_swatch


@pytest.mark.parametrize('slot',range(1,11))
def test_finds_actual_palette_color_without_grid_navigation(panel_group2,slot):
    color=Palette.load().by_label(f'2-{slot}')
    point,fill=find_swatch(panel_group2,color.rgb,k=30)
    assert point is not None and fill>=.9
    x,y=map(round,point)
    assert tuple(panel_group2[y,x])==color.rgb


def test_absent_color_does_not_produce_a_position():
    image=np.full((200,200,3),7,dtype=np.uint8)
    assert find_swatch(image,(200,100,50))==(None,0.0)
