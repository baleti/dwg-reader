#!/usr/bin/env python3
"""diff_clusters.py SIDE.png : largest clusters of 'only AutoCAD' (red) and 'only ours' (blue) ink in a vcompare side-by-side image, as fractions of the page: where to look first."""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage
im = Image.open(sys.argv[1]).convert('RGB'); W = (im.width - 20) // 3
d = np.asarray(im.crop((2 * W + 20, 0, 3 * W + 20, im.height)))
for name, m in (('only AutoCAD (red)', (d[:, :, 0] > 180) & (d[:, :, 1] < 60) & (d[:, :, 2] < 60)), ('only ours (blue)', (d[:, :, 2] > 180) & (d[:, :, 0] < 60) & (d[:, :, 1] < 60))):
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=12))
    if not n: print(name, 'none'); continue
    sizes = ndimage.sum(m, lab, range(1, n + 1)); objs = ndimage.find_objects(lab)
    print('%s: %d px in %d clusters' % (name, int(m.sum()), n))
    for i in np.argsort(sizes)[::-1][:6]:
        sl = objs[i]; print('   %6d px  x %.2f-%.2f  y %.2f-%.2f' % (sizes[i], sl[1].start / W, sl[1].stop / W, sl[0].start / im.height, sl[0].stop / im.height))
