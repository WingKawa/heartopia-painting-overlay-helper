"""拖曳期間的效能摘要；不記錄圖片、游標座標或一般輸入。"""
import time


class InteractionMetrics:
    def __init__(self,record,clock=time.perf_counter):
        self.record,self.clock = record,clock
        self.active = False
        self.previous = None
        self.reset()

    def reset(self):
        self.since = self.clock()
        self.intervals = []
        self.renders = []
        self.waits = []
        self.cells = 0
        self.backends = set()

    def sample(self,active):
        now = self.clock()
        if active and not self.active:
            self.reset()
        if active and self.active and self.previous is not None:
            self.intervals.append((now-self.previous)*1000)
        if self.active and (not active or now-self.since>=5):
            self.flush()
        self.active = bool(active)
        self.previous = now if active else None

    def render(self,elapsed_ms,cells,backend):
        if self.active:
            self.renders.append(elapsed_ms)
            self.cells = max(self.cells,cells)
            self.backends.add(backend)

    def wait(self,elapsed_ms):
        if self.active:
            self.waits.append(elapsed_ms)

    def flush(self):
        if self.intervals or self.renders or self.waits:
            data = {'visible_cells_max':self.cells,'backends':sorted(self.backends)}
            for name,values in [('poll_interval',self.intervals),('render',self.renders),('render_wait',self.waits)]:
                data[name+'_count'] = len(values)
                if values:
                    data[name+'_avg_ms'] = round(sum(values)/len(values),2)
                    data[name+'_max_ms'] = round(max(values),2)
            self.record('interaction_performance',**data)
        self.reset()
