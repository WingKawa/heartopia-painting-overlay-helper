from heartopia_overlay.interaction_metrics import InteractionMetrics


def test_drag_metrics_are_aggregated_and_idle_is_excluded():
    now = [0.0]
    events = []
    metrics = InteractionMetrics(lambda name,**data:events.append((name,data)),lambda:now[0])
    metrics.sample(False)
    now[0] = 100
    metrics.sample(True)
    metrics.render(12,800,'raster')
    metrics.wait(19)
    now[0] += .02
    metrics.sample(True)
    now[0] += .1
    metrics.sample(False)
    assert len(events)==1
    name,data = events[0]
    assert name=='interaction_performance'
    assert data['poll_interval_count']==1 and data['poll_interval_max_ms']==20
    assert data['render_avg_ms']==12 and data['render_wait_max_ms']==19
    assert data['visible_cells_max']==800 and data['backends']==['raster']
    metrics.render(999,999,'canvas')
    metrics.flush()
    assert len(events)==1


def test_long_drag_flushes_every_five_seconds_without_resetting_gesture():
    now=[0.0]
    events=[]
    metrics=InteractionMetrics(lambda *args,**kwargs:events.append(kwargs),lambda:now[0])
    metrics.sample(True)
    for i in range(1,13):
        now[0]=float(i)
        metrics.sample(True)
    assert len(events)==2 and metrics.active
    metrics.sample(False)
    assert len(events)==3
