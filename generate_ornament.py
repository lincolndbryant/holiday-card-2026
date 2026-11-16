#!/usr/bin/env python3
"""Penrose Snowflake hangable-ornament generator.

Same geometry as generate.py (snowflake, lace, leaves, flames, window, lettering), but the round
snowflake disc is a separate piece: it is cut free of the card where its five arms cross the circle,
and the top arm carries a small tab with a hanging hole. Push the disc out of the card and hang it.

Usage:
    python3 generate_ornament.py            # every preset -> out/ornament/
    python3 generate_ornament.py bold       # one preset
    python3 generate_ornament.py --preview  # also write PNG previews (needs playwright)

Requires the same things as generate.py. All units are millimetres.
"""
import math
import sys
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import generate as g

OUT = g.OUT / "ornament"

TAB_LEN = 11.0    # mm the hanging tab sticks out past the circle
HANG_R = 3.0      # radius of the hanging hole (6 mm across: fits ~1/4 in / 6 mm ribbon, folded or flat)
HANG_RIM = 3.0    # minimum paper between the hanging hole and the tab edge
ORNAMENT_BAND = 3.0                  # width of the circular band around the snowflake (0 = no band)
SEAM = "#f4f1ea"  # colour of the release cuts in the preview
ORNAMENT_TEXT = ["LB", "KC", "26"]   # engraved, stacked, on the top arm (replaces that arm's flame)
ORNAMENT_CAP = 3.6                   # letter height in mm (shrinks if the arm's free stretch is shorter)
ORNAMENT_GAP = 1.4                   # mm between the stacked lines
ORNAMENT_TRACK = 0.35                # mm between letters
ORNAMENT_MIN_CAP = 2.2               # never smaller than this (mm)
ORNAMENT_CLEAR = 1.2                 # mm kept between the lettering and any cut-out
ORNAMENT_SMALL_AREA = 16.0           # leaf holes this small (mm2) are dropped if they crowd the lettering
ORNAMENT_LACE_GAP = 1.5              # mm between the arm's last lace hole and the lettering
ORNAMENT_EDGE_GAP = 1.0              # mm between the top of the lettering and the ring band


def lines_d(geom):
    """SVG path data for open polylines."""
    out = []
    for ls in getattr(geom, "geoms", [geom]):
        if ls.geom_type != "LineString" or ls.length < 0.05:
            continue
        out.append("M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in ls.coords))
    return "".join(out)


def clean(geom, min_area=0.5):
    """Drop the zero-area slivers that shape arithmetic leaves where edges meet."""
    parts = [q for q in getattr(geom, "geoms", [geom]) if q.geom_type == "Polygon" and q.area >= min_area]
    return unary_union(parts) if len(parts) != 1 else parts[0]


def ornament_text(p, holes, fixed):
    """Small stacked lettering on the top arm, in the stretch the flame would have used (card coordinates).
    The block sits at the top of the arm's free stretch, just under the ring band. Letters are made as large as will fit while staying
    ORNAMENT_CLEAR mm from the `fixed` cut-outs (window, hanging hole, lace, big leaf holes).
    Small leaf holes (<= ORNAMENT_SMALL_AREA mm2) that would crowd the text are removed instead.
    Returns (polygons, small holes to drop)."""
    from shapely import affinity
    cx, cy = p["center"]
    lace = [h for h in holes if len(h.exterior.coords) <= 6]
    small = [h for h in holes if len(h.exterior.coords) > 6 and h.area <= ORNAMENT_SMALL_AREA]
    keep = unary_union([h for h in holes if all(h is not q for q in small)] + [fixed])
    _, _, _, r0, _ = g.arm_span(p, [affinity.translate(h, -cx, -cy) for h in lace], 0)
    r0 = r0 - g.FLAME_CLEAR + ORNAMENT_LACE_GAP          # just past the last lace hole
    r1 = p["ring"] - ORNAMENT_BAND - ORNAMENT_EDGE_GAP   # short of the ring band
    font = g.load_font(g._text.get("font", "bungee"), g._text.get("weight", 400))
    cmap = font.getBestCmap()
    n = len(ORNAMENT_TEXT)
    cap = ORNAMENT_CAP
    while cap >= ORNAMENT_MIN_CAP:
        block = n * cap + (n - 1) * ORNAMENT_GAP
        if r0 + block <= r1:
            polys = _stack(font, cmap, cap, cx, cy - r1)      # block hangs from the top of the free stretch
            t = unary_union(polys)
            if t.distance(keep) >= ORNAMENT_CLEAR:
                return polys, [h for h in small if t.distance(h) < ORNAMENT_CLEAR]
        cap = round(cap - 0.1, 2)
    sys.exit("ornament lettering does not fit on the top arm; shorten ORNAMENT_TEXT or lower ORNAMENT_MIN_CAP")


def _stack(font, cmap, cap, cx, y_top):
    from shapely import affinity
    k = cap / _glyph_height(font, cmap)
    out, y = [], y_top
    for line in ORNAMENT_TEXT:
        x, parts = 0.0, []
        for ch in line:
            geom, adv = g._glyph_polygons(font, cmap[ord(ch)])
            parts.append(affinity.translate(affinity.scale(geom, k, -k, origin=(0, 0)), x, 0))
            x += adv * k + ORNAMENT_TRACK
        b = unary_union(parts).bounds
        for q in parts:
            q = affinity.translate(q, cx - (b[0] + b[2]) / 2, y - b[1])
            out += [r for r in getattr(q, "geoms", [q]) if r.geom_type == "Polygon" and r.area > 0.02]
        y += cap + ORNAMENT_GAP
    return out


def _glyph_height(font, cmap):
    return g._glyph_polygons(font, cmap[ord("H")])[0].bounds[3]   # capital height in font units


def build_ornament(p):
    """Return the pieces, all in card coordinates (mm, y down)."""
    holes, windows = g.build(p, skip_flames=(0,))      # top arm carries lettering, not a flame
    cx, cy = p["center"]
    W, H = p["card"]
    ring = Point(cx, cy).buffer(p["ring"], resolution=128)
    if ORNAMENT_BAND:
        # a paper band around the snowflake: the open windows stop short of the circle and become
        # enclosed cut-outs; slivers narrower than min_window fill in with paper
        inner = Point(cx, cy).buffer(p["ring"] - ORNAMENT_BAND, resolution=128)
        r = p["min_window"] / 2
        opened = [q.buffer(-r, join_style=1).buffer(r, join_style=1) for q in (w.intersection(inner) for w in windows)]
        windows = [q for w in opened for q in getattr(w, "geoms", [w]) if q.geom_type == "Polygon" and q.area > 15]

    # hanging tab: the top arm continues past the circle and ends in a round cap
    tab_w = max(p["arm"], 2 * (HANG_R + HANG_RIM) + 0.2)           # wide enough to keep a paper rim round the hole
    cap_c = (cx, cy - (p["ring"] + TAB_LEN - tab_w / 2))      # centre of the round end
    tab = LineString([(cx, cy - (p["ring"] - 0.5)), cap_c]).buffer(tab_w / 2, resolution=32)
    hang = Point(*cap_c).buffer(HANG_R, resolution=48)
    assert tab.buffer(-HANG_RIM).contains(hang), "hanging hole too close to the tab edge"

    text, dropped = ornament_text(p, holes, unary_union(windows + [hang]))
    holes = [h for h in holes if all(h is not d for d in dropped)]   # small cut-outs touching the lettering

    disc = ring.difference(unary_union(windows)).union(tab)    # the free piece, before its holes
    ornament = clean(disc.difference(unary_union(holes + [hang])))
    card_hole = ring.union(tab)
    card = clean(box(0, 0, W, H).difference(card_hole))

    # release cuts: the disc's outline except the parts already cut as window edges
    release = disc.boundary.difference(unary_union(windows).buffer(0.02))
    return dict(holes=holes, windows=windows, hang=hang, disc=disc, ornament=ornament, text=text,
                card=card, card_hole=card_hole, release=release, tab=tab, ring=ring)


def check(name, p, o):
    """Report whether the ornament and the card each stay in one piece."""
    def pieces(geom, w):
        e = geom.buffer(-w / 2, join_style=2)
        return len(getattr(e, "geoms", [e]))
    orn, card = o["ornament"], o["card"]
    print(f"  {name}: ornament pieces {len(getattr(orn, 'geoms', [orn]))} "
          f"(at 0.98 mm bridges: {pieces(orn, 0.98)}), card pieces {len(getattr(card, 'geoms', [card]))}, "
          f"release cut {sum(l.length for l in getattr(o['release'], 'geoms', [o['release']])):.0f} mm")


def write_svgs(name, p):
    W, H = p["card"]
    o = build_ornament(p)
    hd = g.d_attr(o["holes"] + [o["hang"]])
    wd = g.d_attr(o["windows"])
    rd = lines_d(o["release"])
    ed = g.d_rings((g.text_engraving(W) if g.TEXT_LINES else []) + o["text"])
    eng = f'<path id="engraving" fill="{g.ENGRAVE}" fill-rule="evenodd" stroke="none" d="{ed}"/>' if ed else ""
    size = f'width="{W:g}mm" height="{H:g}mm" viewBox="0 0 {W:g} {H:g}"'
    OUT.mkdir(parents=True, exist_ok=True)

    orn_polys = [q for q in getattr(o["ornament"], "geoms", [o["ornament"]])]
    card_polys = [q for q in getattr(o["card"], "geoms", [o["card"]])]
    orn_d, card_d = g.d_rings(orn_polys), g.d_rings(card_polys)

    cut = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Penrose Snowflake ORNAMENT ({name}) - {W:g} x {H:g} mm. Grey = engrave (first), Red = inner cuts and the release cuts that free the ornament, Blue = outline (cut last). -->
<svg xmlns="http://www.w3.org/2000/svg" {size}>
  <g id="engrave">{eng}</g>
  <g id="inner-cuts" fill="none" stroke="#FF0000" stroke-width="0.0254">
    <path id="lace" d="{hd}"/>
    <path id="window" d="{wd}"/>
  </g>
  <g id="release-cuts" fill="none" stroke="#FF0000" stroke-width="0.0254">
    <path id="release" d="{rd}"/>
  </g>
  <g id="outer-cut" fill="none" stroke="#0000FF" stroke-width="0.0254">
    <rect x="0" y="0" width="{W:g}" height="{H:g}"/>
  </g>
</svg>
'''
    filled = f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Penrose Snowflake ORNAMENT ({name}) - {W:g} x {H:g} mm. Two filled pieces: the card (with a round opening plus hanging tab) and the ornament that sits in it. Set both paths to cut; the grey path is the engraving. The two pieces share edges, so use the cut-lines file if your software cuts shared edges twice. -->
<svg xmlns="http://www.w3.org/2000/svg" {size}>
  <path id="card" fill="{p["fill"]}" fill-rule="evenodd" d="{card_d}"/>
  <path id="ornament" fill="{p["fill"]}" fill-rule="evenodd" d="{orn_d}"/>
  {eng}
</svg>
'''
    preview = f'''<svg xmlns="http://www.w3.org/2000/svg" {size}>
  <rect width="{W:g}" height="{H:g}" fill="{p["preview_bg"]}"/>
  <path fill="{p["fill"]}" fill-rule="evenodd" d="{card_d}"/>
  <path fill="{p["fill"]}" fill-rule="evenodd" d="{orn_d}"/>
  <path d="{rd}" fill="none" stroke="{p["preview_bg"]}" stroke-width="0.35"/>
  {eng}
</svg>
'''
    # the ornament alone, hanging from a string
    b = o["disc"].bounds
    m = 6
    vb = (b[0] - m, b[1] - m - 14, (b[2] - b[0]) + 2 * m, (b[3] - b[1]) + 2 * m + 14)
    hx, hy = o["hang"].centroid.x, o["hang"].centroid.y
    piece = f'''<svg xmlns="http://www.w3.org/2000/svg" width="560" height="{int(560 * vb[3] / vb[2])}" viewBox="{vb[0]:.2f} {vb[1]:.2f} {vb[2]:.2f} {vb[3]:.2f}">
  <rect x="{vb[0]:.2f}" y="{vb[1]:.2f}" width="{vb[2]:.2f}" height="{vb[3]:.2f}" fill="{p["preview_bg"]}"/>
  <path d="M{hx:.2f},{vb[1]:.2f} L{hx:.2f},{hy:.2f}" stroke="#a83a3a" stroke-width="3" fill="none"/>
  <path fill="{p["fill"]}" fill-rule="evenodd" d="{orn_d}"/>
  <path fill="{g.ENGRAVE}" fill-rule="evenodd" d="{g.d_rings(o["text"])}"/>
</svg>
'''
    stem = f"penrose-snowflake-{W/25.4:g}x{H/25.4:g}-ornament-{name}"
    files = {f"{stem}-cutlines.svg": cut, f"{stem}-filled.svg": filled,
             f"{stem}-preview.svg": preview, f"{stem}-piece.svg": piece}
    for fn, txt in files.items():
        (OUT / fn).write_text(txt)
    print(f"{name}: {len(o['holes']) + 1} holes -> out/ornament/{stem}-*.svg")
    check(name, p, o)
    return [OUT / fn for fn in files], vb


def render_previews(paths):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for f, vb in paths:
            if f.name.endswith("-preview.svg"):
                pg = b.new_page(viewport={"width": 480, "height": 672}, device_scale_factor=2)
            elif f.name.endswith("-piece.svg"):
                pg = b.new_page(viewport={"width": 560, "height": int(560 * vb[3] / vb[2])}, device_scale_factor=2)
            else:
                continue
            pg.goto(f.resolve().as_uri())
            pg.screenshot(path=str(f.with_suffix(".png")))
            pg.close()
        b.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    names = args or list(g.PRESETS)
    written = []
    for n in names:
        files, vb = write_svgs(n, g.PRESETS[n])
        written += [(f, vb) for f in files]
    if "--preview" in sys.argv:
        render_previews(written)
