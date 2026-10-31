"""觀察玩家右鍵拖曳的狀態；只回傳疊層位移，不送出滑鼠輸入。"""
from dataclasses import dataclass


@dataclass
class RightDragSync:
    pressed: bool = False
    previous: tuple | None = None
    context: tuple | None = None

    def reset(self, held=False):
        self.pressed = held
        self.previous = None
        self.context = None

    def sample(self, active, down, point, bounds, context):
        was_down = self.pressed
        self.pressed = down
        x,y = point
        x0,y0,x1,y1 = bounds
        inside = x0 <= x < x1 and y0 <= y < y1
        if not active or not inside:
            self.previous = None
            self.context = None
            return (0,0)
        if self.previous is not None:
            if self.context != context:
                self.previous = None
                self.context = None
                return (0,0)
            dx,dy = x-self.previous[0],y-self.previous[1]
            self.previous = point if down else None
            if not down:
                self.context = None
            return (dx,dy)
        if down and not was_down:
            self.previous = point
            self.context = context
        return (0,0)
