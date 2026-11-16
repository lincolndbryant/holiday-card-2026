#!/usr/bin/env bash
# One-step setup + build.
#   ./build.sh                 build every preset into out/
#   ./build.sh bold            build one preset
#   ./build.sh --preview       also render PNG previews (installs playwright + Chromium on first use)
#   ./build.sh --font-test --preview   the bold card in several fonts -> out/fonts/<font>/
#   ./build.sh --font=righteous        the whole build in one font -> out/fonts/righteous/
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

.venv/bin/python generate.py "$@"
