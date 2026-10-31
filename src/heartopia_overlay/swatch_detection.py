"""色盤校正使用的實心色塊定位，不執行任何遊戲輸入。"""
import numpy as np

MATCH_TOL = 3.0
WINDOW = 90
MIN_FILL = 0.9


def _box_sums(mask: np.ndarray, k: int) -> np.ndarray:
    ii = np.pad(mask.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k]


def find_swatch(img: np.ndarray, rgb, k: int = WINDOW):
    """回傳最密集 k×k 色塊的 (中心, 填充率)，找不到時回傳 (None, 0)。"""
    d = np.linalg.norm(img.astype(np.int16) - np.array(rgb, dtype=np.int16), axis=2)
    mask = d < MATCH_TOL
    if mask.sum() < k * k * MIN_FILL:
        return None, 0.0
    sums = _box_sums(mask, k)
    r, c = divmod(int(sums.argmax()), sums.shape[1])
    return (c + k / 2, r + k / 2), float(sums[r, c] / (k * k))
