# Sheet metal build API -- FreeCAD 1.0.0 + SheetMetal workbench + Flask.
#
# Same install steps as ../setup_env.sh, translated to Docker layers.
# Architecture-agnostic: picks the matching Miniconda installer and conda-
# forge builds (freecad=1.0.0 exists for both linux-64 and linux-aarch64
# on conda-forge, confirmed against its repodata before writing this) so
# this builds correctly on an Oracle Cloud Always Free ARM (Ampere) VM as
# well as a normal x86_64 box.
#
# Build from the sheetmetal-pipeline/ directory (needs scripts/ and
# config/ alongside backend/):
#   docker build -f backend/Dockerfile -t sheetmetal-api .
#   docker run -p 8000:8000 sheetmetal-api

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Miniconda -- Ubuntu 24.04 ships no `freecad` apt package at all for any
# architecture (checked directly against the apt indices, not just
# apt-cache search coming up empty), so conda-forge is the install path
# here, same as Stage 1.
RUN ARCH="$(uname -m)" && \
    case "$ARCH" in \
        x86_64)  MC_ARCH=x86_64 ;; \
        aarch64) MC_ARCH=aarch64 ;; \
        *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; \
    esac && \
    curl -sSL -o /tmp/miniconda.sh "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-${MC_ARCH}.sh" && \
    bash /tmp/miniconda.sh -b -p /opt/miniconda3 && \
    rm /tmp/miniconda.sh

ENV PATH="/opt/miniconda3/bin:${PATH}"

RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    conda create -y -n freecad -c conda-forge \
        freecad=1.0.0 networkx openpyxl flask flask-cors gunicorn && \
    conda clean -afy

# SheetMetal workbench, into FreeCAD's user Mod directory -- freecadcmd
# never auto-loads GUI workbenches, so headless scripts add this path
# themselves (see scripts/common.py::add_sheetmetal_to_path).
RUN FREECADCMD=/opt/miniconda3/envs/freecad/bin/freecadcmd && \
    USER_APP_DATA_DIR="$($FREECADCMD -c "import FreeCAD; print(FreeCAD.getUserAppDataDir())" 2>/dev/null | tail -1)" && \
    MOD_DIR="${USER_APP_DATA_DIR%/}/Mod" && \
    mkdir -p "$MOD_DIR" && \
    git clone --depth 1 https://github.com/shaise/FreeCAD_SheetMetal.git "$MOD_DIR/SheetMetal" && \
    rm -rf "$MOD_DIR/SheetMetal/.git" && \
    $FREECADCMD -c "import sys; sys.path.append('$MOD_DIR/SheetMetal'); import SheetMetalCmd; print('SheetMetal OK')"

WORKDIR /app
COPY scripts ./scripts
COPY config ./config
COPY backend ./backend

ENV FREECAD_LIB_DIR=/opt/miniconda3/envs/freecad/lib
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f "http://localhost:${PORT}/health" || exit 1

CMD ["/opt/miniconda3/envs/freecad/bin/gunicorn", "-c", "backend/gunicorn_conf.py", "backend.app:app"]
