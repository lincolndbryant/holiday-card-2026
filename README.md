![Penrose snowflake card, bold preset](out/penrose-snowflake-5x7-bold-preview.svg)

A laser-cut 5 × 7 in holiday card front: a five-fold snowflake (a symmetry real
ice crystals never have) filled with a Penrose rhombus tiling, hung in a round
window and attached to the card at its five arm tips.

## Build

```sh
./build.sh                # first run creates .venv and installs dependencies; builds the card -> out/ and the ornament -> out/ornament/
./build.sh bold           # one preset of each
./build.sh --card         # card only (or --ornament for the ornament only)
./build.sh --preview      # also render PNG previews (first run downloads Chromium, ~90 MB)
```

Needs Python 3.9+ and Node.js (for the fonts). Edit the words in `text.json`, everything else in `generate.py`.

## Hangable ornament

`generate_ornament.py` (built by default; `./build.sh --ornament` for just this) makes the same snowflake as a separate piece: the round
disc is cut free of the card where its five arms cross the circle, and the top arm grows a small tab with a
hanging hole. Push the disc out of the card and hang it. Files go to `out/ornament/` (`*-piece.png` shows the
ornament on its own). Same presets and `text.json`; tab size and hole are `TAB_LEN` / `HANG_R` in the script. A 3 mm paper band (`ORNAMENT_BAND`, 0 to remove) rings the snowflake like a bauble.
The top arm carries small engraved lettering
(`ORNAMENT_TEXT`, "LB / KC / 26") instead of a flame; small cut-outs that would touch it are dropped.

## Presets (edit `PRESETS` in generate.py)

| preset | struts | tile edge | look |
|---|---|---|---|
| `fine` | 1.0 mm | 3.6 mm | delicate lace |
| `bold` | 1.6 mm | 4.9 mm | heavier, easier to see, more forgiving to cut |

Handy knobs: `FLAME_*` (the curled flame cut-out in each main arm: `FLAME_CURL`, `FLAME_WIDTH`, ...), `TIP_STYLE` (`leaf`/`flame`/`rhombus`), `CURL` (leaf bend), `stem_taper`, `ring_margin`
(keep leaves this far inside the window), `min_gap` / `min_bridge` (1 mm clearances), `strut` (bridge width), `L`/`N` (tile size = L / φᴺ), `ring`
(window radius), `center` (flake position), `card` (card size), `PAPER` / `BACKDROP` (preview colours only), `branches` (branch position, length, width, tip size).

## Lettering

The greeting is **engraved**, not cut. Edit `text.json` (the words, line width in mm, top y, spacing, and
`font`). Fonts are [Fontsource](https://fontsource.org) packages from npm (SIL OFL); `./build.sh` runs
`npm install` for you. Characters the main font lacks (❤ ❄ ★ ...) are drawn from Noto Emoji, filled solid (`FALLBACK_FONTS`, `EMOJI_SCALE` in `generate.py`).
To use another Google font, add `@fontsource/<name>` to `package.json` and set `"font": "<name>"`.

```sh
./build.sh --font=righteous       # whole build in one font -> out/fonts/righteous/
./build.sh --font-test --preview  # bold card in every font in FONT_TEST -> out/fonts/<font>/
```

## Output files (`out/`)

- `*-cutlines.svg`: grey filled lettering (engrave first), red hairline inner cuts, and a blue outline (cut last).
- `*-filled.svg`: the card as one filled shape with transparent cut-outs. Glowforge
  and Cricut-style software cut along every edge; set it to cut, not engrave.
- `*-preview.svg` / `.png`: how the card looks against a light backdrop. It is a single sheet of cardstock with
  holes cut through it; no insert or second layer is needed.

All units are millimetres; the SVGs import at true size.
