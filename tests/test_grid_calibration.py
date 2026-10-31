from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from heartopia_overlay.grid_calibration import measure_grid, normalize_screenshot


@pytest.mark.parametrize('scale',[1,.5])
def test_window_screenshot_removes_title_and_borders_before_measuring(scale):
    source = Image.fromarray(grid())
    framed = Image.new('RGB',(1936,1118),'#303030')
    framed.paste(source,(8,30))
    framed = framed.resize((round(1936*scale),round(1118*scale)),Image.Resampling.NEAREST)
    normalized,trimmed = normalize_screenshot(framed,(1920,1080),[(1936,1118,8,30,1928,1110)])
    assert trimmed and normalized.size==(round(1920*scale),round(1080*scale))
    result = measure_grid(normalized,(0,0,*normalized.size),(1920,1080))
    assert result.pitch==pytest.approx(40,abs=.1)
    assert result.gap==4


def test_client_screenshot_unchanged_and_desktop_not_guessed():
    source = Image.fromarray(grid())
    normalized,trimmed = normalize_screenshot(source,(1920,1080),[(1936,1118,8,30,1928,1110)])
    assert not trimmed and normalized.tobytes()==source.tobytes()
    with pytest.raises(ValueError,match='完整遊戲視窗'):
        normalize_screenshot(Image.new('RGB',(2560,1440)),(1200,900))
from heartopia_overlay.color_picker import ArrowGate


def grid(px=40,py=40,gap=4):
    image = np.full((1080,1920,3),250,dtype=np.uint8)
    for x in range(7,1920,px):
        width = gap*(2 if ((x-7)//px)%5==0 else 1)
        image[:,x:x+width] = 158
    for y in range(13,1080,py):
        width = gap*(2 if ((y-13)//py)%5==0 else 1)
        image[y:y+width] = 158
    return image


@pytest.mark.parametrize('pitch',[12,40,110])
def test_regular_grid_with_asymmetric_major_lines(pitch):
    image = grid(pitch,pitch,2)
    result = measure_grid(image,(0,0,1920,1080),(1920,1080))
    assert result.pitch==pytest.approx(pitch,abs=.01)
    assert result.gap==2
    assert result.size==pytest.approx(pitch-2)


def test_actual_game_lines_and_screenshot_resolution_scaling():
    image = Image.new('RGB',(3840,2160),'white')
    with Image.open(Path(__file__).parent/'fixtures'/'grid_lines.png') as crop:
        image.paste(crop,(787,529))
    result = measure_grid(image,(787,529,2976,1782),(3840,2160))
    assert result.pitch==pytest.approx(164.1,abs=.3)
    assert 15<=result.gap<=17
    scaled = measure_grid(image,(787,529,2976,1782),(2560,1440))
    assert scaled.pitch==pytest.approx(result.pitch*2/3)
    assert scaled.gap==pytest.approx(result.gap*2/3)


def test_reject_no_grid_wrong_aspect_and_non_square_grid():
    with pytest.raises(ValueError):
        measure_grid(np.full((1080,1920,3),250,dtype=np.uint8),(0,0,1920,1080),(1920,1080))
    with pytest.raises(ValueError,match='比例'):
        measure_grid(grid(),(0,0,1920,1080),(1000,1000))
    with pytest.raises(ValueError,match='不一致'):
        measure_grid(grid(40,60),(0,0,1920,1080),(1920,1080))


def test_reject_partial_and_irregular_grid():
    with pytest.raises(ValueError):
        measure_grid(grid(),(0,0,60,60),(1920,1080))
    image = grid()
    image[:,400:404] = 158
    with pytest.raises(ValueError):
        measure_grid(image,(0,0,1920,1080),(1920,1080))


def test_arrow_gate_repeats_accelerates_and_consumes_release_after_focus_loss():
    gate = ArrowGate()
    assert gate.event(0x100,0x27,False)==(False,None)
    assert gate.event(0x100,0x27,True)==(True,(1,0))
    assert gate.event(0x100,0x27,True,True)==(True,(10,0))
    assert gate.event(0x100,0x27,False)==(True,None)
    assert gate.event(0x101,0x27,False)==(True,None)
    assert gate.event(0x101,0x27,False)==(False,None)
    assert gate.event(0x100,0x26,True)==(True,(0,-1))
    assert gate.event(0x100,0x41,True)==(False,None)


def test_hidden_paste_measure_apply_dialog():
    import subprocess,sys
    subprocess.run([sys.executable,'-c',
        "import sys; sys.path.insert(0,'src'); from tests.test_grid_calibration import check_dialog; check_dialog()"],check=True)


def check_dialog():
    import tkinter as tk
    from unittest.mock import patch
    from heartopia_overlay.grid_calibration_dialog import GridCalibrationDialog
    from heartopia_overlay.win.dpi import ensure_dpi_aware
    ensure_dpi_aware()
    root = tk.Tk()
    root.withdraw()
    results = []
    dialog = GridCalibrationDialog(root,(1920,1080),results.append)
    dialog.window.withdraw()
    try:
        with patch('heartopia_overlay.grid_calibration_dialog.ImageGrab.grabclipboard',return_value=Image.fromarray(grid())):
            dialog.paste()
        dialog.measure()
        assert dialog.result is not None
        assert not results
        dialog.accept()
        assert results[0].pitch==40
    finally:
        root.destroy()
