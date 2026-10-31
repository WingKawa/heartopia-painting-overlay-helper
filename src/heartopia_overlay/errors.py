"""本專案的例外型別。

錯誤訊息是使用者介面的一部分：每一則都必須具體到使用者能自行修正，
不要只說「失敗」。
"""


class OverlayError(Exception):
    """所有本專案例外的基底。"""


class TargetError(OverlayError):
    """目標圖不合法：尺寸、顏色、或格式。"""


class GameWindowError(OverlayError):
    """找不到遊戲視窗，或視窗狀態不允許操作。"""
