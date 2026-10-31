import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]


def load_script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_export_excludes_private_inputs_and_history(tmp_path):
    module=load_script('prepare_source')
    source=tmp_path/'source'
    for name in ('README.md','run_assist.py','docs/USAGE.txt','src/heartopia_overlay/assist.py',
                 'tests/fixtures/grid.png','.github/workflows/guide-pages.yml',
                 'data/palette_sources/2026-10-31/group_01.png',
                 'data/palette_sources/2026-10-31/manifest.json',
                 'private.png','diagnostics.zip','config/state.json','logs/events.jsonl',
                 '.git/config','src/heartopia_overlay/__pycache__/assist.pyc','scripts/.env'):
        path=source/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('test',encoding='utf-8')
    manifest=module.prepare(source,tmp_path/'export')
    names={item['path'] for item in manifest}
    assert names=={'README.md','run_assist.py','docs/USAGE.txt','src/heartopia_overlay/assist.py',
                   'tests/fixtures/grid.png','.github/workflows/guide-pages.yml',
                   'data/palette_sources/2026-10-31/group_01.png',
                   'data/palette_sources/2026-10-31/manifest.json'}
    with pytest.raises(FileExistsError):
        module.prepare(source,tmp_path/'export')


def test_portable_package_uses_smoke_version_and_includes_notices(tmp_path,monkeypatch):
    module=load_script('package_assist')
    root=tmp_path/'project'
    version=root/'src/heartopia_overlay/version.py'
    version.parent.mkdir(parents=True)
    version.write_text("VERSION='0.1.1'\nAPP_ID='OverlayHelper'\nAPP_NAME_EN='Overlay Helper'\n")
    for name in ('LICENSE','THIRD_PARTY_NOTICES.md','CHANGELOG.md','docs/USAGE.txt'):
        target=root/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(name)
    source=tmp_path/'built'
    source.mkdir()
    (source/'OverlayHelper.exe').write_bytes(b'fake executable')
    notices=tmp_path/'notices'
    notices.mkdir()
    (notices/'inventory.json').write_text('[]')
    monkeypatch.setattr(module,'ROOT',root)
    def smoke(command,**kwargs):
        Path(command[-1]).write_text(json.dumps({'ok':True,'version':'0.1.1','game_input_executed':False}))
    monkeypatch.setattr(module.subprocess,'run',smoke)
    archive=module.package(source,notices,tmp_path/'output')
    with zipfile.ZipFile(archive) as package:
        names=package.namelist()
        assert any(name.endswith('/LICENSE') for name in names)
        assert any(name.endswith('/THIRD_PARTY_LICENSES/inventory.json') for name in names)
        assert any(name.endswith('/OverlayHelper.exe') for name in names)
    assert Path(str(archive)+'.sha256').is_file()
    with pytest.raises(FileExistsError):
        module.package(source,notices,tmp_path/'output')


def test_portable_package_rejects_user_settings_before_execution(tmp_path,monkeypatch):
    module=load_script('package_assist')
    from heartopia_overlay.version import APP_ID
    source=tmp_path/'built'
    (source/'config').mkdir(parents=True)
    (source/(APP_ID+'.exe')).write_bytes(b'fake executable')
    (source/'config'/'state.json').write_text('{}')
    notices=tmp_path/'notices'
    notices.mkdir()
    (notices/'inventory.json').write_text('[]')
    monkeypatch.setattr(module.subprocess,'run',lambda *args,**kw:pytest.fail('must reject before launching'))
    with pytest.raises(RuntimeError,match='Private'):
        module.package(source,notices,tmp_path/'output')
