#!/usr/bin/env bash
# Reproducible install of FreeCAD + the SheetMetal workbench for headless use.
#
# Installs:
#   - Miniconda under $CONDA_PREFIX (default /opt/miniconda3)
#   - A conda env named "freecad" with FreeCAD 1.0.0 from conda-forge
#     (Ubuntu 24.04 "noble" ships no `freecad` apt package at all, so conda-forge
#     is the path here instead of apt/snap/flatpak/AppImage)
#   - shaise/FreeCAD_SheetMetal cloned into FreeCAD's user Mod directory
#
# Usage: ./setup_env.sh
set -euo pipefail

CONDA_PREFIX_DIR="${CONDA_PREFIX_DIR:-/opt/miniconda3}"
FREECAD_VERSION="${FREECAD_VERSION:-1.0.0}"
SHEETMETAL_REPO="${SHEETMETAL_REPO:-https://github.com/shaise/FreeCAD_SheetMetal.git}"

if [ ! -x "$CONDA_PREFIX_DIR/bin/conda" ]; then
  echo "Installing Miniconda into $CONDA_PREFIX_DIR ..."
  tmp_installer="$(mktemp /tmp/miniconda-XXXXXX.sh)"
  curl -sSL -o "$tmp_installer" https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash "$tmp_installer" -b -p "$CONDA_PREFIX_DIR"
  rm -f "$tmp_installer"
fi

CONDA="$CONDA_PREFIX_DIR/bin/conda"

"$CONDA" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
"$CONDA" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true

if [ ! -x "$CONDA_PREFIX_DIR/envs/freecad/bin/freecadcmd" ]; then
  echo "Creating conda env 'freecad' with FreeCAD $FREECAD_VERSION ..."
  "$CONDA" create -y -n freecad -c conda-forge "freecad=$FREECAD_VERSION"
fi

# networkx enables SheetMetal's newer (recommended) unfolder -- without it,
# the workbench silently falls back to the older, less capable unfolder.
if ! "$CONDA_PREFIX_DIR/envs/freecad/bin/python" -c "import networkx" 2>/dev/null; then
  echo "Installing networkx (for SheetMetal's new unfolder) ..."
  "$CONDA" install -y -n freecad -c conda-forge networkx
fi

FREECADCMD="$CONDA_PREFIX_DIR/envs/freecad/bin/freecadcmd"

USER_APP_DATA_DIR="$("$FREECADCMD" -c "import FreeCAD; print(FreeCAD.getUserAppDataDir())" 2>/dev/null | tail -1)"
MOD_DIR="${USER_APP_DATA_DIR%/}/Mod"
SHEETMETAL_DIR="$MOD_DIR/SheetMetal"

mkdir -p "$MOD_DIR"
if [ ! -d "$SHEETMETAL_DIR" ]; then
  echo "Cloning SheetMetal workbench into $SHEETMETAL_DIR ..."
  git clone --depth 1 "$SHEETMETAL_REPO" "$SHEETMETAL_DIR"
  rm -rf "$SHEETMETAL_DIR/.git"
else
  echo "SheetMetal workbench already present at $SHEETMETAL_DIR"
fi

echo "Verifying: freecadcmd + SheetMetalCmd import ..."
"$FREECADCMD" -c "
import sys
sys.path.append('$SHEETMETAL_DIR')
import SheetMetalCmd
print('OK:', SheetMetalCmd.__file__)
"

echo ""
echo "Environment ready."
echo "  freecadcmd:    $FREECADCMD"
echo "  SheetMetal WB: $SHEETMETAL_DIR"
echo ""
echo "Export these for the pipeline scripts, or let scripts/common.py autodetect them:"
echo "  export FREECADCMD=$FREECADCMD"
echo "  export SHEETMETAL_MOD_DIR=$SHEETMETAL_DIR"
