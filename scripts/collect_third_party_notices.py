"""Collect installed license texts verbatim; no dependency downloads or upload."""
from importlib import metadata
from pathlib import Path
import argparse
import json
import platform
import shutil
import sys

PACKAGES = ('Pillow','numpy','mss','pywin32','PyInstaller','pyinstaller-hooks-contrib')


def license_files(distribution):
    for entry in distribution.files or ():
        basename = Path(str(entry)).name.lower()
        if basename.startswith(('license','licence','copying','notice','authors')) and not basename.endswith(('.py','.pyc','.pyd')):
            path = Path(distribution.locate_file(entry))
            if path.is_file():
                yield entry,path


def collect(output):
    output=Path(output)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    # Verify required sources before creating an output tree.
    distributions=[metadata.distribution(name) for name in PACKAGES]
    sources=[list(license_files(distribution)) for distribution in distributions]
    if any(not files for files in sources):
        raise RuntimeError('A dependency has no installed license text; review before packaging.')
    python_license=Path(sys.base_prefix)/'LICENSE.txt'
    tk_license=Path(sys.base_prefix)/'tcl'/'tk8.6'/'license.terms'
    import tkinter
    tcl_version=tkinter.Tcl().eval('info patchlevel')
    tcl_license=Path(__file__).resolve().parents[1]/'docs'/'licenses'/f'Tcl-{tcl_version}-license.terms'
    if not python_license.is_file() or not tk_license.is_file():
        raise RuntimeError('Python/Tk license sources missing; review this Python distribution.')
    if not tcl_license.is_file():
        raise RuntimeError(f'Collect matching Tcl license before packaging: {tcl_version}')
    output.mkdir(parents=True)
    inventory=[]
    for distribution,files in zip(distributions,sources):
        name=distribution.metadata['Name']
        copied=[]
        for entry,source in files:
            # Numbered names avoid path traversal and duplicate basenames in wheels.
            relative=Path(name)/f'{len(copied)+1:02d}-{source.name}'
            target=output/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
            copied.append({'wheel_path':str(entry).replace('\\','/'),'text':relative.as_posix()})
        inventory.append({'name':name,'version':distribution.version,'licenses':copied})
    shutil.copyfile(python_license,output/'Python-LICENSE.txt')
    shutil.copyfile(tk_license,output/'Tk-license.terms')
    shutil.copyfile(tcl_license,output/'Tcl-license.terms')
    inventory.append({'name':'Python','version':platform.python_version(),'licenses':[{'text':'Python-LICENSE.txt'}]})
    inventory.append({'name':'Tcl','version':tcl_version,'licenses':[{'text':'Tcl-license.terms'}]})
    (output/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'README.txt').write_text(
        'Third-party license texts collected from the build environment.\n'
        'Python-LICENSE.txt includes Python and bundled component notices; Tcl/Tk license.terms files contain Tcl/Tk terms.\n'
        'Pillow and NumPy license files include their bundled native library terms.\n'
        'PyInstaller includes its bootloader exception; build-time hooks and runtime hooks have distinct terms.\n'
        'This product includes software developed by the OpenSSL Project for use in the OpenSSL Toolkit. (http://www.openssl.org/)\n'
        'This inventory is not an assertion that every listed subcomponent is loaded at runtime.\n',encoding='utf-8')
    return inventory


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    items=collect(args.output)
    print(f'Collected notices for {len(items)} components into {args.output}')
