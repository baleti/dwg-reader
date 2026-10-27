# dwg-viewer

Open a .dwg in a browser without AutoCAD: model space and paper-space layouts (sheets) with viewports, layers, lineweights, linetype patterns, hatch patterns, text/mtext, dimensions (their anonymous blocks), blocks and plot styles. Pure Python backend (the sibling parser in this repo), Canvas2D front end, offline.

    bin/dwg-viewer /full/path/FILE.dwg                 # opens the first paper layout with content (else Model)
    bin/dwg-viewer FILE.dwg --layout Layout1           # by name or index
    bin/dwg-viewer --prepare A.dwg B.dwg               # demo prep: parse and cache every layout (re-opening is then instant), print READY
    bin/dwg-viewer FILE.dwg --no-browser --port 8800 --workspace 178

Supported file versions are those the parser reads (AC1015, AC1018, AC1024, AC1027, AC1032; R2007 AC1021 since the parser reads it (pyrender scores 0.98-0.998 on 6 of 7 files); R13/R14 via the experimental dwgr14 reader: model space only, only the entity types it decodes).

Also drawn: leaders (with DSTYLE overrides), multileaders, tables (their *T block), embedded OLE bitmaps, annotative text (the object-context layout of the viewport's annotation scale), wipeouts, image frames, viewport borders, non-rectangular and polygonal viewport clips, per-viewport layer freeze. Not drawn: raster image files (external), non-bitmap OLE objects, ACIS solids, proxy objects without graphics.

## Pipeline
parser (dwgmodel/dwgent) -> dwgviewer/flat.py (ByBlock/ByLayer, linetypes in final units, text options, hatch pattern lines, entity handles)
-> dwgviewer/build.py (scene JSON v2 per layout, viewport groups with clip) -> dwgviewer/server.py -> web/app.js.

## Interaction (CAD style)
- Left drag = selection box: left to right is a window (solid blue, only fully enclosed objects), right to left is crossing (dashed green, anything touched). Click picks one object, Shift toggles, Ctrl+A selects all visible, Esc clears; the count is in the status bar. Selected objects are highlighted (halo, dashed outline, grips) also inside paper-space viewports.
- Pan: middle or right drag, Space+drag, or the Pan button / H. Wheel zooms at the cursor. F fits.
- Panning and zooming never blank the text or turn dashes solid: heavy drawings are shown from a cached bitmap while moving and redrawn in full when the gesture settles.
- Object categories (top bar): Dims, Leaders, Blocks, Curves, Masks, Images show/hide independently of layers (hidden objects are not selectable).
- Layer states: Save, Restore and Delete named states (On, Freeze, Lock, colour overrides, VP freezes, object categories), kept per drawing in the browser.
- Layer Properties Manager (left): Status, Name, On, Frz, Lck, Color (override), Linetype, Lineweight, Transp, Plot, VP Frz, Description; sort by column, filter by name pattern or state (used/unused/off/frozen/locked/layers of the selection); multi-select with click, Shift range, Ctrl toggle, Ctrl+A; bulk On/Off, Freeze, Lock, Isolate, Off sel., All on, VP freeze (current viewport = last clicked viewport), Select objects on layers, Layers of selection, Invert, Reset. Named layer states are not read yet (parser).

## Control panel
layer toggles, object-type toggles (lines, hatch, text), lineweight on/off and multiplier, dark background, plot style (CTB from `$DWG_PLOTSTYLE_DIR` or the local oracle `_ref` folder: colour/lineweight mapping, non-plot layers hidden), click to pick an entity (handle, layer, colour, lineweight, parser properties).

## More tools (2026-10)
- Measure (M): click points, snaps to vertices / midpoints / intersections (Shift = no snap); length, last segment, dx / dy, bearing, area, perimeter, angle; inside a viewport the numbers are model units. Selection info adds total length and area. Find text: Ctrl+F. PNG button saves the current view.
- Xrefs: the toolbar badge lists external references; an xref DWG found next to the drawing (or in a folder of `DWG_XREF_PATH`, os.pathsep separated) is drawn under its INSERT (layers `xref|layer`). INSERT clipping (XCLIP) is honoured (`DWG_NO_XCLIP=1` turns it off for A/B).
- Plot style: pick a table found locally, or load a .ctb from disk with the `.ctb...` button.
- tools/pdfcompare.py FILE LAYOUT PDF [--fit bounds]: whole-sheet comparison against any plotted PDF (e.g. the PDFs delivered with a drawing set); tools/render_bench.py FILE LAYOUT: render timings.

## Checks (local, need oracle-out from the AutoCAD VM)
- tools/vcompare.py FILE LAYOUT: headless render versus the AutoCAD plot (fixed.pdf), ink precision/recall, side-by-side PNG into ~/review-compare-dwg.
- tools/pyrender.py FILE LAYOUT: the same comparison without any browser (PIL renderer of the scene rows: solid/dashed lines, solid hatches, Liberation text, viewport clips and VP freezes); coarser than the browser (no hatch patterns, no SHX) but good for host1 regression sweeps: AC1032_09 L1 0.989/0.991, AC1027_29 Model 0.999/1.0, AC1018_38 L1 0.896/0.978, AC1032_26 L1 0.891/0.812 (browser 0.995 / 0.953 / 0.982 / 0.95).
- tools/vsweep.py OUT FILE...: vcompare over many files. tools/chk_vports.py STEM...: viewport numbers versus the AutoCAD dump.
- tools/ui_test.py FILE [LAYOUT]: scripted browser test (tools/cdp.py, DevTools protocol): selection, highlight pixels, layer table, VP freeze, pan/zoom flicker checks.
- tools/demo_ready.py FILE...: pre-demo check (warm cache + smoke test) that prints the exact demo command per file.
- tests/test_geometry.py: pure unit tests (splines, bulges, matrices, mirrored OCS, MINSERT offsets): python3 -m unittest discover -s tests.
- tools/smoke.py FILE: headless server smoke test (run before committing viewer changes).
Outputs derived from client drawings stay local; never commit corpus, dumps or plots.
