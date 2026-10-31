from heartopia_overlay.assist import visible_cells
from heartopia_overlay.target import TargetGrid


def test_center_zoom_and_pan_clip_partial_cells():
    target = TargetGrid(2, 2, [[0, 1], [None, 0]])
    # 中心 (100,100)，格距20：全圖左上(80,80)。第一格部分可見。
    assert list(visible_cells(target, 0, 100, 100, 20, (90, 90, 115, 115))) == [
        (90, 90, 100, 100), (100, 100, 115, 115)]
    # 拖曳向右20：第二個同色格已完全出界。
    assert list(visible_cells(target, 0, 120, 100, 20, (90, 90, 115, 115))) == [
        (100, 90, 115, 100)]


def test_unselected_and_transparent_cells_are_not_shown():
    target = TargetGrid(2, 2, [[None, 1], [1, None]])
    assert list(visible_cells(target, 0, 10, 10, 10, (0, 0, 20, 20))) == []


def test_assist_import_does_not_load_optional_color_control_or_screen_capture():
    import subprocess
    import sys
    subprocess.run([sys.executable, '-c',
                    "import sys; sys.path.insert(0, 'src'); import heartopia_overlay.assist; "
                    "assert not any(n in sys.modules for n in "
                    "['heartopia_overlay.game_color_control', 'heartopia_overlay.win.screen'])"],
                   check=True)
