import pytest
from heartopia_overlay.win import window
from heartopia_overlay.errors import GameWindowError


@pytest.mark.parametrize('title',['Heartopia','heartopia','心動小鎮','心动小镇','Heartopia - Steam','Heartopia (Global)'])
def test_regional_titles(title):
    assert window.game_title_matches(title)


@pytest.mark.parametrize('title',['Heartopia 手動疊圖','Heartopia Assist','Other Game','Heartopia - preview',
                                  'Heartopia 繪畫疊層小幫手 · 0.1.1','Heartopia - Painting Overlay Helper'])
def test_tool_and_other_titles_not_detected_as_game(title):
    assert not window.game_title_matches(title)


def test_multiple_games_require_foreground_instead_of_first_random_window(monkeypatch):
    monkeypatch.setattr(window,'ensure_dpi_aware',lambda:None)
    monkeypatch.setattr(window.win32gui,'EnumWindows',lambda cb,arg:[cb(hwnd,arg) for hwnd in (1,2)])
    monkeypatch.setattr(window.win32gui,'IsWindowVisible',lambda hwnd:True)
    monkeypatch.setattr(window.win32gui,'GetWindowText',lambda hwnd:'Heartopia')
    monkeypatch.setattr(window.win32gui,'GetForegroundWindow',lambda:2)
    assert window.find_game_hwnd()==2
    monkeypatch.setattr(window.win32gui,'GetForegroundWindow',lambda:99)
    with pytest.raises(GameWindowError,match='多個'):
        window.find_game_hwnd()
