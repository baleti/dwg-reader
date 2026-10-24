"""fuzz_edit.py [seed] [maxsize]: VM-free robustness fuzz of the editor on the local corpus (AC1015..AC1032, files < maxsize bytes): random set_props / transform /
copy_entity / erase / add_* on random model-space entities, save, re-open, compare entity count with the expected one. Prints failures only plus a summary."""
import os, sys, random, traceback
import dwgdoc, dwgxform as X

CORPUS = os.path.expanduser('~/dwg-research/corpus/')
SUPPORTED = ('AC1015', 'AC1018', 'AC1024', 'AC1027', 'AC1032')


def one(path, rng, save_to=None):
    doc = dwgdoc.Doc(open(path, 'rb').read())
    ls = list(doc.entities('*Model_Space')); want = len(ls); log = []
    for _ in range(rng.randint(3, 12)):
        op = rng.choice(['props', 'move', 'copy', 'erase', 'line', 'text', 'rot'])
        try:
            if op == 'line': doc.add_line((rng.random() * 100, 0), (100, rng.random() * 100)); want += 1
            elif op == 'text': doc.add_text((0, 0), 'fz%d' % rng.randint(0, 99), 2.5); want += 1
            elif not ls: continue
            else:
                h = rng.choice(ls)
                if op == 'props': doc.set_props(h, color=rng.randint(1, 255))
                elif op == 'move': doc.transform(h, X.Transform.translate(rng.random() * 10, rng.random() * 10))
                elif op == 'rot': doc.transform(h, X.Transform.rotate((0, 0), rng.random()))
                elif op == 'copy': doc.copy_entity(h, X.Transform.translate(5, 5)); want += 1
                elif op == 'erase': doc.erase(h); ls.remove(h); want -= 1
            log.append(op)
        except NotImplementedError:
            log.append(op + '!NI')
    data = doc.save()
    if save_to: open(save_to, 'wb').write(data)
    got = len(dwgdoc.Doc(data).entities('*Model_Space'))
    return want, got, log


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    mx = int(sys.argv[2]) if len(sys.argv) > 2 else 1500000
    rng = random.Random(seed); n = bad = 0
    for f in sorted(os.listdir(CORPUS)):
        if f[:6] not in SUPPORTED or os.path.getsize(CORPUS + f) > mx: continue
        n += 1
        try:
            want, got, log = one(CORPUS + f, rng)
            if want != got: bad += 1; print('MISMATCH', f, want, got, log)
        except Exception:
            bad += 1; print('EXC', f); traceback.print_exc(limit=3)
    print('files', n, 'bad', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
