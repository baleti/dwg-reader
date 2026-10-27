"""Text and JSON summaries using the viewer's small Doc interface."""

import argparse
import json
import sys


def summarize(doc):
    """Summarize a drawing, preserving individual layout failures."""
    meta = doc.meta()
    layers = meta.get('layers', [])
    summary = {
        'file': meta.get('file', ''),
        'layers': {
            'total': len(layers),
            'off': sum(bool(layer.get('off', False)) for layer in layers),
            # The viewer currently spells this flag "frz".
            'frozen': sum(bool(layer.get('frozen', layer.get('frz', False)))
                          for layer in layers),
            'nonplot': sum(not layer.get('plot', True) for layer in layers),
        },
        'layouts': [],
        'default_layout': meta.get('default', 0),
    }
    for layout in meta.get('layouts', []):
        entry = {
            'i': layout['i'],
            'name': layout.get('name', ''),
            'paper_space': bool(layout.get('ps', False)),
        }
        summary['layouts'].append(entry)
        try:
            data = doc.layout(layout['i'])
        except Exception as exc:
            entry['error'] = str(exc)
            continue

        prims = data.get('prims', [])
        rows = dict.fromkeys(('l', 'h', 't', 'p'), 0)
        for row in prims:
            if row and row[0] in rows:
                rows[row[0]] += 1
        rows['total'] = len(prims)
        entry.update({
            'paper': data.get('paper'),
            'bounds': data.get('bounds', []),
            'rows': rows,
            'model_rows_in_viewports': len(data.get('mprims', [])),
            'viewports': [
                {'id': vp.get('id'), 'scale': vp.get('scale', 1.0),
                 'frozen_layers': len(vp.get('frozen', []))}
                for vp in data.get('vps', [])
            ],
        })
    return summary


def render_text(summary):
    """Render a summary as a human-readable multiline report."""
    layers = summary['layers']
    layouts = summary['layouts']
    lines = [
        f"{summary['file']}: {layers['total']} layers "
        f"({layers['off']} off, {layers['frozen']} frozen), {len(layouts)} layouts"
    ]
    for layout in layouts:
        line = f"  [{layout['i']}] {layout['name']}"
        if 'error' in layout:
            line += f" ERROR {layout['error']}"
        else:
            space = 'paper space' if layout['paper_space'] else 'model'
            rows = layout['rows']
            line += (
                f" ({space}) rows={rows['total']} l={rows['l']}"
                f" h={rows['h']} t={rows['t']} p={rows['p']}"
                f" viewports={len(layout['viewports'])}"
            )
        if layout['i'] == summary['default_layout']:
            line += ' *'
        lines.append(line)
        if 'error' not in layout:
            for vp in layout['viewports']:
                lines.append(
                    f"      viewport {vp['id']} scale={vp['scale']:.4g}"
                    f" frozen={vp['frozen_layers']}"
                )
    return '\n'.join(lines)


def main(argv=None):
    """Print a drawing summary; return 1 when the file cannot be opened."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', metavar='FILE.drw')
    parser.add_argument('--json', action='store_true', help='print JSON')
    args = parser.parse_args(argv)

    from . import build

    try:
        doc = build.Doc(args.file)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    summary = summarize(doc)
    print(json.dumps(summary, indent=1) if args.json else render_text(summary))
    return 0


if __name__ == '__main__':
    sys.exit(main())
