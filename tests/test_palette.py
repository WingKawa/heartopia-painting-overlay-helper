import pytest

from heartopia_overlay.palette import GROUP_SIZES, Palette


@pytest.fixture(scope="module")
def pal():
    return Palette.load()


def test_has_125_colors(pal):
    assert len(pal.colors) == 125


def test_index_is_contiguous(pal):
    assert [c.index for c in pal.colors] == list(range(125))


def test_group_sizes(pal):
    assert GROUP_SIZES == {1: 5, **{g: 10 for g in range(2, 14)}}
    for group, size in GROUP_SIZES.items():
        assert len(pal.by_group(group)) == size


def test_label_matches_group_and_slot(pal):
    for c in pal.colors:
        assert c.label == f"{c.group}-{c.slot}"
        assert c.row == (c.slot + 1) // 2
        assert c.col == ("L" if c.slot % 2 else "R")


def test_lookup_roundtrip(pal):
    for c in pal.colors:
        assert pal.by_label(c.label) is c
        assert pal.by_index(c.index) is c


def test_minimum_pairwise_distance_is_5(pal):
    """量測色盤的最小色距為 5.0（2-10 vs 3-10）。

    這個值決定圖片讀取時色彩吸附的唯一性。若未來重新量測導致它變小，
    應先檢查容許值，避免相近的兩色產生歧義。
    """
    lo, pair = pal.min_pairwise_distance()
    assert round(lo, 2) == 5.00
    assert {p.label for p in pair} == {"2-10", "3-10"}


def test_nearest_exact_match(pal):
    c = pal.by_label("7-3")
    got, dist, runner_up = pal.nearest(c.rgb)
    assert got is c
    assert dist == 0.0
    assert runner_up > 0


def test_nearest_reports_runner_up(pal):
    """近似色同時回報次近距離，供呼叫端比較分類餘裕。"""
    c = pal.by_label("2-10")
    _, dist, runner_up = pal.nearest(c.rgb)
    assert dist == 0.0
    assert round(runner_up, 2) == 5.00
