from xml.sax.saxutils import escape as _esc

FONT = 'Helvetica, Arial, sans-serif'
MONO = 'DejaVu Sans Mono, Menlo, Consolas, monospace'

# colour families: (fill, stroke, title colour)
C = {
    'blue':   ('#e8f0fe', '#4a6fd1', '#1d3b8a'),
    'green':  ('#e6f6ea', '#2e9a4b', '#1c5e2e'),
    'yellow': ('#fff4e0', '#d48a00', '#7a4d00'),
    'orange': ('#fde8e8', '#d14a4a', '#7a1d1d'),
    'purple': ('#f3e8fd', '#8a4ad1', '#4b1d7a'),
    'grey':   ('#f2f2f2', '#888888', '#333333'),
    'teal':   ('#e0f5f5', '#2a9d9d', '#145a5a'),
}

def esc(s):
    return _esc(s)

class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.parts = w, h, []
        self.parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
                          f'font-family="{FONT}" font-size="14">')
        self.parts.append(f'  <title>{esc(title)}</title>')
        self.parts.append('  <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" '
                          'markerWidth="8" markerHeight="8" orient="auto">'
                          '<path d="M0,0 L10,5 L0,10 z" fill="#555"/></marker></defs>')
        self.parts.append(f'  <rect width="{w}" height="{h}" fill="#ffffff"/>')

    def raw(self, s):
        self.parts.append('  ' + s)

    def text(self, x, y, s, size=14, weight='normal', fill='#333', anchor='start', mono=False, italic=False):
        fam = f' font-family="{MONO}"' if mono else ''
        st = ' font-style="italic"' if italic else ''
        self.raw(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
                 f'text-anchor="{anchor}"{fam}{st} xml:space="preserve">{esc(s)}</text>')

    def rich(self, x, y, runs, size=13, anchor='start'):
        """runs: list of (text, mono:bool, bold:bool)"""
        spans = []
        for t, mono, bold in runs:
            a = f' font-family="{MONO}"' if mono else ''
            b = ' font-weight="bold"' if bold else ''
            spans.append(f'<tspan{a}{b}>{esc(t)}</tspan>')
        self.raw(f'<text x="{x}" y="{y}" font-size="{size}" fill="#333" text-anchor="{anchor}" xml:space="preserve">{"".join(spans)}</text>')

    def box(self, x, y, w, h, colour, title=None, lines=(), title_size=15, line_size=12.5,
            mono_lines=False, rx=10, dash=False, line_gap=17, title_mono=False, center=False):
        f, s, t = C[colour]
        d = ' stroke-dasharray="6,4"' if dash else ''
        self.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{f}" stroke="{s}" stroke-width="2"{d}/>')
        cy = y + 22
        ax = x + w / 2 if center else x + 12
        anchor = 'middle' if center else 'start'
        if title:
            self.text(ax, cy, title, size=title_size, weight='bold', fill=t, anchor=anchor, mono=title_mono)
            cy += line_gap + 3
        for ln in lines:
            if isinstance(ln, tuple):
                self.rich(ax, cy, ln if isinstance(ln[0], tuple) else [ln], size=line_size, anchor=anchor)
            else:
                self.text(ax, cy, ln, size=line_size, mono=mono_lines, anchor=anchor)
            cy += line_gap
        return cy

    def arrow(self, x1, y1, x2, y2, label=None, colour='#555', dash=False, lx=None, ly=None, lsize=12):
        d = ' stroke-dasharray="6,4"' if dash else ''
        self.raw(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{colour}" stroke-width="2" marker-end="url(#arr)"{d}/>')
        if label:
            self.text(lx if lx is not None else (x1 + x2) / 2 + 6, ly if ly is not None else (y1 + y2) / 2,
                      label, size=lsize, fill='#555')

    def line(self, x1, y1, x2, y2, colour='#999', width=2, dash=False):
        d = ' stroke-dasharray="6,4"' if dash else ''
        self.raw(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{colour}" stroke-width="{width}"{d}/>')

    def save(self, path):
        self.parts.append('</svg>')
        with open(path, 'w') as fh:
            fh.write('\n'.join(self.parts) + '\n')
        # add the "Words on this sheet" strip, if glossary.py has one for this file
        import glossary
        glossary.apply(path)
