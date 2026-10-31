import json
import zipfile
import pytest
from pathlib import Path
from heartopia_overlay.diagnostic_log import DiagnosticLog


def test_repeated_states_are_not_flooded_and_private_home_is_redacted(tmp_path):
    log = DiagnosticLog(tmp_path/'logs')
    for _ in range(100):
        log.state('connection',connected=False)
    log.state('connection',connected=True)
    log.record('error',detail=str(Path.home()/'some-file'))
    lines = [json.loads(line) for line in log.events]
    assert len([line for line in lines if line['event']=='connection'])==2
    assert lines[-1]['detail'].startswith('<USER>')
    log.close()


def test_export_cannot_overwrite_active_log(tmp_path):
    log = DiagnosticLog(tmp_path/'logs')
    original = (tmp_path/'logs'/'assist.jsonl').read_bytes()
    with pytest.raises(ValueError):
        log.export(tmp_path/'logs'/'assist.jsonl','snapshot')
    assert (tmp_path/'logs'/'assist.jsonl').read_bytes()==original
    log.close()


def test_rotation_export_contains_only_known_logs_and_snapshot(tmp_path):
    directory = tmp_path/'logs'
    log = DiagnosticLog(directory,max_bytes=1024)
    for index in range(100):
        log.record('event',index=index,message='x'*90)
    assert len(list(directory.glob('assist.jsonl*')))<=3
    assert all(p.stat().st_size<=1024 for p in directory.glob('assist.jsonl*'))
    (directory/'private.png').write_bytes(b'not a log')
    output = tmp_path/'report.zip'
    log.export(output,'diagnostic snapshot')
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist())=={'README.txt','diagnostics.txt','current-session.jsonl',
                                         'logs/assist.jsonl','logs/assist.jsonl.1','logs/assist.jsonl.2'}
        assert archive.read('diagnostics.txt')==b'diagnostic snapshot'
        for line in archive.read('current-session.jsonl').decode('utf-8').splitlines():
            json.loads(line)
    log.close()


def test_memory_export_still_works_if_log_directory_cannot_be_created(tmp_path):
    blocked = tmp_path/'file'
    blocked.write_text('keep me')
    log = DiagnosticLog(blocked/'logs')
    assert log.write_error
    log.record('test_error',reason='example')
    output = tmp_path/'report.zip'
    log.export(output,'fallback')
    with zipfile.ZipFile(output) as archive:
        assert 'test_error' in archive.read('current-session.jsonl').decode('utf-8')
    assert blocked.read_text()=='keep me'
    log.close()
