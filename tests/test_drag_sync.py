from heartopia_overlay.drag_sync import RightDragSync


BOUNDS = (100,100,500,500)
CONTEXT = (123,0,0,1920,1080)


def test_one_to_one_movement_including_release_and_next_drag():
    sync = RightDragSync()
    assert sync.sample(True,True,(200,200),BOUNDS,CONTEXT)==(0,0)
    assert sync.sample(True,True,(220,185),BOUNDS,CONTEXT)==(20,-15)
    assert sync.sample(True,False,(225,180),BOUNDS,CONTEXT)==(5,-5)
    assert sync.sample(True,False,(250,250),BOUNDS,CONTEXT)==(0,0)
    assert sync.sample(True,True,(300,300),BOUNDS,CONTEXT)==(0,0)
    assert sync.sample(True,True,(290,320),BOUNDS,CONTEXT)==(-10,20)


def test_drag_must_start_inside_and_cannot_resume_after_leaving():
    sync = RightDragSync()
    assert sync.sample(True,True,(50,200),BOUNDS,CONTEXT)==(0,0)
    assert sync.sample(True,True,(200,200),BOUNDS,CONTEXT)==(0,0)
    sync.sample(True,False,(200,200),BOUNDS,CONTEXT)
    sync.sample(True,True,(200,200),BOUNDS,CONTEXT)
    assert sync.sample(True,True,(600,200),BOUNDS,CONTEXT)==(0,0)
    assert sync.sample(True,True,(250,200),BOUNDS,CONTEXT)==(0,0)


def test_focus_or_mode_loss_cancels_until_fresh_press():
    sync = RightDragSync()
    sync.sample(True,True,(200,200),BOUNDS,CONTEXT)
    assert sync.sample(False,True,(220,220),BOUNDS,CONTEXT)==(0,0)
    assert sync.sample(True,True,(240,240),BOUNDS,CONTEXT)==(0,0)
    sync.sample(True,False,(240,240),BOUNDS,CONTEXT)
    sync.sample(True,True,(250,250),BOUNDS,CONTEXT)
    assert sync.sample(True,True,(260,260),BOUNDS,CONTEXT)==(10,10)


def test_window_movement_and_resize_cancel_drag():
    for context in [(123,30,0,1920,1080),(123,0,0,2560,1440)]:
        sync = RightDragSync()
        sync.sample(True,True,(200,200),BOUNDS,CONTEXT)
        assert sync.sample(True,True,(220,220),BOUNDS,context)==(0,0)
        assert sync.sample(True,True,(230,230),BOUNDS,context)==(0,0)


def test_enabling_while_button_held_does_not_start_drag():
    sync = RightDragSync()
    sync.reset(held=True)
    assert sync.sample(True,True,(200,200),BOUNDS,CONTEXT)==(0,0)
    sync.sample(True,False,(200,200),BOUNDS,CONTEXT)
    sync.sample(True,True,(200,200),BOUNDS,CONTEXT)
    assert sync.sample(True,True,(205,203),BOUNDS,CONTEXT)==(5,3)
