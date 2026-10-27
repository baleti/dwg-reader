import sys, os, time, cProfile, pstats, io, json
sys.path.insert(0, os.path.expanduser('~/dwg-viewer'))
from dwgviewer import build
f = sys.argv[1]
t = time.time()
pr = cProfile.Profile(); pr.enable()
d = build.Doc(f); m = d.meta()
t1 = time.time()
tot = 0; n = 0
for l in m['layouts']:
    for tw in ((True, False) if not l['ps'] else (True,)):
        s = d.layout(l['i'], tw); tot += len(json.dumps(s)); n += 1
pr.disable()
print('FILE', os.path.basename(f), 'size', os.path.getsize(f), 'layouts', len(m['layouts']), 'scenes', n, 'meta %.2f total %.2f json %dKB' % (t1 - t, time.time() - t, tot // 1024))
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats(os.environ.get('SORT','tottime')).print_stats(int(os.environ.get('N','14'))); print('\n'.join(s.getvalue().splitlines()[6:60]))
