#!/usr/bin/env python3
"""chk_text_just.py STEM... : TEXT box (AutoCAD ext) relative to the alignment point for every justification other than left/baseline; compare with the offsets web/app.js uses."""
import sys,json,collections; sys.path.insert(0,'/home/user1/dwg-viewer')
from dwgviewer import build
res=collections.defaultdict(list)
for stem in sys.argv[1:]:
    d=json.load(open('/home/user1/dwg-research/oracle-out/%s/dump.json'%stem))
    orc={}
    for b in d['blocks']:
        for e in b.get('entities',[]):
            if e['t']=='TEXT' and e.get('ext') and e.get('al') and (e.get('hm'),e.get('vm'))!=('TextLeft','TextBase') and e.get('rot',0)==0:
                orc[(e['layer'],e['s'],round(e['al'][0],1),round(e['al'][1],1))]=e
    doc=build.Doc('/home/user1/dwg-research/corpus/%s.dwg'%stem)
    for es in doc.sc.by_block.values():
        for e in es:
            if e['kind']!='TEXT' or abs(e['rot'])>1e-6: continue
            o=orc.get((e['layer'],e['text'],round(e['align'][0],1),round(e['align'][1],1)))
            if not o: continue
            ext=o['ext']; h=e['height']; ax,ay=e['align'][0],e['align'][1]
            res[(o['hm'],o['vm'],'x_center')].append(((ext[0]+ext[3])/2-ax)/h)
            res[(o['hm'],o['vm'],'x_min')].append((ext[0]-ax)/h)
            res[(o['hm'],o['vm'],'x_max')].append((ext[3]-ax)/h)
            res[(o['hm'],o['vm'],'y_min')].append((ext[1]-ay)/h)
            res[(o['hm'],o['vm'],'y_max')].append((ext[4]-ay)/h)
for k,v in sorted(res.items()):
    v.sort(); print(k,len(v),'median %.3f p10 %.3f p90 %.3f'%(v[len(v)//2],v[len(v)//10],v[9*len(v)//10]))
