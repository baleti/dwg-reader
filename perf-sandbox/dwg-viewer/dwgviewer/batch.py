"""Discover drawings and warm their scene caches with injectable workers."""

import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import os
import queue
import subprocess
import sys
import time


def find_drawings(paths, exts=('.dwg',)):
    """Return unique absolute drawing paths without traversing hidden directories."""
    extensions = tuple(ext.lower() for ext in exts)
    found = set()

    def keep(path):
        if os.path.isfile(path) and os.path.splitext(path)[1].lower() in extensions:
            found.add(os.path.abspath(path))

    for path in paths:
        path = os.path.abspath(path)
        if os.path.isfile(path):
            keep(path)
        elif os.path.isdir(path) and not os.path.islink(path):
            if os.path.basename(path).startswith('.'):
                continue
            for root, dirs, names in os.walk(path, followlinks=False):
                dirs[:] = [name for name in dirs if not name.startswith('.')
                           and not os.path.islink(os.path.join(root, name))]
                for name in names:
                    keep(os.path.join(root, name))
    return sorted(found)


def plan(files, is_cached, min_bytes=0, max_bytes=None):
    """Classify files, then order work by size and path."""
    sized = []
    skipped = []
    for path in files:
        if is_cached(path):
            skipped.append((path, 'cached'))
            continue
        try:
            size = os.path.getsize(path)
        except OSError:
            skipped.append((path, 'unreadable'))
            continue
        if size < min_bytes or (max_bytes is not None and size > max_bytes):
            skipped.append((path, 'size'))
        else:
            sized.append((size, path))
    return [path for size, path in sorted(sized)], skipped


def run(todo, worker, jobs=1, timeout=None, on_result=None):
    """Run workers concurrently; deliver callbacks on the calling thread.

    Timeouts start when each worker starts, excluding time queued for a slot.
    Python threads cannot be killed: timed-out workers finish during shutdown.
    """
    todo = list(todo)
    results = [None] * len(todo)
    events = queue.Queue()
    running = {}

    def invoke(index, path):
        start = time.monotonic()
        events.put(('start', index, start))
        try:
            return worker(path)
        finally:
            events.put(('finish', index, time.monotonic()))

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
        futures = [executor.submit(invoke, i, path) for i, path in enumerate(todo)]
        remaining = len(todo)
        while remaining:
            wait = None
            if timeout is not None and running:
                wait = max(0.0, min(running.values()) + timeout - time.monotonic())
            try:
                event, index, stamp = events.get(timeout=wait)
            except queue.Empty:
                index = min(running, key=running.get)
                event, stamp = 'timeout', time.monotonic()
            if results[index] is not None:
                continue
            if event == 'start':
                running[index] = stamp
                continue
            start = running.pop(index)
            result = {'path': todo[index], 'seconds': float(stamp - start)}
            try:
                # A finish event is emitted just before the future becomes ready.
                value = futures[index].result(timeout=0 if event == 'timeout' else None)
            except TimeoutError as exc:
                if event == 'timeout' and not futures[index].done():
                    result.update(ok=False, error='timeout')
                else:
                    result.update(ok=False, error=f'{type(exc).__name__}: {exc}')
            except Exception as exc:
                result.update(ok=False, error=f'{type(exc).__name__}: {exc}')
            else:
                if timeout is not None and stamp - start > timeout:
                    result.update(ok=False, error='timeout')
                else:
                    result.update(ok=True, result=value)
            results[index] = result
            remaining -= 1
            if on_result is not None:
                on_result(result)
    return results


def summary(results):
    """Format batch counts, accumulated durations, and failures."""
    results = list(results)
    failures = [result for result in results if not result['ok']]
    seconds = sum(result['seconds'] for result in results)
    lines = [f'{len(results) - len(failures)} ok, {len(failures)} failed, {seconds:.1f} s']
    for result in sorted(failures, key=lambda r: os.path.basename(r['path'])):
        lines.append(f"  FAIL {os.path.basename(result['path'])}: {result['error']}")
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--min-mb', type=float, default=0)
    parser.add_argument('--max-mb', type=float)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)

    from . import cache

    def is_cached(path):
        try:
            meta = cache.read_meta(path)
            return bool(meta) and all(
                os.path.isfile(cache.layout_path(path, layout['i'], True))
                for layout in meta['layouts'])
        except OSError:
            return False

    todo, skipped = plan(
        find_drawings(args.paths), is_cached,
        min_bytes=args.min_mb * 1024 ** 2,
        max_bytes=None if args.max_mb is None else args.max_mb * 1024 ** 2)
    if args.dry_run:
        for path in todo:
            print(f'TODO {path}')
        for path, reason in skipped:
            print(f'SKIP {path}: {reason}')
        return

    def worker(path):
        completed = subprocess.run(
            [sys.executable, '-m', 'dwgviewer', path, '--prepare'],
            check=True, capture_output=True, text=True)
        return {'stdout': completed.stdout, 'stderr': completed.stderr}

    count = 0

    def progress(result):
        nonlocal count
        count += 1
        status = 'ok' if result['ok'] else 'FAIL'
        print(f"[{count}/{len(todo)}] {os.path.basename(result['path'])} {status}", flush=True)

    print(summary(run(todo, worker, jobs=args.jobs, on_result=progress)))


if __name__ == '__main__':
    main()
