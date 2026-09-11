"""Shared setup for all pipeline scripts run under freecadcmd.

Every script that needs SheetMetal support should do:

    from common import add_sheetmetal_to_path
    add_sheetmetal_to_path()
    import SheetMetalCmd, SheetMetalBaseCmd, SheetMetalBendCuts  # etc.

`import SheetMetalCmd` only works once the workbench directory is on
sys.path -- FreeCAD's Mod/<name>/InitGui.py auto-loading only runs for the
GUI, not for freecadcmd, so headless scripts add the path themselves.
"""

import os
import subprocess
import sys


def _freecad_user_mod_dir():
    import FreeCAD

    return os.path.join(FreeCAD.getUserAppDataDir().rstrip("/"), "Mod")


def add_sheetmetal_to_path():
    """Locate the SheetMetal workbench directory and add it to sys.path.

    Resolution order:
      1. $SHEETMETAL_MOD_DIR env var, if set
      2. <FreeCAD user app data dir>/Mod/SheetMetal (the default install
         location used by setup_env.sh)
    """
    override = os.environ.get("SHEETMETAL_MOD_DIR")
    candidates = [override] if override else []
    candidates.append(os.path.join(_freecad_user_mod_dir(), "SheetMetal"))

    for path in candidates:
        if path and os.path.isdir(path):
            if path not in sys.path:
                sys.path.append(path)
            return path

    raise RuntimeError(
        "Could not find the SheetMetal workbench directory. Tried: "
        f"{candidates}. Run setup_env.sh, or set SHEETMETAL_MOD_DIR."
    )


def output_dir():
    """Path to the (gitignored) directory pipeline scripts write exports to."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(path, exist_ok=True)
    return path
