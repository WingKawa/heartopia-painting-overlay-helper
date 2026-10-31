"""色盤辨識使用的實際遊戲截圖。"""
import pathlib
import numpy as np
import pytest
from PIL import Image


@pytest.fixture(scope="session")
def panel_group2():
    """展開第 2 組的右側色盤；由完整截圖裁切 (3100, 300)。"""
    path = pathlib.Path(__file__).parent / "fixtures" / "panel_group2.webp"
    return np.asarray(Image.open(path).convert("RGB"))
