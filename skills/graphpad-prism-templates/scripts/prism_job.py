"""Prepare and launch Prism native scripts; inspect saved XML without dependencies."""
import argparse, json, subprocess, shutil, os
from pathlib import Path
import xml.etree.ElementTree as ET

EXE=Path(r'C:\Program Files\GraphPad\Prism 8\prism.exe')
CAT=Path(__file__).resolve().parents[1]/'references/catalog.json'

def quote(p):
    s=str(Path(p).resolve())
    if any(c in s for c in ['"','\r','\n']): raise ValueError('Invalid path')
    return '"'+s+'"'

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('prepare'); p.add_argument('--template-root',default=os.environ.get('PRISM_TEMPLATE_ROOT')); p.add_argument('--id',type=int,required=True); p.add_argument('--out',required=True); p.add_argument('--data'); p.add_argument('--table',type=int,default=1); p.add_argument('--graph',type=int,default=1); p.add_argument('--shape-verified',action='store_true')
    p=sp.add_parser('run'); p.add_argument('script'); p.add_argument('--exe',default=str(EXE))
    p=sp.add_parser('inspect'); p.add_argument('project')
    a=ap.parse_args()
    if a.cmd=='inspect':
        root=ET.parse(a.project).getroot()
        for node in root.iter():
            node.tag=node.tag.rsplit('}',1)[-1]
        for t in root.findall('Table'):
            cols=[]
            for c in list(t):
                if c.tag.endswith('Column'):
                    cols.append(dict(kind=c.tag,title=c.findtext('Title'),attributes=c.attrib,subcolumns=[len(s.findall('d')) for s in c.findall('Subcolumn')]))
            print(json.dumps(dict(id=t.get('ID'),title=t.findtext('Title'),attributes=t.attrib,columns=cols),ensure_ascii=False))
        for tag in ['TableSequence','GraphSequence']:
            el=root.find(tag)
            if el is not None: print(tag,ET.tostring(el,encoding='unicode'))
        return
    if a.cmd=='run':
        exe=Path(a.exe); script=Path(a.script).resolve()
        if not exe.is_file() or not script.is_file(): raise FileNotFoundError('Executable or script missing')
        print('Started PID',subprocess.Popen([str(exe),'@'+str(script)]).pid); return
    if a.table<1 or a.graph<1: raise ValueError('Sheet indices start at 1')
    if a.data and not a.shape_verified: raise ValueError('Inspect template and verify import mapping before --shape-verified')
    rows=json.loads(CAT.read_text(encoding='utf-8')); item=next((x for x in rows if x['id']==a.id),None)
    if item is None: raise ValueError('Unknown template id')
    if not a.template_root: raise ValueError('Set --template-root or PRISM_TEMPLATE_ROOT to your legally obtained local template directory')
    source=Path(a.template_root).resolve()/item['path']
    if not source.is_file(): raise FileNotFoundError(source)
    out=Path(a.out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    local=out/('template'+source.suffix); shutil.copy2(source,local)
    lines=['Open '+quote(local),'Save '+quote(out/'working.pzfx')]
    if a.data:
        data=Path(a.data).resolve()
        if not data.is_file(): raise FileNotFoundError(data)
        mapped=out/'mapped.tsv'; shutil.copy2(data,mapped)
        lines+=['GoTo D '+str(a.table),'ClearTable','Import '+quote(mapped),'RecalcAll']
    lines+=['GoTo G '+str(a.graph),'ExportPNG '+quote(out/'figure.png'),'ExportPDF '+quote(out/'figure.pdf'),'Save '+quote(out/'result.pzfx')]
    script=out/'job.pzc'
    # UTF-8 BOM permits Unicode Windows paths; validate acceptance in installed Prism.
    script.write_text('\r\n'.join(lines)+'\r\n',encoding='utf-8-sig')
    (out/'job.json').write_text(json.dumps(dict(template=item,has_user_data=bool(a.data),table=a.table,graph=a.graph,status='prepared, execution and visual QA pending'),ensure_ascii=False,indent=2),encoding='utf-8')
    print(script)

if __name__=='__main__': main()
