from dataclasses import replace
import json
import numpy as np
from PIL import Image
import pytest
from heartopia_overlay.palette import Palette
from heartopia_overlay.palette_calibration import PaletteCalibration,calibrate_palette
from heartopia_overlay.game_color import observe_palette,SelectionError
from tests.test_game_color import screenshot


ROI = (3360,560,3830,1650)


@pytest.mark.parametrize('group',range(1,14))
def test_detect_actual_palette_in_each_group(group):
    image = Image.fromarray(screenshot(group))
    result,found = calibrate_palette(image,ROI,image.size,Palette.load())
    assert found==group
    assert observe_palette(np.asarray(image),Palette.load(),result).group==group
    assert result.left_x==pytest.approx(3454,abs=6)
    assert result.right_x==pytest.approx(3699,abs=6)
    assert result.dy==pytest.approx(181,abs=3)


def test_one_calibration_handles_all_groups_and_json_roundtrip():
    palette = Palette.load()
    result,_ = calibrate_palette(Image.fromarray(screenshot(2)),ROI,(3840,2160),palette)
    result = PaletteCalibration.load(json.loads(json.dumps(result.record())))
    for group in range(1,14):
        view = observe_palette(screenshot(group),palette,result)
        assert view.group==group
        for color in palette.by_group(group):
            assert view.point(color.slot)==result.point(color.slot)
        if group<13:
            assert view.neighbor(13)[0]>view.chip[0]
        if group>1:
            assert view.neighbor(1)[0]<view.chip[0]


def test_custom_layout_does_not_use_default_screen_ratios():
    palette = Palette.load()
    original = Image.fromarray(screenshot(8)).crop((3400,575,3770,1600))
    image = Image.new('RGB',(2560,1600))
    image.paste(original,(2100,400))
    result,found = calibrate_palette(image,(2050,385,2550,1500),image.size,palette)
    assert found==8
    assert observe_palette(np.asarray(image),palette,result).group==8
    assert result.left_x==pytest.approx(2154,abs=6)
    with pytest.raises(SelectionError,match='16:9'):
        observe_palette(np.asarray(image),palette)


def test_calibration_converts_screenshot_resolution_but_rejects_changed_game_resolution():
    image = Image.fromarray(screenshot(4))
    result,group = calibrate_palette(image,ROI,(2560,1440),Palette.load())
    assert group==4
    assert observe_palette(screenshot(4,(2560,1440)),Palette.load(),result).group==4
    with pytest.raises(SelectionError,match='解析度'):
        observe_palette(screenshot(4),Palette.load(),result)


def test_reject_invalid_calibration_and_obscured_palette():
    image = Image.fromarray(screenshot(2))
    result,_ = calibrate_palette(image,ROI,image.size,Palette.load())
    with pytest.raises(ValueError):
        replace(result,dy=float('nan')).validate()
    with pytest.raises(ValueError):
        PaletteCalibration.load({'width':100})
    with pytest.raises(ValueError):
        calibrate_palette(Image.new('RGB',image.size),ROI,image.size,Palette.load())
    with pytest.raises(SelectionError):
        observe_palette(np.zeros((2160,3840,3),dtype=np.uint8),Palette.load(),result)


def test_hidden_palette_dialog_pastes_measures_and_checks_manual_adjustment():
    import subprocess,sys
    subprocess.run([sys.executable,'-c',"import sys;sys.path.insert(0,'src');"
                    "from tests.test_palette_calibration import check_dialog;check_dialog()"],check=True)


def check_dialog():
    import tkinter as tk
    from unittest.mock import patch
    from heartopia_overlay.palette_calibration_dialog import PaletteCalibrationDialog
    from heartopia_overlay.win.dpi import ensure_dpi_aware
    ensure_dpi_aware()
    root = tk.Tk()
    root.withdraw()
    results = []
    dialog = PaletteCalibrationDialog(root,(3840,2160),Palette.load(),results.append)
    dialog.window.withdraw()
    try:
        with patch('heartopia_overlay.grid_calibration_dialog.ImageGrab.grabclipboard',
                   return_value=Image.fromarray(screenshot(2))):
            dialog.paste()
        dialog.measure()
        assert dialog.result is not None,dialog.text.get()
        assert dialog.group==2 and not results
        assert len(dialog.canvas.find_all())>10
        dialog.fields['left_x'].set(str(float(dialog.fields['left_x'].get())+1))
        assert dialog.result is None
        dialog.check_fields()
        assert dialog.result is not None
        dialog.accept()
        assert results[0].width==3840
    finally:
        root.destroy()
