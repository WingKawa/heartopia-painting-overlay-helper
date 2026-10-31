from heartopia_overlay.right_drag_events import RightDragEvents

CONTEXT = (42,(100,100,1000,1000),43,(0,0,1200,1200),99)


def test_fast_complete_drag_preserves_press_release_and_excludes_later_motion():
    events=RightDragEvents()
    events.configure(CONTEXT)
    for message,point,stamp in [(0x204,(200,200),100),(0x200,(400,250),110),
                                 (0x205,(500,300),120),(0x200,(800,900),130)]:
        events.event(message,point,stamp,True,CONTEXT)
    updates,overflow=events.drain()
    assert not overflow and len(updates)==1
    update=updates[0]
    assert update['started'] and update['ended'] and update['reason']=='released'
    assert update['delta']==update['total']==(300,100)
    assert update['event_duration_ms']==20
    assert events.drain()==([],0)


def test_drains_apply_only_new_motion_and_keep_multiple_click_boundaries():
    events=RightDragEvents()
    events.configure(CONTEXT)
    events.event(0x204,(200,200),0,True,CONTEXT)
    events.event(0x200,(210,220),1,True,CONTEXT)
    first=events.drain()[0][0]
    assert first['delta']==(10,20) and first['started'] and not first['ended']
    events.event(0x205,(220,240),2,True,CONTEXT)
    events.event(0x204,(300,300),3,True,CONTEXT)
    events.event(0x205,(310,320),4,True,CONTEXT)
    updates,_=events.drain()
    assert [u['delta'] for u in updates]==[(10,20),(10,20)]
    assert [u['started'] for u in updates]==[False,True]


def test_leaving_bounds_or_losing_focus_cancels_until_fresh_press():
    for eligible,point,reason in [(True,(1100,200),'left_bounds'),(False,(230,200),'focus_or_context_lost')]:
        events=RightDragEvents();events.configure(CONTEXT)
        events.event(0x204,(200,200),0,True,CONTEXT)
        events.event(0x200,(220,200),1,True,CONTEXT)
        events.event(0x200,point,2,eligible,CONTEXT)
        events.event(0x200,(250,200),3,True,CONTEXT)
        events.event(0x205,(270,200),4,True,CONTEXT)
        update=events.drain()[0][0]
        assert update['total']==(20,0) and update['reason']==reason
        events.event(0x204,(300,200),5,True,CONTEXT)
        events.event(0x205,(310,200),6,True,CONTEXT)
        assert events.drain()[0][0]['total']==(10,0)


def test_enable_while_held_and_context_changes_do_not_start_or_resume_drag():
    events=RightDragEvents()
    events.event(0x204,(200,200),0,False,None)
    events.configure(CONTEXT)
    events.event(0x200,(220,200),1,True,CONTEXT)
    events.event(0x205,(230,200),2,True,CONTEXT)
    assert events.drain()==([],0)
    events.event(0x204,(200,200),3,True,CONTEXT)
    events.cancel()
    events.configure(CONTEXT)
    events.event(0x200,(500,200),4,True,CONTEXT)
    events.event(0x205,(600,200),5,True,CONTEXT)
    update=events.drain()[0][0]
    assert update['reason']=='context_changed' and update['total']==(0,0)


def test_high_frequency_motion_is_coalesced_and_timestamp_wrap_is_safe():
    events=RightDragEvents();events.configure(CONTEXT)
    events.event(0x204,(200,200),0xfffffffe,True,CONTEXT)
    for i in range(10000):
        events.event(0x200,(200+i%700,200),i&0xffffffff,True,CONTEXT)
    assert not events.completed
    events.event(0x205,(300,200),10000,True,CONTEXT)
    updates,_=events.drain()
    assert len(updates)==1 and updates[0]['total']==(100,0)
    assert updates[0]['events']==10001 and updates[0]['event_duration_ms']==10002
