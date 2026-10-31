"""Rebuild palette data solely from original PNGs and explicit sample regions."""
from pathlib import Path
import argparse
import hashlib
import json
from PIL import Image


def measure(manifest_path):
    manifest_path=Path(manifest_path)
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    frames=manifest['frames']
    if manifest.get('schema')!=1 or sorted(frame['group'] for frame in frames)!=list(range(1,14)):
        raise ValueError('Exactly one screenshot per group 1 through 13 is required.')
    palette=[]
    samples=[]
    for frame in sorted(frames,key=lambda frame:frame['group']):
        group=frame['group']
        path=(manifest_path.parent/frame['file']).resolve()
        if path.parent!=manifest_path.parent.resolve():
            raise ValueError('Screenshot must be beside the manifest.')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=frame['sha256']:
            raise ValueError(f'Screenshot checksum mismatch: {frame["file"]}')
        expected=list(range(1,6 if group==1 else 11))
        regions=frame['regions']
        if sorted(region['slot'] for region in regions)!=expected:
            raise ValueError(f'Wrong slot coverage in group {group}')
        with Image.open(path) as original:
            if original.format!='PNG' or original.mode not in ('RGB','RGBA') or list(original.size)!=frame['size']:
                raise ValueError(f'Original RGB/RGBA PNG required: {frame["file"]}')
            # No resize, quantization, palette reference, ICC transform or gamma transform.
            image=original.convert('RGBA')
            for region in sorted(regions,key=lambda region:region['slot']):
                slot=region['slot']
                x0,y0,x1,y1=region['box']
                if not (0<=x0<x1<=image.width and 0<=y0<y1<=image.height and x1-x0>=9 and y1-y0>=9):
                    raise ValueError(f'Invalid sample box: {group}-{slot}')
                patch=image.crop((x0,y0,x1,y1))
                extrema=patch.getextrema()
                if any(lo!=hi for lo,hi in extrema) or extrema[3]!=(255,255):
                    raise ValueError(f'Non-uniform or transparent patch: {group}-{slot}')
                rgb=[channel[0] for channel in extrema[:3]]
                color={'index':len(palette),'label':f'{group}-{slot}','group':group,'slot':slot,
                       'row':(slot+1)//2,'col':'L' if slot%2 else 'R','rgb':rgb,
                       'hex':'#'+''.join(f'{channel:02X}' for channel in rgb)}
                palette.append(color)
                samples.append({'label':color['label'],'file':frame['file'],'sha256':digest,
                                'box':region['box'],'pixels':patch.width*patch.height,
                                'min_rgb':rgb,'max_rgb':rgb,'rgb':rgb})
    if len({tuple(color['rgb']) for color in palette})!=125:
        raise ValueError('Measured palette has duplicate colors; inspect source/positions.')
    report={'schema':1,'source_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'method':manifest['method'],'colors':len(palette),'samples':samples}
    return palette,report


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=root/'data/palette_sources/2026-10-31/manifest.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.report.exists() or args.output.resolve()==args.report.resolve():
        raise FileExistsError('Use distinct new output/report paths; existing files are never overwritten.')
    palette,report=measure(args.manifest)
    for path,data in ((args.output,palette),(args.report,report)):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print(f'Measured {len(palette)} colors from original PNGs; all sample patches are uniform.')
