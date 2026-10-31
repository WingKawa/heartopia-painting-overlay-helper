from heartopia_overlay.color_picker import PickGate


def test_shift_pick_swallows_both_down_and_up_even_after_shift_release():
    gate = PickGate()
    assert gate.event(0x201,True)==(True,True)
    assert gate.event(0x202,False)==(True,False)
    assert not gate.captured


def test_regular_drawing_is_never_consumed():
    gate = PickGate()
    assert gate.event(0x201,False)==(False,False)
    assert gate.event(0x202,False)==(False,False)
    assert gate.event(0x204,True)==(False,False)
def test_function_keys_record_quick_taps_once_and_do_not_activate_on_focus_switch():
    from heartopia_overlay.color_picker import FunctionKeyGate
    gate = FunctionKeyGate()
    context = (42,43)
    assert gate.event(0x100,0x74,context,42)==(context,0x74,True)
    assert gate.event(0x100,0x74,context,42) is None
    assert gate.event(0x101,0x74,None,99)==(context,0x74,False)
    assert gate.event(0x100,0x74,context,99) is None
    assert gate.event(0x100,0x74,context,42) is None
    assert gate.event(0x101,0x74,context,42) is None
    assert gate.event(0x100,0x74,context,42)==(context,0x74,True)
