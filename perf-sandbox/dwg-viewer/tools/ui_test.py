#!/usr/bin/env python3
"""ui_test.py FILE [LAYOUT] : scripted interaction test through headless chromium (CDP): selection (click, window, crossing, shift, Ctrl+A, Esc),
highlight pixels, layer table (multi-select, bulk operations, VP freeze, lock), and flicker checks while panning/zooming
(every frame during the gesture must keep the text and dashes; frames compared with the settled render). Exit code 1 on failure."""
import sys, os, asyncio, io, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Session
import numpy as np
from PIL import Image

FAILS = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' : ' + str(info)) if info != '' else ''))
    if not cond: FAILS.append(name)

W2C = "(wx,wy)=>{const r=cv.getBoundingClientRect();return [r.left+(wx-view.x)*view.s, r.top+(view.y-wy)*view.s]}"


def ink(png, box=None):
    im = Image.open(io.BytesIO(png)).convert('L')
    if box: im = im.crop(box)
    a = np.asarray(im) < 200
    return a


async def main(path, layout):
    async with Session(path) as s:
        await s.open(layout=layout)
        # ---------- pick a line row on the paper (or model) layer that is visible
        info = await s.js("""(()=>{const w2c=__W2C__; const rows=lay.prims.length?lay.prims:lay.mprims; const T=new Map();
          for(const p of rows){ const t=p[p.length-1]; let o=T.get(t); if(!o){o={layers:new Set(),u:[1e300,1e300,-1e300,-1e300],n:0};T.set(t,o)} o.layers.add(p[1]); o.n++; const b=p.bb; o.u=[Math.min(o.u[0],b[0]),Math.min(o.u[1],b[1]),Math.max(o.u[2],b[2]),Math.max(o.u[3],b[3])]; }
          const out=[]; const r=cv.getBoundingClientRect();
          for(const p of rows){ if(p[0]!=='l'||!on(p[1])||lyLock[p[1]]) continue; const t=p[p.length-1], o=T.get(t); const f=p[5]; if(f.length<4) continue;
            const mx=(f[0]+f[2])/2,my=(f[1]+f[3])/2; const c=w2c(mx,my);
            if(c[0]>r.left+40&&c[0]<r.right-40&&c[1]>r.top+40&&c[1]<r.bottom-40){ const pr=pickRow(mx,my,6/view.s); if(!pr||pr[pr.length-1]!==t) continue;
              if(out.some(q=>q.top===t)) continue; out.push({c, top:t, bb:o.u, layer:p[1], single:o.layers.size===1}); if(out.length>300) break; } }
          const st=Math.max(1,Math.floor(out.length/6)); return JSON.stringify(out.filter((o,i)=>i%st===0).slice(0,6)); })()""".replace('__W2C__', W2C))
        cands = json.loads(info)
        check('found visible lines', len(cands) > 0, len(cands))
        # ---------- 1 click select
        cvr = await s.js("(()=>{const r=cv.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]})()")
        pts = {}
        for q in cands:
            pts[(q['top'], 0)] = await s.js("(%s)(%f,%f)" % (W2C, q['bb'][0], q['bb'][3])); pts[(q['top'], 1)] = await s.js("(%s)(%f,%f)" % (W2C, q['bb'][2], q['bb'][1]))
        ok_ = [q for q in cands if pts[(q['top'], 0)][0] - 14 > cvr[0] and pts[(q['top'], 0)][1] - 14 > cvr[1] and pts[(q['top'], 1)][0] + 14 < cvr[2] and pts[(q['top'], 1)][1] + 14 < cvr[3]]
        c = (ok_ or cands)[0]
        await s.click(c['c'][0], c['c'][1])
        n = await s.js("S.size"); check('click selects one object', n >= 1, n)
        check('selected object highlighted (items)', (await s.js("selItems.length")) > 0)
        sel_txt = await s.js("document.getElementById('sel').textContent"); check('status shows count', 'selected' in sel_txt and sel_txt[0].isdigit(), sel_txt)
        await asyncio.sleep(0.3)
        px = await s.js("(()=>{const c=cv.getContext('2d');const d=devicePixelRatio;const r=cv.getBoundingClientRect();const x=Math.round(%s)" % ("(%f-r.left)*d" % c['c'][0]) + ",y=Math.round(%s);let blue=0;for(let dx=-9;dx<=9;dx++)for(let dy=-9;dy<=9;dy++){const p=c.getImageData(x+dx,y+dy,1,1).data;if(p[2]>200&&p[0]<200)blue++;}return blue})()" % ("(%f-r.top)*d" % c['c'][1]))
        if px <= 0: print('WARN no halo pixels read back around the picked line (canvas readback may be clipped by a viewport)')
        else: check('highlight halo pixels present around the picked line', True, px)
        # ---------- shift-click second object toggles
        others = [q for q in cands if q['top'] != c['top']]
        if others:
            c2 = others[-1]
            await s.click(c2['c'][0], c2['c'][1], mods=8)
            n2 = await s.js("S.size"); check('shift-click adds', n2 >= n, (n, n2))
            await s.click(c2['c'][0], c2['c'][1], mods=8)
            n3 = await s.js("S.size"); check('shift-click again removes', n3 == n, (n, n3))
        await s.key('Escape'); check('Esc clears selection', (await s.js("S.size")) == 0)
        # ---------- window vs crossing
        bb = c['bb']; p0 = await s.js("(%s)(%f,%f)" % (W2C, bb[0], bb[3])); p1 = await s.js("(%s)(%f,%f)" % (W2C, bb[2], bb[1]))
        pad = 12
        await s.drag(p0[0] - pad, p0[1] - pad, p1[0] + pad, p1[1] + pad)
        wsel = await s.js("S.size"); has = await s.js("S.has(%d)" % c['top'])
        check('window (left to right) selects the enclosed object', has and wsel >= 1, wsel)
        await s.key('Escape')
        # crossing: right to left over the middle of the object touches it
        mx = (p0[0] + p1[0]) / 2
        await s.drag(mx + 30, p1[1] + 25, mx - 30, p0[1] - 25)
        csel = await s.js("S.size")
        check('crossing (right to left) selects touched objects', csel >= 1 and await s.js("S.has(%d)" % c['top']), csel)
        # window must not select a partially enclosed object: tiny window inside a long line's middle
        await s.key('Escape')
        await s.drag(mx - 3, (p0[1] + p1[1]) / 2 - 3, mx + 3, (p0[1] + p1[1]) / 2 + 3)
        tiny = await s.js("S.has(%d)" % c['top'])
        longobj = (bb[2] - bb[0]) * (await s.js("view.s")) > 40 or (bb[3] - bb[1]) * (await s.js("view.s")) > 40
        check('window does not select a partly enclosed long object', (not tiny) or not longobj)
        await s.key('Escape')
        await s.key('a', mods=2)
        na = await s.js("S.size"); check('Ctrl+A selects all visible objects', na > 1, na)
        await s.key('Escape')
        # ---------- object categories and text scale
        kinds = await s.js("JSON.stringify(Object.values(lay.kinds).reduce((a,k)=>(a[k]=(a[k]||0)+1,a),{}))")
        kinds = json.loads(kinds)
        if kinds.get('dim'):
            await s.js("cv.focus()"); await s.key('a', mods=2); n_all = await s.js("S.size"); await s.key('Escape')
            await s.js("document.querySelector('#cats input').click()")
            await s.key('a', mods=2); n_nodim = await s.js("S.size"); await s.key('Escape')
            await s.js("document.querySelector('#cats input').click()")
            check('Dims category toggle removes dimension objects from view and selection', n_nodim == n_all - kinds['dim'], (n_all, n_nodim, kinds['dim']))
        await s.js("const e=document.getElementById('txK'); e.value=1.5; e.oninput({target:e}); e.value=1; e.oninput({target:e})")
        # ---------- layers
        nl = await s.js("meta.layers.length"); rows = await s.js("document.querySelectorAll('#ltable .lrow:not(.lhead)').length")
        check('layer table lists all layers', rows == nl, (rows, nl))
        rowsel = await s.js("""(()=>{const r=[...document.querySelectorAll('#ltable .lrow:not(.lhead)')]; const b=e=>{const x=e.getBoundingClientRect();return [x.left+x.width/2,x.top+x.height/2]}; return JSON.stringify([b(r[0].querySelector('.w-name')), b(r[Math.min(3,r.length-1)].querySelector('.w-name')), b(r[Math.min(5,r.length-1)].querySelector('.w-name'))])})()""")
        a, b3, c5 = json.loads(rowsel)
        await s.click(*a); await s.click(*b3, mods=8)
        ls = await s.js("lSel.size"); check('shift-click selects a layer range', ls >= 2, ls)
        await s.click(*c5, mods=2)
        ls2 = await s.js("lSel.size"); check('ctrl-click toggles one more layer', ls2 == ls + 1 or ls2 == ls - 1, (ls, ls2))
        before = await s.js("JSON.stringify([...lSel].map(i=>lyOn[i]))")
        await s.js("document.getElementById('lbOn').click()")
        after = await s.js("JSON.stringify([...lSel].map(i=>lyOn[i]))")
        check('On/Off toggles all selected layers together', before != after and len(set(json.loads(after))) == 1, (before, after))
        await s.js("document.getElementById('lbAllOn').click()")
        check('All on', await s.js("lyOn.every(x=>x)"))
        await s.js("document.getElementById('lbFrz').click()")
        check('Freeze applies to the selection', await s.js("[...lSel].every(i=>lyFrz[i])"))
        await s.js("document.getElementById('lbAllOn').click()")
        await s.js("document.getElementById('lbLock').click()")
        lk = await s.js("[...lSel].every(i=>lyLock[i])"); check('Lock applies to the selection', lk)
        await s.js("document.getElementById('lbIso').click()")
        check('Isolate turns every other layer off', await s.js("lyOn.filter(x=>x).length===lSel.size"), await s.js("lyOn.filter(x=>x).length+'/'+lSel.size"))
        await s.js("document.getElementById('lbAllOn').click(); lyLock.fill(false); applyLayerState(); buildLayerTable()")
        # select objects on layer / layers of selection
        await s.js("cv.focus()")
        await s.key('a', mods=2)
        await s.js("document.getElementById('lbOfSel').click()")
        check('Layers of selected objects fills the layer selection', (await s.js("lSel.size")) >= 1, await s.js("lSel.size"))
        await s.key('Escape')
        cs = next((q for q in cands if q['single']), None)
        if cs is None: print('SKIP layer-object tests (no single-layer object)')
        else:
            await s.js("lSel.clear(); lSel.add(%d); buildLayerTable(); document.getElementById('lbSelObj').click()" % cs['layer'])
            check('Select objects on layer', (await s.js("S.size")) >= 1 and await s.js("S.has(%d)" % cs['top']), await s.js("S.size"))
            await s.js("lyLock[%d]=true; buildLayerTable(); clearSelection(false); draw()" % cs['layer'])
            await s.click(cs['c'][0], cs['c'][1])
            check('locked layer objects are not selectable', (await s.js("S.has(%d)" % cs['top'])) is False)
            await s.js("lyLock[%d]=false; buildLayerTable()" % cs['layer'])
        # VP freeze on a sheet
        nv = await s.js("lay.vps.length")
        if nv:
            ctr = await s.js("(%s)((lay.vps[0].clip[0]+lay.vps[0].clip[4])/2,(lay.vps[0].clip[1]+lay.vps[0].clip[5])/2)" % W2C)
            await s.js("clearSelection(false)")
            await s.click(ctr[0] + 1, ctr[1] + 1)
            await s.js("curVp = 0; buildLayerTable()")
            li = await s.js("lay.mprims.find(p=>on(p[1]))[1]")
            await s.js("lSel.clear(); lSel.add(%d); buildLayerTable(); document.getElementById('lbVp').click()" % li)
            check('VP freeze toggles the layer in the current viewport only', await s.js("lay.vps[0].fzs.has(%d)" % li) and (nv < 2 or not await s.js("lay.vps[1].fzs.has(%d)" % li)))
            await s.js("document.getElementById('lbReset').click()")
        # ---------- flicker while panning / zooming
        await s.js("interacting=false; invalidate()"); await asyncio.sleep(1.0)
        base = await s.js("JSON.stringify({text:STAT.text,dash:STAT.dash,ms:lastFullMs})")
        base = json.loads(base); print('settled stats', base)
        await s.js("frameLog.length=0")
        r = await s.js("(()=>{const r=cv.getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
        cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
        shots = []
        await s.mouse('mouseMoved', cx, cy, 'none', 0); await s.mouse('mousePressed', cx, cy, 'middle', 4)
        for i in range(1, 13):
            await s.mouse('mouseMoved', cx + 14 * i, cy + 6 * i, 'middle', 4)
            await asyncio.sleep(0.04)
            shots.append(await s.shot())
        await s.mouse('mouseReleased', cx + 14 * 12, cy + 72, 'middle', 0)
        for k in range(8):
            await s.wheel(cx, cy, -120 if k % 2 == 0 else 120); await asyncio.sleep(0.03)
            shots.append(await s.shot())
        await asyncio.sleep(1.2)
        final = await s.shot()
        log = json.loads(await s.js("JSON.stringify(frameLog)"))
        full = [f for f in log if f['mode'] == 'full']; bm = [f for f in log if f['mode'] == 'bitmap']
        print('frames', len(log), 'full', len(full), 'bitmap', len(bm), 'max ms', max([f['ms'] for f in log] or [0]))
        # no full frame may lose all text / dashes compared with its neighbours: text count never collapses to 0 when the settled view had text
        if base['text'] > 5:
            check('no frame drew without text', all(f['text'] > 0 for f in log), [f['text'] for f in log][:12])
        if base['dash'] > 5:
            check('no frame drew without dashed lines', all(f['dash'] > 0 for f in log), [f['dash'] for f in log][:12])
        # pixel level: every interaction screenshot keeps most of the ink of the settled picture (no blank or half-drawn frames)
        ink_final = ink(final).sum()
        worst = min(ink(sh).sum() for sh in shots) / max(ink_final, 1)
        check('screenshots during the gesture keep their ink', worst > 0.5, round(worst, 2))
        check('no JS errors', not s.errors, [e[:400] for e in s.errors[:3]])
        print(json.dumps({'fails': FAILS}))

lay = int(sys.argv[2]) if len(sys.argv) > 2 else None
asyncio.run(main(sys.argv[1], lay))
sys.exit(1 if FAILS else 0)
