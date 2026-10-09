"""Trace manually verified text-free images and restore live labels locally."""
from pathlib import Path
import argparse, subprocess, sys, json
import vtracer
def main():
    p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--text-removed',action='store_true');a=p.parse_args()
    if not a.text_removed: p.error('Visually confirm graphics input is text-free before --text-removed')
    out=a.out.resolve();raw=out.with_name(out.stem+'-graphics.svg')
    if out.exists() or raw.exists():raise FileExistsError('Output already exists')
    m=json.loads(a.manifest.read_text(encoding='utf-8-sig'))
    if m.get('schema_version')!='1.0' or not isinstance(m.get('text_elements'),list):raise ValueError('Invalid text manifest')
    out.parent.mkdir(parents=True,exist_ok=True)
    vtracer.convert_image_to_svg_py(str(a.image.resolve()),str(raw),colormode='color',mode='spline')
    subprocess.run([sys.executable,str(Path(__file__).resolve().parent/'vendor/merge_live_text.py'),'--input-svg',str(raw),'--text-manifest',str(a.manifest.resolve()),'--output-svg',str(out)],check=True)
if __name__=='__main__':main()
