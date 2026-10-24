# DWG writer / editor (own code) - quick guide
Needs `templates/blank_<year>.dwg` (tools/make_templates.sh, one-time, local). Versions: AC1015 (R2000), AC1018, AC1024, AC1027, AC1032. All output verified with AutoCAD AUDIT (wtest.py).

```python
import dwgdoc, dwgxform as X
doc = dwgdoc.Doc(open('templates/blank_2018.dwg','rb').read())      # or any existing drawing: edits keep untouched objects byte-exact
doc.add_layer('A-WALL', color=3, lineweight=50); doc.add_style('Arial-100','arial.ttf'); doc.add_ltype('DASHED','Dashed',[12.5,-6.25])
doc.add_line((0,0),(1000,0),layer='A-WALL'); doc.add_circle/arc/point/lwpolyline/ellipse/text/mtext/solid/spline/hatch/leader/xline/ray/3dface/polyline2d(...)
doc.add_dimstyle('ARCH-50', DIMSCALE=50, DIMTXT=2.5); doc.add_dim_aligned/linear/radius/diameter/angular(...)
doc.add_block('DOOR'); doc.add_attdef('DOOR','MARK','prompt','D01',(0,0),100); doc.add_insert('DOOR',(0,0),attribs={'MARK':'D-17'})
lh = doc.add_layout('A3 Plan', paper=(420,297)); doc.add_viewport(lh,(210,148.5),(420,297),paper_viewport=True); doc.add_viewport(lh,(210,148.5),(380,260),view_center=(5000,3000),scale=1/50)
doc.add_xdata(h,'APP',[(1000,'x'),(1070,7)]); doc.add_xrecord(None,'KEY',[(1,'text'),(70,7)])
ls = doc.entities('*Model_Space'); doc.set_props(ls[0],color=3,layer='A-WALL'); doc.transform(ls[0],X.Transform.rotate((0,0),0.5)); doc.copy_entity(ls[1],X.Transform.mirror((0,0),(1,1))); doc.erase(ls[2])
doc.set_layer('A-WALL', new_name='WALLS'); doc.rename_block('DOOR','DOOR-A'); doc.delete_layer('OLD', force=True)
open('out.dwg','wb').write(doc.save())
```
CLI: `dwgtool.py info|layers|edit`. Tests: `python3 wtest.py OUTDIR` (AutoCAD VM), `chk_codec.py FILE -q` (codec round trip), `sweep_codec.py` (corpus, host1).
Internals: dwgcodec*.py symmetric per-object codecs; dwgwrite.py AutoCAD-strict container (see PROGRESS-WRITE.md for the rules found by experiment).

## Additions (2026-10-20)
- `doc.replace_text('old', 'new')` (TEXT, MTEXT, ATTDEF and INSERT attribute values, all blocks/layouts); CLI `dwgtool.py edit IN OUT --replace-text OLD NEW`.
- Shape linetypes: `doc.add_style('LTSHP', 'ltypeshp.shx', shapefile=True); doc.add_ltype('TRACKS', 'x', [10, dict(length=-5, shape=130, style='LTSHP'), -5])` (AUDIT clean R2000 and R2018).
- Older AC1015 files (BL-coded second header) can be edited; HANDSEED is located exactly (R2004 family via the header decoder).
- VM-free checks: `wtest_offline.py` (scenario build + re-read), `fuzz_edit.py SEED` (random edits on the local corpus), `worker_edit_doc.py FILE` (move/erase/retext + exact diff of all other entities).
