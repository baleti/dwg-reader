#!/usr/bin/env python3
"""vqa.py [--max-layouts N] [--out DIR] STEM... : fidelity QA of every layout of each drawing against the AutoCAD 'fixed' plots in oracle-out/<stem>/plots.
Runs tools/vcompare.py per layout in a subprocess (timeout, memory cap); appends one JSON line per layout to DIR/vqa.jsonl (resumable). Local use only."""
import sys, os, json, subprocess, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
ORA = os.path.expanduser('~/dwg-research/oracle-out')
ap = argparse.ArgumentParser()
ap.add_argument('stems', nargs='+'); ap.add_argument('--out', default=os.path.expanduser('~/dwg-research/qa/out'))
ap.add_argument('--src', default=os.path.expanduser('~/dwg-edit-tests/src')); ap.add_argument('--max-layouts', type=int, default=8)
ap.add_argument('--redo', action='store_true', help='rescore even when a record exists (aggregation keeps the newest per view)')
ap.add_argument('--layouts', default='')
ap.add_argument('--kind', default='fixed', help='fixed (A3 extents, whole content) or native (the layout\'s own page setup; compared with ours framed on the paper)')
ap.add_argument('--timeout', type=int, default=300); ap.add_argument('--caps', default='1')
a = ap.parse_args()
os.makedirs(os.path.join(a.out, a.kind), exist_ok=True)
log = os.path.join(a.out, 'vqa.jsonl' if a.kind == 'fixed' else 'vqa_%s.jsonl' % a.kind)
done = set()
if os.path.exists(log) and not a.redo:
    for l in open(log):
        try: r = json.loads(l); done.add((r['stem'], r['li']))
        except Exception: pass
for stem in a.stems:
    try: d = json.load(open(os.path.join(ORA, stem, 'dump.json')))
    except Exception as ex:
        print(stem, 'no dump', ex); continue
    n = min(len(d.get('layouts', [])), a.max_layouts)
    for li in ([int(x) for x in a.layouts.split(',')] if a.layouts else range(n)):
        if (stem, li) in done: continue
        cmd = [sys.executable, os.path.join(HERE, 'vcompare.py'), os.path.join(a.src, stem + '.dwg'), str(li), '--out', os.path.join(a.out, a.kind), '--kind', a.kind]
        if a.caps == '1': cmd = ['systemd-run', '--user', '--scope', '-q', '-p', 'MemoryMax=3G', '-p', 'MemorySwapMax=0', '-p', 'CPUQuota=300%', 'nice', '-n', '19'] + cmd
        env = dict(os.environ, **({'VC_FIT': 'bounds'} if a.kind == 'native' else {}))
        rec = dict(stem=stem, li=li, version=stem[:6])
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout, env=env)
            lines = [l for l in p.stdout.splitlines() if l.startswith('{')]
            if lines: rec.update(json.loads(lines[-1]))
            else: rec['err'] = (p.stderr or p.stdout).strip().splitlines()[-1][:160] if (p.stderr or p.stdout).strip() else 'rc%d' % p.returncode
        except subprocess.TimeoutExpired: rec['err'] = 'timeout'
        rec['model'] = (li == 0)
        open(log, 'a').write(json.dumps(rec) + '\n')
        print(stem, li, rec.get('p5a', rec.get('err')), rec.get('r5a'), flush=True)
