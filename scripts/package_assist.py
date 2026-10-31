"""Package a built portable release, including notices and a startup smoke check."""
from pathlib import Path
import argparse
import hashlib
import json
import runpy
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def package(source,notices,output):
    product=runpy.run_path(str(ROOT/'src'/'heartopia_overlay'/'version.py'))
    version,app_id=product['VERSION'],product['APP_ID']
    name=f'{app_id}-{version}-windows-x64'
    source,notices,output=Path(source),Path(notices),Path(output)
    stage,archive=output/name,output/(name+'.zip')
    if stage.exists() or archive.exists():
        raise FileExistsError(f'Existing output will not be overwritten: {stage}')
    executable=source/(app_id+'.exe')
    if not executable.is_file() or not (notices/'inventory.json').is_file():
        raise RuntimeError('Build the executable and collect third-party notices first.')
    for path in source.rglob('*'):
        if any(part.casefold() in ('config','logs','.git','venv','__pycache__') for part in path.relative_to(source).parts):
            raise RuntimeError(f'Private or development files in build: {path}')
    report_dir=ROOT/'build'/'release-checks'
    report_dir.mkdir(parents=True,exist_ok=True)
    report=report_dir/(name+'-smoke.json')
    # A fresh report is required even if a previous check succeeded.
    if report.exists():
        raise FileExistsError(f'Previous smoke report exists; review it before rerunning: {report}')
    subprocess.run([str(executable.resolve()),'--smoke-test',str(report.resolve())],check=True,timeout=180)
    result=json.loads(report.read_text(encoding='utf-8'))
    if not result.get('ok') or result.get('version')!=version or result.get('game_input_executed') is not False:
        raise RuntimeError('Built executable failed the version/startup/no-game-input check.')
    output.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source,stage)
    shutil.copytree(notices,stage/'THIRD_PARTY_LICENSES')
    for source_name,target_name in [('LICENSE','LICENSE'),('THIRD_PARTY_NOTICES.md','THIRD_PARTY_NOTICES.md'),
                                    ('docs/USAGE.txt','使用說明.txt'),('CHANGELOG.md','CHANGELOG.md')]:
        shutil.copyfile(ROOT/source_name,stage/target_name)
    (stage/'VERSION.txt').write_text(f"{product['APP_NAME_EN']}\n{version}\nWindows x64 portable\n",encoding='utf-8')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as package:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                package.write(path,path.relative_to(stage.parent).as_posix())
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise RuntimeError('ZIP integrity check failed.')
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/(archive.name+'.sha256')).write_text(f'{digest}  {archive.name}\n',encoding='ascii')
    print(f'Local package: {archive}\nSHA256: {digest}\nBuild and release instructions: docs/BUILDING.md')
    return archive


if __name__=='__main__':
    product=runpy.run_path(str(ROOT/'src'/'heartopia_overlay'/'version.py'))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'build'/'release-dist'/product['APP_ID'])
    parser.add_argument('--notices',type=Path,default=ROOT/'build'/'release-notices')
    parser.add_argument('--output',type=Path,default=ROOT/'dist')
    args=parser.parse_args()
    package(args.source,args.notices,args.output)
