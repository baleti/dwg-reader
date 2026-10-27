import sys, os, time, resource
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
t = time.time()
doc = build.Doc(sys.argv[1]); print('parse', round(time.time() - t, 1), 's rss', rss(), 'MB', 'layouts', len(doc.lays), flush=True)
for i in range(len(doc.lays)):
    t = time.time(); r = doc.layout(i); print(i, doc.lays[i]['name'], r['n'], round(time.time() - t, 1), 's rss', rss(), 'MB', flush=True)
