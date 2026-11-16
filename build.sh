#!/usr/bin/env bash
# One-step setup + build. Builds the card AND the hangable ornament by default.
#   ./build.sh                 card -> out/   and   ornament -> out/ornament/   (all presets)
#   ./build.sh bold            one preset of each
#   ./build.sh --preview       also render PNG previews (installs playwright + Chromium on first use)
#   ./build.sh --card          card only          ./build.sh --ornament   ornament only
#   ./build.sh --font-test --preview   the bold card in several fonts -> out/fonts/<font>/   (card only)
#   ./build.sh --font=righteous        the whole card in one font -> out/fonts/righteous/    (card only)
set -euo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
command -v npm >/dev/null || { echo "npm is needed for the fonts: install Node.js (https://nodejs.org)" >&2; exit 1; }
npm install --silent --no-audit --no-fund

case " $* " in
  *" --preview "*)
    .venv/bin/pip install -q --disable-pip-version-check playwright
    .venv/bin/python -m playwright install chromium >/dev/null
    ;;
esac

mode=both; args=()
for a in "$@"; do
  case "$a" in
    --card)                   mode=card ;;
    --ornament)               mode=ornament ;;
    --font=*|--font-test)     mode=card; args+=("$a") ;;   # font options apply to the card only
    *)                        args+=("$a") ;;
  esac
done

[ "$mode" != ornament ] && .venv/bin/python generate.py ${args[@]+"${args[@]}"}
[ "$mode" != card ]     && .venv/bin/python generate_ornament.py ${args[@]+"${args[@]}"}
exit 0
