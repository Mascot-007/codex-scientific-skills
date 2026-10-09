"""Local editable scientific figures; SVG cache to Illustrator and PowerPoint."""
from pathlib import Path
import argparse, json, shutil, subprocess, sys, xml.etree.ElementTree as ET
from urllib.parse import unquote

VENDOR=Path(__file__).resolve().parent/'vendor'
sys.path.insert(0,str(VENDOR))
import prepare_geometry_cache as geometry

def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def do_js(app,script):
    import pythoncom
    return str(app._oleobj_.Invoke(app._oleobj_.GetIDsOfNames('DoJavaScript'),0,pythoncom.DISPATCH_METHOD,True,script))

def illustrator(cache,state,out):
    import win32com.client
    app=win32com.client.Dispatch('Illustrator.Application')
    w,h=cache['view_box'][2:]
    fields=do_js(app,f'(function(){{var d=app.documents.add(DocumentColorSpace.RGB,{w},{h});return encodeURIComponent(d.name)+"|"+encodeURIComponent(d.activeLayer.name);}})()').split('|')
    info=dict(name=unquote(fields[0]),layer=unquote(fields[1]))
    runtime=(VENDOR/'cell_lct_cached_runtime.jsx').read_text(encoding='utf-8-sig')
    def call(c):
        result=do_js(app,'var CELL_LCT_CACHED_CONFIG='+json.dumps(c,ensure_ascii=True)+';\n'+runtime)
        if not result.startswith('OK|'): raise RuntimeError(result)
        return result
    for b in state['batches']:
        p=out/'geometry-cache'/f"batch-{b['index']}.json"
        write_json(p,dict(viewBox=cache['view_box'],atoms=[cache['atoms'][i] for i in b['atom_indices']]))
        call(dict(operation='draw',batchJsonPath=p.as_posix(),targetDocumentName=info['name'],targetLayerName=info['layer'],rootGroupName=state['root_group_name'],batchGroupName=b['group_name'],placement='center',maxWidthFraction=1,maxHeightFraction=1,delayMs=0))
    result=call(dict(operation='save',targetDocumentName=info['name'],outputAi=(out/'figure.ai').as_posix()))
    name=result.split('documentName=',1)[1]
    call(dict(operation='export',targetDocumentName=name,outputPng=(out/'illustrator.png').as_posix()))
    pdf=(out/'illustrator.pdf').as_posix()
    qa=do_js(app,'(function(){var d=app.activeDocument;var p=new PDFSaveOptions();d.saveAs(new File('+json.dumps(pdf)+'),p);var a=[];for(var i=0;i<d.textFrames.length;i++)a.push(encodeURIComponent(d.textFrames[i].contents));return [d.textFrames.length,d.pathItems.length,d.compoundPathItems.length,app.version,a.join("|")].join("|");})()').split('|')
    return dict(text_count=int(qa[0]),path_count=int(qa[1]),compound_count=int(qa[2]),version=qa[3],texts=[unquote(x) for x in qa[4:] if x])

def powerpoint(out):
    import win32com.client
    app=win32com.client.Dispatch('PowerPoint.Application')
    pres=app.Presentations.Open(str(out/'figure.pptx'),False,False,True)
    slide=pres.Slides.Item(1)
    slide.Export(str(out/'powerpoint.png'),'PNG',1600,int(1600*pres.PageSetup.SlideHeight/pres.PageSetup.SlideWidth))
    pres.SaveAs(str(out/'powerpoint.pdf'),32)
    texts=[]
    for i in range(1,slide.Shapes.Count+1):
        s=slide.Shapes.Item(i)
        if s.HasTextFrame and s.TextFrame.HasText: texts.append(s.TextFrame.TextRange.Text)
    return dict(version=str(app.Version),shape_count=slide.Shapes.Count,text_count=len(texts),texts=texts)

def main():
    p=argparse.ArgumentParser();p.add_argument('--svg',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--application',choices=['ai','ppt','both'],default='both');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    source=a.svg.resolve();out=a.out.resolve()
    if not source.is_file(): raise FileNotFoundError(source)
    out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(source,out/'master.svg')
    cache,state=geometry.prepare(out/'master.svg',out/'geometry-cache',out.name,20,50,320,2200)
    texts=[x for x in cache['atoms'] if x['kind']=='text']
    write_json(out/'text-manifest.json',dict(source_canvas=cache['view_box'],text_atoms=texts))
    qa=dict(source=str(source),expected_text_count=len(texts),atom_count=len(cache['atoms']),status='prepared')
    write_json(out/'verification.json',qa)
    if a.prepare_only: print(json.dumps(qa));return
    try:
        if a.application in ['ppt','both']:
            subprocess.run([sys.executable,str(VENDOR/'run_cell_ppt_ooxml.py'),'--geometry-cache',str(out/'geometry-cache/geometry-cache.json'),'--output-pptx',str(out/'figure.pptx')],check=True)
            qa['powerpoint']=powerpoint(out)
        if a.application in ['ai','both']: qa['illustrator']=illustrator(cache,state,out)
        for k in ['powerpoint','illustrator']:
            if k in qa and qa[k]['text_count']!=len(texts): raise RuntimeError(f'{k} text count mismatch')
            if k in qa and sorted(qa[k]['texts'])!=sorted(t['text']['contents'] for t in texts): raise RuntimeError(f'{k} text content mismatch')
        qa['status']='rendered; visual inspection required'
    except Exception as e:
        qa['status']='failed';qa['error']=str(e);raise
    finally: write_json(out/'verification.json',qa)
    print(json.dumps(qa,ensure_ascii=False))

if __name__=='__main__':main()
