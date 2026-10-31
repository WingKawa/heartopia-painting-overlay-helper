"""125 色調色盤。純資料，不碰螢幕。

色值由遊戲色盤截圖量測，取樣範圍與重建資料位於
data/palette_sources/2026-10-31。
編號規則 `N-M` 依遊戲色盤順序：
第 1 組 5 色（灰階），第 2~13 組各 10 色。
`row` / `col` 是遊戲調色盤內的格位，兩欄、由左至右、由上至下。
"""
import itertools
import json
import math
import pathlib
from dataclasses import dataclass

import numpy as np

from .paths import bundled

_DATA_DIR = bundled("data")
DATA = _DATA_DIR / "palette.json"
GROUP_SIZES = {1: 5, **{g: 10 for g in range(2, 14)}}


@dataclass(frozen=True)
class Color:
    index: int
    label: str
    group: int
    slot: int
    row: int
    col: str
    rgb: tuple
    hex: str


class Palette:
    def __init__(self, colors: list):
        self.colors = colors
        self._by_label = {c.label: c for c in colors}
        self._by_index = {c.index: c for c in colors}
        self._rgb = np.array([c.rgb for c in colors], dtype=np.float64)

    @classmethod
    def load(cls, path=DATA) -> "Palette":
        return _load_cached(pathlib.Path(path))

    def by_label(self, label: str) -> Color:
        return self._by_label[label]

    def by_index(self, index: int) -> Color:
        return self._by_index[index]

    def by_group(self, group: int) -> list:
        return [c for c in self.colors if c.group == group]

    def nearest(self, rgb) -> tuple:
        """回傳 (最近色, 最近距離, 次近距離)。

        同時回報次近距離，供呼叫端比較近似色的分類餘裕。
        """
        d = np.linalg.norm(self._rgb - np.asarray(rgb, dtype=np.float64), axis=1)
        order = np.argpartition(d, 1)[:2]
        first, second = order[np.argsort(d[order])]
        return self.colors[int(first)], float(d[first]), float(d[second])

    def min_pairwise_distance(self) -> tuple:
        """回傳 (最小距離, (色 A, 色 B))。由測試守著，遊戲改版變小會先亮紅燈。"""
        return min(
            ((math.dist(a.rgb, b.rgb), (a, b))
             for a, b in itertools.combinations(self.colors, 2)),
            key=lambda t: t[0],
        )


_cache: dict = {}


def _load_cached(path: pathlib.Path) -> Palette:
    key = str(path)
    if key not in _cache:
        raw = json.loads(path.read_text(encoding="utf-8"))
        _cache[key] = Palette([
            Color(index=r["index"], label=r["label"], group=r["group"], slot=r["slot"],
                  row=r["row"], col=r["col"], rgb=tuple(r["rgb"]), hex=r["hex"])
            for r in raw
        ])
    return _cache[key]
