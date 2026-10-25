# dwg-reader

Read AutoCAD .dwg files (R12 to 2018+) without AutoCAD, in plain Python with an optional Rust fast path.

- Opens every DWG version from R12 (AC1009) to the current format (AC1032): container, compression, object map and entity decoders.
- Per-version coverage against AutoCAD's own dump is in COVERAGE-BY-VERSION.md and ACCURACY.md (aggregate numbers only).
- Not yet decoded: 3D solid geometry stored in the AcDs data store (2013+), table cell contents, and proprietary third-party object types.

## Measured coverage

Every number is a comparison against AutoCAD 2026 (running in an offline virtual machine) on real drawings; per version, 17 to 95 randomly chosen files (551 in total, files over 25 MB excluded). Drawings and AutoCAD dumps are not redistributed. Details and per-version failure causes: [COVERAGE-BY-VERSION.md](COVERAGE-BY-VERSION.md), [ACCURACY.md](ACCURACY.md).

| Version | Files | Opened | Files with exact per-type entity counts | Entities matched (handle + type) | Header / tables / layouts exact |
|---|---|---|---|---|---|
| R12 (AC1009) | 17 | 17/17 | 100% | 100.00% (by count) | 94% / 100% / 100% |
| R13 (AC1012) | 28 | 28/28 | 100% | 100.00% | 96% / 100% / 100% |
| R14 (AC1014) | 46 | 46/46 | 100% | 100.00% | 100% / 96% / 93% |
| 2000 (AC1015) | 29 | 29/29 | 93% | 99.97% | 100% / 100% / 100% |
| 2004 (AC1018) | 53 | 53/53 | 98% | 100.00% | 100% / 100% / 100% |
| 2007 (AC1021) | 95 | 95/95 | 92% | 99.99% | 100% / 99% / 99% |
| 2010 (AC1024) | 95 | 95/95 | 93% | 99.99% | 100% / 100% / 100% |
| 2013 (AC1027) | 95 | 95/95 | 95% | 100.00% | 100% / 100% / 100% |
| 2018+ (AC1032) | 93 | 93/93 | 98% | 99.96% | 100% / 100% / 100% |

"Entities matched" counts the entities that AutoCAD lists in each file, matched by handle and type (TEXT, MTEXT, ATTDEF and VIEWPORT by position and string). R12 has no stored handles, so it is matched by count.

### Not decoded yet

- 3D solid and region geometry stored in the AcDs data store (2013 and later files).
- Table cell contents (ACAD_TABLE) and arc-dimension graphics.
- Proprietary third-party object types (for example CADSTEXT, CADS_VPM, KSW_*).
- A few percent of sampled files still differ from AutoCAD in the count of some entity types (extra or missing LINE, POINT, MTEXT, INSERT); some of these are AutoCAD behaviour (regenerated dimensions, dropped anonymous blocks) and some are parser gaps under investigation.

This is not a claim that every entity of every drawing is decoded.

## How it was built

Independent implementation. The format was worked out from public format descriptions (read, not copied) and by experiment, and every decoded value is checked against output of AutoCAD 2026 running in an offline virtual machine. No code, tables or constants from other DWG libraries (LibreDWG, Open Design Alliance, or others) are used. The test drawings are not redistributed.

Status: experimental.

## License

MIT, see [LICENSE](LICENSE). AutoCAD and DWG are trademarks of Autodesk, Inc. This project is independent and is not affiliated with, endorsed by or sponsored by Autodesk.
