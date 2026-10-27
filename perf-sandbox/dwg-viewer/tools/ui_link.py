#!/usr/bin/env python3
"""ui_link.py FILE LAYOUT : Link round trip (headless chromium): freeze a layer in a viewport, pick another annotation scale, hide a layer, build the link,
reopen it and check that the same state is restored (VP freeze, annotation scale, hidden layer, view)."""
import sys, os, asyncio, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Session

FAILS = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' : ' + str(info)) if info != '' else ''))
    if not cond: FAILS.append(name)


async def main(path, layout):
    async with Session(path) as s:
        await s.open(layout=layout)
        li = await s.js("layIdx")
        await s.js("lay.vps[0].fzs.add(1); curVp = 0; layerTableViewportChanged(); 1")
        sc = await s.js("(()=>{const e=document.getElementById('vpAnno'); if (e.style.display==='none') return null; e.selectedIndex=(e.selectedIndex+1)%e.options.length; e.onchange(); return lay.vps[0].an})()")
        ctb = await s.js("(async()=>{const e=$('ctb'); if (e.options.length < 2) return ''; e.value = e.options[1].value; await e.onchange({target: e}); return e.value})()")
        await s.js("lyOn[2] = false; applyLayerState(); 1")
        link = await s.js("(async()=>{let u=''; const orig=navigator.clipboard; Object.defineProperty(navigator,'clipboard',{value:{writeText:async t=>{u=t}},configurable:true}); await $('linkBtn').onclick(); return u})()")
        check('link built', bool(link) and '?' in link, link[:120] if link else link)
    async with Session(path) as s2:
        await s2.open(query=link.split('?', 1)[1], layout=None)
        check('layout restored', await s2.js("layIdx") == li)
        check('VP freeze restored', await s2.js("lay.vps[0].fzs.has(1)") is True)
        check('hidden layer restored', await s2.js("lyOn[2]") is False)
        if ctb: check('plot style restored', await s2.js("$('ctb').value") == ctb, ctb)
        if sc is not None: check('annotation scale restored', abs(await s2.js("lay.vps[0].an") - sc) < 1e-9, sc)
    print(json.dumps({'fails': FAILS})); return 1 if FAILS else 0

sys.exit(asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)))
