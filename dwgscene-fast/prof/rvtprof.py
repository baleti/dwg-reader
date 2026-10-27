import sys, os, cProfile, pstats, io, time
sys.path.insert(0, os.path.expanduser('~/src/rvt-ballet'))
from rvtballet import cli
f = sys.argv[1]; out = '/tmp/rvtprof_out.glb'
pr = cProfile.Profile(); t = time.time(); pr.enable()
cli.main(['convert', f, out])
pr.disable()
print('FILE', os.path.basename(f), 'total %.1f' % (time.time() - t))
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats('cumulative').print_stats(35); print(s.getvalue()[:6000])
