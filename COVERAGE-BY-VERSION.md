# DWG decode coverage by version, measured against AutoCAD 2026 (2026-10-24)

Ground truth: AutoCAD 2026 in the offline VM (dump.json: every entity of every block with handle/type/geometry, tables, layouts, header variables). Sample: stratified
random pick from campaign21/sample.tsv, up to 40 files per version (all of AC1009/AC1012/AC1014/AC1015 except files over the size cap), files over 25 MB excluded
from the AutoCAD run. Aggregate numbers only; no client names or paths. Tools: campaign21/cov/{pick,dump_batch.sh,measure,run_all,aggregate,make_report}.

Metrics per file: opened = Model() raises no exception; counts exact = per-type entity counts equal AutoCAD's over all blocks; matched by count = sum over types of
min(ours, AutoCAD) / AutoCAD; matched by handle+type = the AutoCAD entity handle exists in our entity list with the same type (TEXT/MTEXT/ATTDEF/VIEWPORT: matched by
position + string (MTEXT formatting codes and braces normalized, AutoCAD rescales tab stops) instead, because the AutoCAD dump overwrites their handle with the height; R12 has no stored handles, AutoCAD numbers them on load: n/a);
geometry exact = coordinates equal to 1e-6 relative (LINE, ARC, CIRCLE, INSERT, LWPOLYLINE, POINT, SPLINE, HATCH pattern name, SOLID corners);
header exact = every header variable present in both with equal value (case-insensitive names); tables exact = layers, text styles, linetypes, dimstyles (DIMSCALE, DIMTXT, ...);
layouts exact = tab order, limits, plot settings, viewport count.

Known classes of difference that are AutoCAD behaviour, not parser errors: AutoCAD synthesizes Layout1, 12x9 limits and dimstyles for R12 (excluded for AC1009);
the dump omits anonymous dynamic-block copies (*U) that we list; TEXTSIZE header variable is reset by AutoCAD on load; 'name @ scale' viewport-override layers and *adsk_constraints are internal (ignored in the layer comparison);
One 16 MB AC1015 file is excluded because AutoCAD's dump of it is not valid JSON (twice); AutoCAD renumbers anonymous blocks (*D, *X) and drops unreferenced ones, so per-block comparison of those is not possible, only totals; AutoCAD regenerates dimension graphics and adds a default viewport to a layout that has none
(handles above the file's last object), which appear as small count differences (a few entities per file) that the file data cannot explain; R14 layer plot flags and R14 layout limits come from data not stored in the file or not decoded;
the dump's per-layout viewport list is empty for all but the first layouts of R13-R2000 files, so viewport counts of those versions are compared with the VIEWPORT entities of the layout's paper-space block. Empty STYLE font files are filled with txt.shx by AutoCAD (not counted).

## AC1009 (n=17 measured)

- files opened: 17/17 (100%)
- files with exact per-type entity counts: 17/17 (100%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 189729/189729 (100.00%)
- entities matched by handle+type: n/a (R12 has no stored handles, AutoCAD numbers them on load)
- header exact (all shared variables equal): 16/17 (94%); tables exact: 17/17 (100%); layouts exact: 17/17 (100%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 160273 | 100.00 | 5.13 | 0.00 |
| ARC | 10408 | 100.00 | 0.00 | - |
| CIRCLE | 2261 | 100.00 | 0.00 | - |
| POLYLINE | 2009 | 100.00 | 0.20 | - |
| INSERT | 4131 | 100.00 | 0.44 | 11.11 |
| TEXT | 2671 | 100.00 | 100.00 | 100.00 |
| DIMENSION | 545 | 100.00 | 0.00 | - |
| VIEWPORT | 4 | 100.00 | 100.00 | - |

Top failure causes (files affected, example ids):
1. header TEXTSIZE: 1 files (47e78289f2)

## AC1012 (n=28 measured)

- files opened: 28/28 (100%)
- files with exact per-type entity counts: 28/28 (100%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 306779/306779 (100.00%)
- entities matched by handle+type: 306779/306779 (100.00%)
- header exact (all shared variables equal): 27/28 (96%); tables exact: 28/28 (100%); layouts exact: 28/28 (100%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 275172 | 100.00 | 100.00 | 100.00 |
| ARC | 7627 | 100.00 | 100.00 | 100.00 |
| CIRCLE | 2496 | 100.00 | 100.00 | 100.00 |
| POLYLINE | 2868 | 100.00 | 100.00 | - |
| INSERT | 4744 | 100.00 | 100.00 | 100.00 |
| TEXT | 6410 | 100.00 | 100.00 | 100.00 |
| MTEXT | 392 | 100.00 | 100.00 | 100.00 |
| DIMENSION | 737 | 100.00 | 100.00 | - |
| SPLINE | 35 | 100.00 | 100.00 | 100.00 |
| ELLIPSE | 41 | 100.00 | 100.00 | 100.00 |
| VIEWPORT | 20 | 100.00 | 100.00 | - |

Top failure causes (files affected, example ids):
1. header TEXTSIZE: 1 files (b25fc9d57e)

## AC1014 (n=46 measured)

- files opened: 46/46 (100%)
- files with exact per-type entity counts: 46/46 (100%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 1589018/1589018 (100.00%)
- entities matched by handle+type: 1589016/1589018 (100.00%)
- header exact (all shared variables equal): 46/46 (100%); tables exact: 44/46 (96%); layouts exact: 43/46 (93%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 1407294 | 100.00 | 100.00 | 100.00 |
| ARC | 31986 | 100.00 | 100.00 | 100.00 |
| CIRCLE | 8809 | 100.00 | 100.00 | 100.00 |
| POLYLINE | 25557 | 100.00 | 100.00 | - |
| INSERT | 49070 | 100.00 | 100.00 | 100.00 |
| TEXT | 20948 | 100.00 | 99.99 | 99.99 |
| MTEXT | 6879 | 100.00 | 100.00 | 100.00 |
| HATCH | 5085 | 100.00 | 100.00 | 99.94 |
| DIMENSION | 5895 | 100.00 | 100.00 | - |
| SPLINE | 360 | 100.00 | 100.00 | 100.00 |
| ELLIPSE | 288 | 100.00 | 100.00 | 100.00 |
| VIEWPORT | 321 | 100.00 | 100.00 | - |
| REGION | 13 | 100.00 | 100.00 | - |

Top failure causes (files affected, example ids):
1. layouts limits: 3 files (fb83cecc86, 07af5af274, a85b0b625c)
1. tables layer/plot: 2 files (fb83cecc86, 07af5af274)

## AC1015 (n=29 measured)

- files opened: 29/29 (100%)
- files with exact per-type entity counts: 27/29 (93%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 459648/459704 (99.99%)
- entities matched by handle+type: 459580/459704 (99.97%)
- header exact (all shared variables equal): 29/29 (100%); tables exact: 29/29 (100%); layouts exact: 29/29 (100%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 331425 | 99.99 | 99.99 | 100.00 |
| ARC | 26381 | 100.00 | 100.00 | 100.00 |
| CIRCLE | 6198 | 100.00 | 100.00 | 100.00 |
| LWPOLYLINE | 23004 | 100.00 | 100.00 | 100.00 |
| POLYLINE | 5530 | 100.00 | 100.00 | - |
| INSERT | 22704 | 99.95 | 99.95 | 99.99 |
| TEXT | 13043 | 100.00 | 99.98 | 99.98 |
| MTEXT | 8382 | 99.94 | 99.18 | 99.18 |
| HATCH | 6348 | 100.00 | 100.00 | 99.94 |
| DIMENSION | 826 | 100.00 | 99.88 | 99.27 |
| SPLINE | 3329 | 100.00 | 100.00 | 100.00 |
| ELLIPSE | 5367 | 100.00 | 100.00 | 100.00 |
| VIEWPORT | 174 | 100.00 | 100.00 | 93.33 |
| REGION | 405 | 100.00 | 100.00 | - |

Top failure causes (files affected, example ids):
1. count mismatch INSERT: 2 files (59568cc658, 7c4e9f257c)
1. count mismatch LINE: 1 files (59568cc658)
1. count mismatch DIMENSION: 1 files (59568cc658)
1. count mismatch POINT: 1 files (59568cc658)
1. count mismatch MTEXT: 1 files (59568cc658)

## AC1018 (n=53 measured)

- files opened: 53/53 (100%)
- files with exact per-type entity counts: 52/53 (98%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 1096608/1096608 (100.00%)
- entities matched by handle+type: 1096593/1096608 (100.00%)
- header exact (all shared variables equal): 53/53 (100%); tables exact: 53/53 (100%); layouts exact: 53/53 (100%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 379879 | 100.00 | 100.00 | 100.00 |
| ARC | 28555 | 100.00 | 100.00 | 100.00 |
| CIRCLE | 1683 | 100.00 | 100.00 | 100.00 |
| LWPOLYLINE | 30966 | 100.00 | 100.00 | 100.00 |
| POLYLINE | 438235 | 100.00 | 100.00 | - |
| INSERT | 23881 | 100.00 | 100.00 | 100.00 |
| TEXT | 79181 | 100.00 | 100.00 | 100.00 |
| MTEXT | 6635 | 100.00 | 99.77 | 99.77 |
| HATCH | 71625 | 100.00 | 100.00 | 100.00 |
| DIMENSION | 276 | 100.00 | 100.00 | 100.00 |
| SPLINE | 23646 | 100.00 | 100.00 | 100.00 |
| ELLIPSE | 1098 | 100.00 | 100.00 | 100.00 |
| VIEWPORT | 205 | 100.00 | 100.00 | 100.00 |

Top failure causes (files affected, example ids):
1. count mismatch INSERT: 1 files (a749cee6a6)
1. count mismatch MTEXT: 1 files (a749cee6a6)

## AC1021 (n=95 measured)

- files opened: 95/95 (100%)
- files with exact per-type entity counts: 87/95 (92%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 3085762/3085826 (100.00%)
- entities matched by handle+type: 3085661/3085826 (99.99%)
- header exact (all shared variables equal): 95/95 (100%); tables exact: 94/95 (99%); layouts exact: 94/95 (99%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 1961445 | 100.00 | 100.00 | 100.00 |
| ARC | 391840 | 100.00 | 100.00 | 100.00 |
| CIRCLE | 18731 | 100.00 | 100.00 | 100.00 |
| LWPOLYLINE | 203168 | 100.00 | 100.00 | 100.00 |
| POLYLINE | 61005 | 100.00 | 100.00 | - |
| INSERT | 94760 | 99.99 | 99.99 | 99.99 |
| TEXT | 3962 | 100.00 | 100.00 | 100.00 |
| MTEXT | 35515 | 99.98 | 99.71 | 99.71 |
| HATCH | 75876 | 100.00 | 100.00 | 100.00 |
| DIMENSION | 4695 | 100.00 | 99.98 | 100.00 |
| SPLINE | 145283 | 100.00 | 100.00 | 100.00 |
| ELLIPSE | 46624 | 100.00 | 100.00 | 100.00 |
| VIEWPORT | 529 | 99.81 | 99.81 | 100.00 |
| REGION | 3 | 100.00 | 100.00 | - |

Top failure causes (files affected, example ids):
1. count mismatch INSERT: 7 files (2c48b51825, 1d50908c72, b238d20c6c, bf8afe3e8b)
1. count mismatch MTEXT: 2 files (2c48b51825, a0b136f7da)
1. count mismatch LINE: 1 files (2c48b51825)
1. count mismatch POINT: 1 files (2c48b51825)
1. count mismatch DIMENSION: 1 files (2c48b51825)

## AC1024 (n=95 measured)

- files opened: 95/95 (100%)
- files with exact per-type entity counts: 88/95 (93%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 4507493/4507868 (99.99%)
- entities matched by handle+type: 4507434/4507868 (99.99%)
- header exact (all shared variables equal): 95/95 (100%); tables exact: 95/95 (100%); layouts exact: 95/95 (100%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 3015041 | 100.00 | 100.00 | 100.00 |
| ARC | 478976 | 100.00 | 100.00 | 100.00 |
| CIRCLE | 24803 | 100.00 | 100.00 | 100.00 |
| LWPOLYLINE | 224930 | 100.00 | 100.00 | 100.00 |
| POLYLINE | 6197 | 100.00 | 100.00 | - |
| INSERT | 209413 | 99.98 | 99.98 | 100.00 |
| TEXT | 26843 | 100.00 | 99.99 | 99.99 |
| MTEXT | 51134 | 99.89 | 99.78 | 99.78 |
| HATCH | 148248 | 100.00 | 100.00 | 99.98 |
| DIMENSION | 8600 | 100.00 | 100.00 | 99.99 |
| SPLINE | 115741 | 100.00 | 100.00 | 100.00 |
| ELLIPSE | 171175 | 100.00 | 100.00 | 100.00 |
| VIEWPORT | 780 | 100.00 | 100.00 | 98.75 |
| REGION | 741 | 100.00 | 100.00 | - |

Top failure causes (files affected, example ids):
1. count mismatch LINE: 6 files (09c59d9d55, 58fc17d402, d56be55fa4, 1f392128d6)
1. count mismatch POINT: 6 files (09c59d9d55, 58fc17d402, d56be55fa4, 1f392128d6)
1. count mismatch MTEXT: 6 files (09c59d9d55, 58fc17d402, d56be55fa4, 1f392128d6)
1. count mismatch INSERT: 5 files (09c59d9d55, d56be55fa4, 1f392128d6, bb19735538)
1. count mismatch LWPOLYLINE: 2 files (f05cf43e12, 58fc17d402)

## AC1027 (n=95 measured)

- files opened: 95/95 (100%)
- files with exact per-type entity counts: 90/95 (95%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 3877634/3877706 (100.00%)
- entities matched by handle+type: 3877581/3877706 (100.00%)
- header exact (all shared variables equal): 95/95 (100%); tables exact: 95/95 (100%); layouts exact: 95/95 (100%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 2280303 | 100.00 | 100.00 | 100.00 |
| ARC | 181105 | 100.00 | 100.00 | 100.00 |
| CIRCLE | 13730 | 100.00 | 100.00 | 100.00 |
| LWPOLYLINE | 704278 | 100.00 | 100.00 | 100.00 |
| POLYLINE | 29283 | 100.00 | 100.00 | - |
| INSERT | 171047 | 99.99 | 99.99 | 100.00 |
| TEXT | 13285 | 100.00 | 99.97 | 99.97 |
| MTEXT | 69671 | 99.99 | 99.92 | 99.92 |
| HATCH | 136753 | 100.00 | 100.00 | 99.99 |
| DIMENSION | 11186 | 100.00 | 100.00 | 100.00 |
| SPLINE | 109813 | 100.00 | 100.00 | 100.00 |
| ELLIPSE | 67800 | 100.00 | 100.00 | 100.00 |
| VIEWPORT | 718 | 100.00 | 100.00 | 97.56 |
| 3DSOLID | 168 | 100.00 | 100.00 | - |
| REGION | 159 | 100.00 | 100.00 | - |

Top failure causes (files affected, example ids):
1. count mismatch LWPOLYLINE: 2 files (caa4142eb2, 746deae904)
1. count mismatch INSERT: 2 files (46894df5d1, f891a6135e)
1. count mismatch POINT: 2 files (46894df5d1, f891a6135e)
1. count mismatch LINE: 2 files (46894df5d1, f891a6135e)
1. count mismatch MTEXT: 2 files (46894df5d1, f891a6135e)

## AC1032 (n=93 measured)

- files opened: 93/93 (100%)
- files with exact per-type entity counts: 91/93 (98%)
- entities matched by count (sum min(ours,AutoCAD) / AutoCAD): 2599606/2600094 (99.98%)
- entities matched by handle+type: 2599044/2600094 (99.96%)
- header exact (all shared variables equal): 93/93 (100%); tables exact: 93/93 (100%); layouts exact: 93/93 (100%)

| type | AutoCAD n | count matched % | handle+type matched % (TEXT/MTEXT/ATTDEF: position+string) | geometry exact % (where checked) |
|---|---|---|---|---|
| LINE | 1784392 | 100.00 | 100.00 | 100.00 |
| ARC | 177797 | 100.00 | 100.00 | 100.00 |
| CIRCLE | 19056 | 100.00 | 100.00 | 100.00 |
| LWPOLYLINE | 116983 | 100.00 | 100.00 | 100.00 |
| POLYLINE | 4911 | 100.00 | 100.00 | - |
| INSERT | 110910 | 99.99 | 99.99 | 100.00 |
| TEXT | 9252 | 100.00 | 99.49 | 99.49 |
| MTEXT | 43223 | 99.79 | 99.72 | 99.72 |
| HATCH | 66510 | 100.00 | 100.00 | 100.00 |
| DIMENSION | 6146 | 100.00 | 100.00 | 99.95 |
| SPLINE | 61990 | 100.00 | 100.00 | 100.00 |
| ELLIPSE | 45030 | 100.00 | 100.00 | 100.00 |
| VIEWPORT | 547 | 100.00 | 100.00 | 98.53 |
| REGION | 6 | 100.00 | 100.00 | - |

Top failure causes (files affected, example ids):
1. count mismatch POINT: 2 files (6e984d14c0, b478330132)
1. count mismatch MTEXT: 2 files (6e984d14c0, b478330132)
1. count mismatch LINE: 2 files (6e984d14c0, b478330132)
1. count mismatch SOLID: 1 files (6e984d14c0)
1. count mismatch INSERT: 1 files (b478330132)


## Robustness census of the remaining sample files (no ground truth)

The 397 files of campaign21/sample.tsv that have no AutoCAD dump (files over 25 MB, up to 150 MB, and files not picked) were opened and fully decoded with campaign21/cov/openall.py on host2 (Model() plus every entity of every block; an exception or a timeout counts as a failure). Count correctness is not checked here, only that the parser opens the file and decodes it without error.

| version | files | opened and fully decoded | entities decoded |
|---|---|---|---|
| AC1014 | 1 | 1 | 353154 |
| AC1015 | 4 | 4 | 3330821 |
| AC1018 | 2 | 2 | 2988388 |
| AC1021 | 197 | 197 | 47271332 |
| AC1024 | 61 | 61 | 14011532 |
| AC1027 | 25 | 25 | 17787256 |
| AC1032 | 107 | 107 | 28429279 |

Total 397 of 397 (100%), slowest file 56 s. Together with the 551 compared files, 948 of the 949 sample files are covered; the remaining one is the file whose AutoCAD dump is not valid JSON and was not part of either run.
