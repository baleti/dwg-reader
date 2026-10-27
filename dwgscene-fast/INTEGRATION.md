# Integration plan (apply after ~/demo-state/RENAME-DONE; owner of the viewer repo edits is c8-perf then)
1. Build: dwgscene-fast/build.sh (host2/host1), copy dwgscene_fast.abi3.so next to dwgfast.abi3.so in the viewer repo (git-ignored, like dwgfast). Without it everything runs in pure Python.
2. Copy fastflat.py into dwgviewer/ (as `fastflat.py`, import `from . import fastflat`); at the end of dwgviewer/flat.py:
       try:
           if not os.environ.get('DWG_NO_FAST'): from . import fastflat; fastflat.install(sys.modules[__name__])
       except Exception: pass
   (fastflat.install patches Flattener.flatten, adds Flattener._one, and replaces build._round with the Rust round_list).
3. Tests: dwgscene-fast/tests/parity.py (kernels) and prof/fast.py FILE (scene JSON parity per layout, stock vs fast) over the corpus; run before committing. Demo smoke test (--no-browser, curl main page and /sheets/) per the demo-ready rule.
4. Progressive open + parallel layouts: server.py/cli --prepare build the default layout first (cache.write_layout), other layouts in os.fork children (prof/par.py shows the pattern; 'tl' dict key order differs only).
5. Cross-platform: os.fork is POSIX-only; use concurrent.futures.ProcessPoolExecutor with spawn on Windows/macOS (Doc must then be rebuilt per worker: parse is 0.4 s) and build the abi3 .so/.pyd per platform with maturin.
Known parity notes: Rust hypot vs CPython hypot differ by 1 ulp in LWPOLYLINE bulge arcs (<1e-9 before rounding to 3 decimals).
6. Native Bits: in dwgviewer/build.py (where fastbits is applied) add try: import dwgscene_fast, dwgbits; dwgbits.Bits = dwgscene_fast.Bits  (skip fastbits.apply then). tests/bits_parity.py + prof/r14cmp.py over AC1009/12/14/15 corpus.
