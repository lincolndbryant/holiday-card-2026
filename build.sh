#!/usr/bin/env bash
# One-step setup + build.
#   ./build.sh                 build every preset into out/
#   ./build.sh bold            build one preset
#   ./build.sh --preview       also render PNG previews (installs playwright + Chromium on first use)
set -euo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt

case " $* " in
  *" --preview "*)
    .venv/bin/pip install -q --disable-pip-version-check playwright
    .venv/bin/python -m playwright install chromium >/dev/null
    ;;
esac

.venv/bin/python generate.py "$@"
