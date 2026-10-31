import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from PIL import Image
import pytest

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'data/palette_sources/2026-10-31'


def module():
    spec=importlib.util.spec_from_file_location('measure_palette',ROOT/'scripts/measure_palette.py')
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_original_screenshots_reproduce_all_deployed_colors_and_audit_report():
    palette,report=module().measure(SOURCES/'manifest.json')
    assert palette==json.loads((ROOT/'data/palette.json').read_text(encoding='utf-8'))
    assert report==json.loads((SOURCES/'measurement.json').read_text(encoding='utf-8'))
    assert len(palette)==125
    assert all(sample['pixels']==441 and sample['min_rgb']==sample['max_rgb'] for sample in report['samples'])


def test_modified_original_is_rejected_before_sampling(tmp_path):
    folder=tmp_path/'sources'
    shutil.copytree(SOURCES,folder)
    with (folder/'group_01.png').open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError,match='checksum'):
        module().measure(folder/'manifest.json')


def test_nonuniform_patch_is_rejected_even_if_hash_is_updated(tmp_path):
    folder=tmp_path/'sources'
    shutil.copytree(SOURCES,folder)
    manifest_path=folder/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    frame=manifest['frames'][0]
    path=folder/frame['file']
    x,y,*_=frame['regions'][0]['box']
    with Image.open(path) as source:
        image=source.copy()
    image.putpixel((x,y),(255,0,255,255))
    image.save(path)
    frame['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='Non-uniform'):
        module().measure(manifest_path)


def test_missing_group_cannot_silently_produce_partial_palette(tmp_path):
    manifest=json.loads((SOURCES/'manifest.json').read_text())
    manifest['frames'].pop()
    path=tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='Exactly one screenshot'):
        module().measure(path)
