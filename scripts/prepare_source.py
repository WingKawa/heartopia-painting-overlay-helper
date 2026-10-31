"""Export an explicit source allowlist, never the whole working directory or Git history."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES=('README.md','LICENSE','THIRD_PARTY_NOTICES.md','CHANGELOG.md',
            'docs/DEVELOPMENT.md','docs/BUILDING.md',
            '.gitignore','requirements.txt','requirements-dev.txt','requirements-build.txt',
            'pytest.ini','run_assist.py','Start-Assist.bat','Start-Assist.vbs','assist.spec')
TREES=(('src',('.py',)),('tests',('.py','.json','.png','.webp')),
       ('data/palette_sources',('.png','.json','.md')),
       ('scripts',('.py',)),('docs/guide',('.html','.png')),
       ('docs/licenses',('.md','.terms')),('docs/release',('.md',)),
       ('.github',('.yml','.md')))


def source_files(root):
    root=Path(root)
    candidates=[root/name for name in ROOT_FILES]
    candidates += [root/'data'/'palette.json',root/'docs'/'USAGE.txt']
    for directory,suffixes in TREES:
        candidates.extend(path for path in (root/directory).rglob('*') if path.suffix.lower() in suffixes)
    return sorted({path for path in candidates if path.is_file() and not path.is_symlink()
                   and not any(part.startswith('.') or part=='__pycache__' for part in path.relative_to(root).parts
                               if part not in ('.github','.gitignore'))},key=lambda path:path.relative_to(root).as_posix())


def prepare(root,output):
    root,output=Path(root),Path(output)
    if output.exists():
        raise FileExistsError(f'Existing output will not be overwritten: {output}')
    files=source_files(root)
    output.mkdir(parents=True)
    manifest=[]
    for source in files:
        relative=source.relative_to(root)
        target=output/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'Copy mismatch: {relative}')
        manifest.append({'path':relative.as_posix(),'sha256':digest})
    (output/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Prepared {len(files)} source files in {output}; review rights and README links before publishing.')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    prepare(ROOT,args.output)
