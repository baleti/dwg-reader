# dwg-reader

Read AutoCAD .dwg files (R12 to 2018+) without AutoCAD, in plain Python with an optional Rust fast path.

- Opens every DWG version from R12 (AC1009) to the current format (AC1032): container, compression, object map and entity decoders.
- Per-version coverage against AutoCAD's own dump is in COVERAGE-BY-VERSION.md and ACCURACY.md (aggregate numbers only).
- Not yet decoded: 3D solid geometry stored in the AcDs data store (2013+), table cell contents, and proprietary third-party object types.

## How it was built

Independent implementation. The format was worked out from public format descriptions (read, not copied) and by experiment, and every decoded value is checked against output of AutoCAD 2026 running in an offline virtual machine. No code, tables or constants from other DWG libraries (LibreDWG, Open Design Alliance, or others) are used. The test drawings are not redistributed.

Status: experimental.

## License

MIT, see [LICENSE](LICENSE). AutoCAD and DWG are trademarks of Autodesk, Inc. This project is independent and is not affiliated with, endorsed by or sponsored by Autodesk.
