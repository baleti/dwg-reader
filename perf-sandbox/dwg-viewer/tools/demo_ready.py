#!/usr/bin/env python3
"""demo_ready.py FILE.dwg... : pre-demo check. Warms the cache (--prepare), runs the headless server smoke test on every file and prints the exact demo command per file."""
import sys, os, subprocess
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = True
for f in sys.argv[1:]:
    f = os.path.abspath(f)
    r1 = subprocess.run([sys.executable, '-m', 'dwgviewer', '--prepare', f], cwd=HERE, capture_output=True, text=True)
    r2 = subprocess.run([sys.executable, os.path.join(HERE, 'tools', 'smoke.py'), f], cwd=HERE, capture_output=True, text=True)
    good = r1.returncode == 0 and r2.returncode == 0 and 'SMOKE OK' in r2.stdout
    ok &= good
    print(('READY  ' if good else 'FAILED ') + os.path.join(HERE, 'bin', 'dwg-viewer') + ' ' + f)
    if not good: print((r1.stderr + r2.stderr + r2.stdout)[-400:])
sys.exit(0 if ok else 1)
