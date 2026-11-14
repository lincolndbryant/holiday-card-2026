#!/usr/bin/env python3
"""Penrose Snowflake laser-cut card generator.

A five-fold snowflake filled with a Penrose P3 (rhombus) tiling, hung in a round
window on a card front and attached to the card at its five arm tips.

Usage:
    python3 generate.py            # build every preset into out/
    python3 generate.py bold       # build one preset
    python3 generate.py --preview  # also write PNG previews (needs playwright)

Requires: shapely  (pip install shapely)
All units are millimetres.
"""
import cmath
import math
import sys
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

PHI = (1 + 5 ** 0.5) / 2
OUT = Path(__file__).parent / "out"

# ---------------------------------------------------------------- presets ---
# card:     card width/height and the snowflake centre
# tiling:   sun radius L and deflation count N -> rhombus edge = L / PHI**N
# strut:    paper left between neighbouring holes
# border:   solid rim kept inside the snowflake outline
# min_feat: holes thinner than this are left solid (avoid scorching)
# window_close: gaps in the snowflake outline narrower than 2x this (between leaves/stems) are filled with paper;
#           window_halo: extra paper grown around the whole edge (mm);
#           min_window: open gaps narrower than this are filled
# stem_taper: stem width at its leaf end / at its root;  ring_margin: leaves stay this far inside the window edge
# min_gap:  nearest any two holes may come (default 1.0 mm); the smaller hole is trimmed back
# min_bridge: any paper joined to the rest by a neck narrower than this gets the
#           neighbouring holes filled in (default 1.0 mm)
# arm/hub/branch sizes shape the silhouette
PAPER = "#1f3b57"     # cardstock colour (preview only; the cut files carry no colour)
BACKDROP = "#f4f1ea"  # what you see through the holes in the preview (window, wall, envelope)

TIP_STYLE = "leaf"   # rhombus | leaf | flame
CURL = 0.28           # sideways bend of each leaf (0 = symmetric)

PRESETS = {
    "fine": dict(
        card=(127.0, 177.8), center=(63.5, 82.0), ring=54,
        L=104.0, N=7, strut=1.0, border=1.3, min_feat=0.9, tip_inset=1.3, tip_gap=1.0,
        hub=19.5, arm=10, minor_len=31.5, minor_w=6.5, minor_tip=9,
        branches=((29, 15, 4.8, 7.2), (37.5, 7, 4.3, 5.5)),
        twig_w=4, twig_tip=5,
        fill=PAPER, preview_bg=BACKDROP, tip_style=TIP_STYLE, window_close=1.5, window_halo=0.0, min_window=2.0, stem_taper=0.62, ring_margin=3.0,
    ),
    "bold": dict(
        card=(127.0, 177.8), center=(63.5, 82.0), ring=54,
        L=88.0, N=6, strut=1.6, border=1.9, min_feat=1.2, tip_inset=1.8, tip_gap=1.6,
        hub=20, arm=12, minor_len=31.5, minor_w=7.5, minor_tip=10,
        branches=((29, 15, 6, 8), (38.5, 7, 5.5, 6.5)),
        twig_w=5, twig_tip=6,
        fill=PAPER, preview_bg=BACKDROP, tip_style=TIP_STYLE, window_close=1.5, window_halo=0.0, min_window=2.0, stem_taper=0.62, ring_margin=3.0,
    ),
}


# ---------------------------------------------------------------- tiling ----
def penrose_rhombi(L, N):
    """Robinson-triangle deflation from a 10-triangle 'sun'; returns (kind, [4 pts])
    where kind 1 = thick (72 deg) rhombus, 0 = thin (36 deg)."""
    tris = []
    for i in range(10):
        B = cmath.rect(L, (2 * i - 1) * math.pi / 10)
        C = cmath.rect(L, (2 * i + 1) * math.pi / 10)
        if i % 2 == 0:
            B, C = C, B
        tris.append((0, 0j, B, C))
    for _ in range(N):
        nxt = []
        for c, A, B, C in tris:
            if c == 0:
                P = A + (B - A) / PHI
                nxt += [(0, C, P, B), (1, P, C, A)]
            else:
                Q = B + (A - B) / PHI
                R = B + (C - B) / PHI
                nxt += [(1, R, C, A), (1, Q, R, B), (0, R, Q, A)]
        tris = nxt
    key = lambda z: (round(z.real, 4), round(z.imag, 4))
    pairs = {}
    for c, A, B, C in tris:
        pairs.setdefault((c,) + tuple(sorted([key(B), key(C)])), []).append((A, B, C))
    return [(k[0], [v[0][0], v[0][1], v[1][0], v[0][2]]) for k, v in pairs.items() if len(v) == 2]


def inset(poly, d):
    """Shrink a convex polygon by d on every side."""
    out = []
    n = len(poly)
    for i in range(n):
        p = poly[i]
        a = poly[i - 1] - p
        b = poly[(i + 1) % n] - p
        a /= abs(a)
        b /= abs(b)
        ang = math.acos(max(-1, min(1, (a * b.conjugate()).real)))
        out.append(p + (a + b) / abs(a + b) * d / math.sin(ang / 2))
    return out


# ------------------------------------------------------------- silhouette ---
def xy(z):
    return (z.real, z.imag)


def tip(base, th, e, style="rhombus", curl=0.0):
    """Branch-end cap pointing along th, narrow end at base. Same length/width as a thick
    Penrose rhombus of edge e. style: rhombus | leaf (symmetric, pointed) |
    flame (round belly low, tapering to a point; curl bends the point sideways)."""
    u = cmath.rect(1, th)
    a = e * math.cos(math.radians(36))
    b = e * math.sin(math.radians(36))
    if style == "rhombus":
        return Polygon([xy(p) for p in (base, base + u * a + u * 1j * b, base + u * 2 * a, base + u * a - u * 1j * b)])
    k, ex = (0.9, 0.9) if style == "leaf" else (0.62, 0.9)
    n = 28
    length, half = 2 * a, b
    side = []
    for i in range(n + 1):
        t = i / n
        hw = half * math.sin(math.pi * t ** k) ** ex
        c = curl * half * 1.4 * t ** 2.2
        side.append((t * length, c, hw))
    pts = [base + u * x + u * 1j * (c + w) for x, c, w in side]
    pts += [base + u * x + u * 1j * (c - w) for x, c, w in reversed(side[1:-1])]
    return Polygon([xy(p) for p in pts])


def bar(a, b, w):
    return LineString([xy(a), xy(b)]).buffer(w / 2, cap_style=2)


def tbar(a, b, w0, w1):
    """Straight stem that narrows from width w0 at a to w1 at b."""
    d = (b - a) / abs(b - a)
    n = d * 1j
    return Polygon([xy(q) for q in (a + n * w0 / 2, b + n * w1 / 2, b - n * w1 / 2, a - n * w0 / 2)])


def snowflake(p):
    parts = [Polygon([xy(cmath.rect(p["hub"], math.pi / 2 + k * math.pi / 5)) for k in range(10)])]
    tips = []
    for k in range(5):
        th = -math.pi / 2 + k * 2 * math.pi / 5  # first arm points up
        u = cmath.rect(1, th)
        parts.append(bar(0, u * (p["ring"] + 4), p["arm"]))  # reaches into the card = tab
        for f, ln, w, e in p["branches"]:
            base = u * f
            for s in (1, -1):
                t2 = th + s * math.pi / 5  # side branches at +/-36 deg
                v = cmath.rect(1, t2)
                # shrink this branch until its leaf sits ring_margin inside the window edge
                sc = 1.0
                while sc > 0.45:
                    l2, e2 = ln * sc, e * sc
                    cand = tip(base + v * (l2 - e2 * 0.5), t2, e2, p["tip_style"], CURL * s)
                    if max(abs(complex(*c)) for c in cand.exterior.coords) <= p["ring"] - p["ring_margin"]:
                        break
                    sc -= 0.02
                l2, e2 = ln * sc, e * sc
                parts.append(tbar(base, base + v * l2, w, w * p["stem_taper"]))
                tips.append(tip(base + v * (l2 - e2 * 0.5), t2, e2, p["tip_style"], CURL * s))
        th2 = th + math.pi / 5  # minor arm between main arms
        v = cmath.rect(1, th2)
        parts.append(tbar(0, v * p["minor_len"], p["minor_w"], p["minor_w"] * p["stem_taper"]))
        tips.append(tip(v * (p["minor_len"] - 5), th2, p["minor_tip"], p["tip_style"], 0))
        for s in (1, -1):
            t3 = th2 + s * math.pi / 5
            base = v * (p["hub"] + 4.5)
            parts.append(bar(base, base + cmath.rect(6, t3), p["twig_w"]))
            tips.append(tip(base + cmath.rect(4.5, t3), t3, p["twig_tip"], p["tip_style"], CURL * s))
    return unary_union(parts + tips), tips


# ------------------------------------------------------------------- text ----
FONT = Path(__file__).parent / "fonts" / "Bungee-Regular.ttf"

# (text, width of the line in mm, top y in mm) -- laid out under the round window
TEXT_LINES = (
    ("HAPPY HOLIDAYS", 98.0, 147.0),
    ("LB | KC - 2026", 58.0, None),   # None: sits below the previous line
)
TEXT_LINE_GAP = 8.0      # mm between lines
TEXT_TRACKING = 0.7      # extra mm between letters
ENGRAVE = "#8a8a8a"      # engraving fill colour (grey) in the SVGs and previews


def _glyph_polygons(font, name, flat=14):
    """Outline of one glyph as a shapely geometry in font units (y up)."""
    from fontTools.pens.basePen import BasePen

    class Flat(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.contours, self.cur = [], []

        def _moveTo(self, pt):
            self.cur = [pt]

        def _lineTo(self, pt):
            self.cur.append(pt)

        def _curveToOne(self, p1, p2, p3):
            p0 = self.cur[-1]
            for i in range(1, flat + 1):
                t = i / flat
                a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
                self.cur.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                                 a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))

        def _closePath(self):
            if len(self.cur) > 2:
                self.contours.append(self.cur)
            self.cur = []

    gs = font.getGlyphSet()
    pen = Flat(gs)
    gs[name].draw(pen)
    geom = Polygon()
    for c in pen.contours:  # even-odd: nested contours are counters
        geom = geom.symmetric_difference(Polygon(c).buffer(0))
    return geom, gs[name].width


def text_engraving(card_w):
    """Engraved lettering as polygons (counters are interior rings), centred on the card,
    one entry of TEXT_LINES per line. Engraved, not cut, so nothing can fall out."""
    from fontTools.ttLib import TTFont
    font = TTFont(str(FONT))
    cmap = font.getBestCmap()
    res, top = [], None
    for text, width, y_top in TEXT_LINES:
        glyphs = [_glyph_polygons(font, cmap[ord(ch)]) for ch in text]
        # glyph advance in font units; scale k (mm per unit) chosen so the inked line is `width` mm wide
        units = sum(adv for _, adv in glyphs)
        ink_units = units - glyphs[0][0].bounds[0] - (glyphs[-1][1] - glyphs[-1][0].bounds[2])
        k = (width - TEXT_TRACKING * (len(text) - 1)) / ink_units
        x, line = 0.0, []
        for g, adv in glyphs:
            if not g.is_empty:
                g = affinity.scale(g, k, -k, origin=(0, 0))      # font y-up -> svg y-down
                line.append(affinity.translate(g, x, 0))
            x += adv * k + TEXT_TRACKING
        b = unary_union(line).bounds
        top = y_top if y_top is not None else top + TEXT_LINE_GAP
        dx, dy = (card_w - (b[2] - b[0])) / 2 - b[0], top - b[1]
        for g in line:
            g = affinity.translate(g, dx, dy)
            res += [q for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and q.area > 0.05]
        top += b[3] - b[1]
    return res


# ------------------------------------------------------------------ build ---
def enforce_gap(holes, p):
    """Trim the smaller of any two holes that come closer than min_gap (minus a hair of
    tolerance, so intentionally min_gap-wide struts are left alone)."""
    from shapely.strtree import STRtree
    gap = p.get("min_gap", 1.0)
    holes = sorted(holes, key=lambda h: -h.area)
    for i in range(len(holes)):  # big first: bigger holes keep their shape
        tree = STRtree(holes)
        for j in tree.query(holes[i].buffer(gap)):
            if j <= i or holes[i].distance(holes[j]) >= gap - 0.01:
                continue
            g2 = holes[j].difference(holes[i].buffer(gap, join_style=1))
            parts = [q for q in getattr(g2, "geoms", [g2]) if q.geom_type == "Polygon"]
            parts = [q for q in parts if q.area >= 2.0 and not q.buffer(-p["min_feat"] / 2).is_empty]
            holes[j] = max(parts, key=lambda q: q.area) if parts else Polygon()
    return [h for h in holes if not h.is_empty]


def window_region(ring, flake, p):
    """The round window's open area: the ring minus the snowflake grown by window_halo.
    Gaps narrower than min_window become paper again (no thin slivers of void)."""
    c = p.get("window_close", 0.0)
    closed = flake.buffer(c, join_style=1).buffer(-c, join_style=1) if c else flake  # fills gaps < 2c wide
    w = ring.difference(closed.buffer(p.get("window_halo", 0.0), join_style=1))
    r = p.get("min_window", 2.0) / 2
    w = w.buffer(-r, join_style=1).buffer(r, join_style=1)
    return [q for q in getattr(w, "geoms", [w]) if q.area > 15]  # tiny slivers stay solid


def widen_bridges(holes, ring, flake, p, max_iter=20):
    """Fill holes beside any neck narrower than p['min_bridge'] so no paper hangs by a thread.
    Works in the snowflake's own frame (centre at the origin)."""
    wb = p.get("min_bridge", 1.0)
    r = wb / 2 - 0.01  # tolerance: strips exactly wb wide must not count as broken
    window = unary_union(window_region(ring, flake, p))
    box = Point(0, 0).buffer(p["ring"] + 8)
    for _ in range(max_iter):
        solid = box.difference(unary_union(holes + [window]))
        eroded = solid.buffer(-r, join_style=2)
        parts = sorted(getattr(eroded, "geoms", [eroded]), key=lambda s: -s.area)
        if len(parts) < 2:
            break
        main = parts[0].buffer(r + 0.01, join_style=2)
        necks = unary_union([s.buffer(r + 0.01, join_style=2).intersection(main) for s in parts[1:]])
        fill = necks.buffer(0.3)
        keep = [h for h in holes if not h.intersects(fill)]
        if len(keep) == len(holes):
            break
        holes = keep
    return holes


def build(p):
    flake, tips = snowflake(p)
    ring = Point(0, 0).buffer(p["ring"], resolution=128)
    tipu = unary_union(tips)
    lace_area = flake.intersection(ring).difference(tipu.buffer(p["tip_gap"], join_style=1))
    lace_area = lace_area.buffer(-p["border"], join_style=2)

    holes = []
    for _, poly in penrose_rhombi(p["L"], p["N"]):
        hp = Polygon([xy(z) for z in inset(poly, p["strut"] / 2)])
        if not hp.intersects(lace_area):
            continue
        g = hp.intersection(lace_area)
        for h in getattr(g, "geoms", [g]):
            # keep only whole rhombi that are wide enough to cut cleanly
            if h.geom_type != "Polygon" or h.area < 0.98 * hp.area or h.area < 2.0:
                continue
            if h.buffer(-p["min_feat"] / 2).is_empty:
                continue
            holes.append(h.simplify(0.01))
    holes += [t.buffer(-p["tip_inset"], join_style=1) for t in tips]

    holes = enforce_gap(holes, p)
    holes = widen_bridges(holes, ring, flake, p)

    windows = window_region(ring, flake, p)

    cx, cy = p["center"]
    move = lambda g: affinity.translate(g, cx, cy)
    return [move(h) for h in holes], [move(w) for w in windows]


def d_attr(polys):
    s = []
    for g in polys:
        pts = list(g.exterior.coords)[:-1]
        s.append("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + "Z")
    return "".join(s)


def d_rings(polys):
    """Path data for polygons including their interior rings (use with fill-rule evenodd)."""
    s = []
    for g in polys:
        for ring in [g.exterior, *g.interiors]:
            pts = list(ring.coords)[:-1]
            s.append("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + "Z")
    return "".join(s)


def write_svgs(name, p):
    W, H = p["card"]
    holes, windows = build(p)
    hd, wd = d_attr(holes), d_attr(windows)
    ed = d_rings(text_engraving(W)) if TEXT_LINES else ""
    eng = f'<path id="engraving" fill="{ENGRAVE}" fill-rule="evenodd" stroke="none" d="{ed}"/>' if ed else ""
    size = f'width="{W:g}mm" height="{H:g}mm" viewBox="0 0 {W:g} {H:g}"'
    OUT.mkdir(exist_ok=True)

    cut = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Penrose Snowflake ({name}) - {W:g} x {H:g} mm. Grey fill = engrave (first), Red = inner cuts, Blue = outline (cut last). -->
<svg xmlns="http://www.w3.org/2000/svg" {size}>
  <g id="engrave">{eng}</g>
  <g id="inner-cuts" fill="none" stroke="#FF0000" stroke-width="0.0254">
    <path id="lace" d="{hd}"/>
    <path id="window" d="{wd}"/>
  </g>
  <g id="outer-cut" fill="none" stroke="#0000FF" stroke-width="0.0254">
    <rect x="0" y="0" width="{W:g}" height="{H:g}"/>
  </g>
</svg>
'''
    filled = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Penrose Snowflake ({name}) - {W:g} x {H:g} mm. Filled card shape; transparent holes are cut-outs (set that path to cut). The grey path is the engraving (set it to engrave). -->
<svg xmlns="http://www.w3.org/2000/svg" {size}>
  <path id="card" fill="{p["fill"]}" fill-rule="evenodd" d="M0,0H{W:g}V{H:g}H0Z{wd}{hd}"/>
  {eng}
</svg>
'''
    preview = f'''<svg xmlns="http://www.w3.org/2000/svg" {size}>
  <rect width="{W:g}" height="{H:g}" fill="{p["preview_bg"]}"/>
  <path fill="{p["fill"]}" fill-rule="evenodd" d="M0,0H{W:g}V{H:g}H0Z{wd}{hd}"/>
  {eng}
</svg>
'''
    stem = f"penrose-snowflake-{W/25.4:g}x{H/25.4:g}-{name}"
    files = {f"{stem}-cutlines.svg": cut, f"{stem}-filled.svg": filled, f"{stem}-preview.svg": preview}
    for fn, txt in files.items():
        (OUT / fn).write_text(txt)
    print(f"{name}: {len(holes)} holes, {len(windows)} window pieces -> out/{stem}-*.svg")
    return [OUT / fn for fn in files]


def render_previews(paths):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 480, "height": 672}, device_scale_factor=2)
        for f in paths:
            if f.name.endswith("-preview.svg"):
                pg.goto(f.resolve().as_uri())
                pg.screenshot(path=str(f.with_suffix(".png")))
        b.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    names = args or list(PRESETS)
    written = []
    for n in names:
        written += write_svgs(n, PRESETS[n])
    if "--preview" in sys.argv:
        render_previews(written)
