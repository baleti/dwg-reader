# DWG parser accuracy against AutoCAD (aggregate numbers only)

Ground truth: AutoCAD 2026 in an offline VM dumps every corpus drawing (entities, tables, layouts, header); our own parser is compared per object with `tools/oracle/chk_*.py`. The corpus itself and the dumps are local-only and not published. Corpus: 59 drawings, AC1009 to AC1032. Numbers below are from the last sweeps (2026-10-19; ellipse, attributes and text properties re-run after the R13/R14 reader work: 56 of 59 files now readable); R13/R14 decoding is being extended, so those rows move.

| Check | Compared | Match | Note |
|---|---|---|---|
| LINE/CIRCLE/ARC/LWPOLYLINE/INSERT/POINT geometry, layer, colour, lineweight | 40 readable files | 36 files exact | rest: fit-point splines (derived control points), one anonymous-block INSERT |
| Fit-point spline to NURBS (recipe `fitspline.py`) | 11 splines | 11 (error < 1e-10) | chord-length knots, natural ends |
| TEXT/MTEXT/HATCH multiset | 76 comparisons | 69 exact | rest: fields re-evaluated by AutoCAD, annotative scale, diameter glyph |
| TEXT/MTEXT properties (height, rotation, style, width, attachment) | 20406 | 20397 | 56 files readable |
| DIMENSION (measurement, text position, user text, definition points) | 2922 | 2922 | 49 files |
| HATCH (pattern, scale, angle, loops, boundary) | 22649 | 22630 | 19 hatches in unreferenced anonymous blocks are skipped on purpose; all others match |
| ELLIPSE | 25197 | 25126 | 71 missing, all R13/R14 |
| WIPEOUT/IMAGE clip boundary | 4052 | 4052 | |
| INSERT attributes | 3158 | 3150 | one anonymous block (8 INSERTs in 2 files) |
| Symbol tables (layers, text styles, linetypes, dimstyles) | 40 files | 38 exact | 2 internal layers only |
| Header variables (~117 per file) | 57 files | 54 exact | plot-style name code page; text size in two files |
| Layouts (name, order, limits, style sheet, origin) | 148 | 148 | |
| Paper-space viewports (view, height, direction, twist) | 150 | 119 | the rest are the overall viewport AutoCAD recomputes (not drawn); one frozen-layer case |

Not yet readable by the parser: 19 of 59 files (AC1009, most AC1021). R13/R14 files load; DIMENSION is now exact in all 9, HATCH within 2 of 322; still missing VIEWPORT, ELLIPSE, LEADER, XLINE, some polylines (AutoCAD counts 2D polylines as LWPOLYLINE there), plus a small surplus of POINT/MTEXT/SOLID/INSERT in 3 files.

## Added 2026-10-21 (c8-dwgparser)
| Check | Compared | Match | Note |
|---|---|---|---|
| Entity counts per type (countcmp), 57 readable files incl. AC1021 | 57 files | 50 exact | rest: AutoCAD-created objects not stored in the file (TEXT/MTEXT/INSERT of unresolved xrefs and annotative evaluation), proxy entities, PDF underlay (now decoded) |
| Entity-level properties (visibility, linetype scale, linetype, colour method, transparency), chk_props | all handle-keyed entities | 0 differences | |
| INSUNITS / lineweight display / celweight (header tail R2007+) | 32 files | 32 | |
| INSUNITS (R2000) | 6 files | 6 | |
| Native fast path vs Python reference | 1.4M objects, 252 files of dwg2text | 0 differences | |
| AC1021 object CRC chain over the sampled corpus | 20,880 files | 20,880 | 15 container failures fixed afterwards |
