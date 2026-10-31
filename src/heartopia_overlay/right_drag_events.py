"""滑鼠 hook 執行緒累計右鍵拖曳；介面只領取位移摘要，不轉送輸入。"""
from collections import deque
import threading
import time
from .drag_sync import RightDragSync


class RightDragEvents:
    def __init__(self,clock=time.perf_counter):
        self.clock = clock
        self.lock = threading.RLock()
        self.context = None
        self.held = False
        self.sync = RightDragSync()
        self.current = None
        self.completed = deque()
        self.overflow = 0

    def configure(self,context):
        with self.lock:
            if context != self.context:
                self.end('context_changed')
                self.context = context
                self.sync.reset(self.held)

    def cancel(self):
        self.configure(None)

    def end(self,reason):
        if self.current is not None:
            if self.current['started'] and self.current['total']==self.current['delivered']:
                self.current['queued'] = self.clock()
            self.current['ended'] = True
            self.current['reason'] = reason
            self.completed.append(self.current)
            self.current = None
            if len(self.completed)>128:
                self.overflow += len(self.completed)
                self.completed.clear()
        self.sync.reset(self.held)

    def event(self,message,point,stamp,eligible,context):
        """stamp 是 Windows 事件時間；即使 GUI 正忙，也保留正確的按放邊界。"""
        if message not in (0x200,0x204,0x205):
            return
        with self.lock:
            if message==0x204:
                if self.held:
                    return
                self.held = True
                self.sync.reset(False)
                if context is None or context != self.context or not eligible:
                    self.sync.reset(True)
                    return
                bounds = context[1]
                self.sync.sample(True,True,point,bounds,context)
                if self.sync.previous is None:
                    return
                self.current = dict(context=context,total=[0,0],delivered=[0,0],events=0,
                                    max_gap_ms=0,start=stamp,last=stamp,queued=self.clock(),
                                    started=False,ended=False,reason=None)
            elif self.current is not None:
                if not eligible or context != self.context:
                    self.end('focus_or_context_lost')
                else:
                    bounds = self.current['context'][1]
                    if self.current['started'] and self.current['total']==self.current['delivered']:
                        self.current['queued'] = self.clock()
                    dx,dy = self.sync.sample(True,message!=0x205,point,bounds,self.current['context'])
                    state = self.current
                    state['total'][0] += dx
                    state['total'][1] += dy
                    state['max_gap_ms'] = max(state['max_gap_ms'],(stamp-state['last'])&0xffffffff)
                    state['last'] = stamp
                    state['events'] += 1
                    if self.sync.previous is None:
                        self.end('released' if message==0x205 else 'left_bounds')
            if message==0x205:
                self.held = False
                self.end('released')
                self.sync.reset(False)

    def drain(self):
        with self.lock:
            states = list(self.completed)
            self.completed.clear()
            if self.current is not None:
                states.append(self.current)
            updates = []
            for state in states:
                total = state['total']
                delta = tuple(total[i]-state['delivered'][i] for i in (0,1))
                if delta!=(0,0) or not state['started'] or state['ended']:
                    updates.append(dict(context=state['context'],delta=delta,
                                        started=not state['started'],ended=state['ended'],
                                        reason=state['reason'],total=tuple(total),events=state['events'],
                                        event_gap_max_ms=state['max_gap_ms'],
                                        event_duration_ms=(state['last']-state['start'])&0xffffffff,
                                        queue_age_ms=round((self.clock()-state['queued'])*1000,2)))
                    state['started'] = True
                    state['delivered'] = list(total)
                    state['queued'] = self.clock()
            overflow,self.overflow = self.overflow,0
            return updates,overflow
