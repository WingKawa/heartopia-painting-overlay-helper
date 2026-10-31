import json
import pytest
from heartopia_overlay.session import SessionStore,pack_grid,unpack_grid
from heartopia_overlay.target import TargetGrid


@pytest.mark.parametrize('key,value',[
    ('auto_color_enabled',1),('auto_color_enabled','true'),
    ('auto_color_notice_version',True),('auto_color_notice_version',-1),
    ('auto_color_notice_version','1'),
])
def test_rejects_invalid_auto_color_consent_state(key,value):
    from heartopia_overlay.session import validate
    state=sample()
    state[key]=value
    with pytest.raises(ValueError):
        validate(state)


def sample():
    return {'version':1,'source':pack_grid(TargetGrid(3,2,[[0,124,None],[3,None,5]])),
            'image_path':'D:/pictures/cropped.jpg','canvas_width':12,'canvas_height':9,
            'offset_x':-3,'offset_y':4,'canvas_custom':True,'left':-1244.5,'top':300,
            'gap':16,'cell_size':147.25,'clip':[745,501,3014,1817],
            'sync_drag':True,'enabled':True,'aligning':False,'selected_color':84,
            'map_mode':'擺放圖片','opacity':.55,'ui_scale':'150%'}


def test_atomic_save_and_restore_source_without_original_file(tmp_path):
    store = SessionStore(tmp_path/'config'/'state.json')
    state = sample()
    store.save(state)
    loaded,grid = store.load()
    assert loaded==state
    assert grid.cells==[[0,124,None],[3,None,5]]
    assert not list(store.path.parent.glob('*.tmp'))


def test_invalid_new_state_does_not_overwrite_saved_session(tmp_path):
    store = SessionStore(tmp_path/'state.json')
    store.save(sample())
    old = store.path.read_bytes()
    state = sample()
    state['cell_size']=float('nan')
    with pytest.raises(ValueError):
        store.save(state)
    assert store.path.read_bytes()==old


def test_corrupt_and_unknown_session_report_errors(tmp_path):
    store = SessionStore(tmp_path/'state.json')
    assert store.load() is None
    store.path.write_text('{ broken',encoding='utf-8')
    with pytest.raises(ValueError):
        store.load()
    state = sample()
    state['version']=99
    store.path.write_text(json.dumps(state),encoding='utf-8')
    with pytest.raises(ValueError):
        store.load()


def test_truncated_or_invalid_color_snapshot_rejected():
    state = sample()['source']
    state['width']=10
    with pytest.raises(ValueError):
        unpack_grid(state)


def test_rejects_bad_saved_offset_and_color(tmp_path):
    store = SessionStore(tmp_path/'state.json')
    for key,value in [('offset_x','bad'),('selected_color',125),('canvas_width',0),('left',float('inf'))]:
        state = sample()
        state[key]=value
        with pytest.raises(ValueError):
            store.save(state)
