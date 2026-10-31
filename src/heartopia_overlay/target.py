"""目標圖讀取與把關。純資料，不碰螢幕。

把關原則：能百分之百還原原意的就自動處理，需要猜測的就拒絕。

等倍降採樣是無損的。**小幅色彩吸附也不是猜測**：125 色兩兩最小距離
5.00，容許值 2.0 時 2*2.0 = 4.0 < 5.00，所以落在某合法色 2.0 以內的
顏色數學上不可能同時落在另一個合法色的 2.0 以內——吸附結果唯一且可證明。
超出容許值就拒絕。

小幅色彩吸附用於處理圖片匯出或編碼產生的通道微差。

TRANSPARENT 代表「不畫」，與「畫白色 1-5」是兩種不同結果，
因為遊戲的空白格帶有斜紋材質。
"""
import pathlib
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .errors import TargetError
from .palette import Palette

TRANSPARENT = None

# 見模組說明。這個值與 palette 的最小色距綁定，
# 由 tests/test_target.py::test_snap_tolerance_guarantees_a_unique_match 守著。
SNAP_TOLERANCE = 2.0

VALID_SIZES = frozenset({
    (30, 18), (50, 28), (100, 56), (150, 84),      # 16:9
    (30, 24), (50, 38), (100, 76), (150, 114),     # 4:3
    (30, 30), (50, 50), (100, 100), (150, 150),    # 1:1
    (24, 30), (38, 50), (76, 100), (114, 150),     # 3:4
    (18, 30), (28, 50), (56, 100), (84, 150),      # 9:16
})

# 支援原始像素與 30 倍放大格式；介面使用 unrestricted 保留任意尺寸。
UPSCALES = (1, 30)


@dataclass(frozen=True)
class TargetGrid:
    w: int
    h: int
    cells: list           # list[list[int | None]]，值為 palette index 或 TRANSPARENT
    snapped: int = 0      # 經過色彩吸附的像素數，供日誌與異常偵測用


def _resolve_scale(iw: int, ih: int) -> tuple:
    for scale in UPSCALES:
        if iw % scale or ih % scale:
            continue
        w, h = iw // scale, ih // scale
        if (w, h) in VALID_SIZES:
            return w, h, scale
    nearest = min(VALID_SIZES, key=lambda s: abs(s[0] - iw) + abs(s[1] - ih))
    raise TargetError(
        f"圖片尺寸 {iw}x{ih} 不是合法的畫布尺寸。"
        f"最接近的合法尺寸是 {nearest[0]}x{nearest[1]}。"
        f"請使用原始像素尺寸的圖片。"
    )


def load_target(path, *, unrestricted=False) -> TargetGrid:
    """unrestricted 模式保留原始像素尺寸，一個像素就是一格。"""
    # convert("RGBA") 不套用 ICC 轉換，確保檔案中的 RGB 位元原封不動進入比對
    arr = np.asarray(Image.open(pathlib.Path(path)).convert("RGBA"))
    ih, iw = arr.shape[:2]
    w, h, scale = (iw, ih, 1) if unrestricted else _resolve_scale(iw, ih)

    if scale == 1:
        sampled = arr
    else:
        off = scale // 2                       # 取每個色塊的中心，避開格線
        sampled = arr[off::scale, off::scale][:h, :w]

    pal = Palette.load()
    rgb = sampled[:, :, :3].astype(np.int16)
    opaque = sampled[:, :, 3] >= 128

    # 任意尺寸不能建立整張圖 × 125 色 × RGB 的巨大暫存陣列。
    # 只匹配實際出現的不透明顏色，並分批限制暫存記憶體用量。
    ref = np.array([c.rgb for c in pal.colors], dtype=np.float32)
    idx = np.zeros((h,w), dtype=np.int16)
    dist = np.zeros((h,w), dtype=np.float32)
    colors, inverse = np.unique(rgb[opaque], axis=0, return_inverse=True)
    matched = np.empty(len(colors), dtype=np.int16)
    distances = np.empty(len(colors), dtype=np.float32)
    for start in range(0,len(colors),4096):
        batch = colors[start:start+4096].astype(np.float32)
        d = np.linalg.norm(batch[:,None,:] - ref[None,:,:],axis=2)
        nearest = d.argmin(axis=1)
        matched[start:start+len(batch)] = nearest
        distances[start:start+len(batch)] = d[np.arange(len(batch)),nearest]
        if unrestricted:
            bad = np.flatnonzero(distances[start:start+len(batch)]>SNAP_TOLERANCE)
            if len(bad):
                color = colors[start+int(bad[0])]
                y,x = np.argwhere(opaque & (rgb==color).all(axis=2))[0]
                raise TargetError(f'圖中有像素不在遊戲的 125 色內，例如：({int(x)}, {int(y)}) '
                                  f'RGB({int(color[0])}, {int(color[1])}, {int(color[2])})')
    idx[opaque] = matched[inverse]
    dist[opaque] = distances[inverse]

    illegal = opaque & (dist > SNAP_TOLERANCE)
    if illegal.any():
        ys, xs = np.nonzero(illegal)
        head = "、".join(
            f"({int(x)}, {int(y)}) RGB({rgb[y, x, 0]}, {rgb[y, x, 1]}, {rgb[y, x, 2]})"
            for x, y in list(zip(xs, ys))[:5]
        )
        hint = ""
        if scale != 1:
            hint = (f"。這張圖是 {scale} 倍放大版，可能是「帶網格參考圖」或"
                    f"「標號網格參考圖」，請改用「下載當前尺寸 (1:1 像素)」")
        raise TargetError(
            f"圖中有 {int(illegal.sum())} 個像素不在遊戲的 125 色內，例如：{head}{hint}"
        )

    snapped = int((opaque & (dist > 0)).sum())
    cells = [
        [int(idx[y, x]) if opaque[y, x] else TRANSPARENT for x in range(w)]
        for y in range(h)
    ]
    return TargetGrid(w=w, h=h, cells=cells, snapped=snapped)
