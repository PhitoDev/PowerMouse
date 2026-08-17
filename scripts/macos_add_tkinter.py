"""Copy tkinter into a Briefcase macOS app bundle.

The Briefcase macOS support package ships without tkinter, but the dwell
palette (powermouse.palette) is a Tk app. This script copies tkinter from
the Python running it (a python-build-standalone interpreter, e.g. one
managed by uv -- the same one CI uses to run Briefcase) into the app's
embedded Python framework:

- the ``tkinter`` stdlib package
- the ``_tkinter`` extension module (it already carries an
  ``LC_RPATH @loader_path/../..`` entry, which resolves to the framework's
  ``lib`` directory below)
- the Tcl/Tk dylibs and script libraries into that ``lib`` directory

Run it between ``briefcase create macOS`` and ``briefcase build macOS`` so
the copied files are picked up by Briefcase's code signing:

    python scripts/macos_add_tkinter.py build/powermouse/macos/app/PowerMouse.app
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path-to-.app>", file=sys.stderr)
        return 2
    app = Path(sys.argv[1])
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    fw_lib = (
        app / "Contents" / "Frameworks" / "Python.framework" / "Versions" / version / "lib"
    )
    if not fw_lib.is_dir():
        print(f"error: {fw_lib} does not exist", file=sys.stderr)
        return 1

    # Use base_prefix so this works when run from a venv.
    src_lib = Path(sys.base_prefix) / "lib"
    src_stdlib = src_lib / f"python{version}"
    src_dynload = src_stdlib / "lib-dynload"
    dst_stdlib = fw_lib / f"python{version}"
    dst_dynload = dst_stdlib / "lib-dynload"

    # 1. The tkinter stdlib package.
    shutil.copytree(src_stdlib / "tkinter", dst_stdlib / "tkinter", dirs_exist_ok=True)

    # 2. The _tkinter extension module.
    extensions = sorted(src_dynload.glob("_tkinter.*.so"))
    if not extensions:
        print(f"error: no _tkinter extension found in {src_dynload}", file=sys.stderr)
        return 1
    for extension in extensions:
        shutil.copy2(extension, dst_dynload / extension.name)

    # 3. Tcl/Tk dylibs and script libraries (e.g. libtcl9.0.dylib,
    # libtcl9tk9.0.dylib, tcl9/, tcl9.0/, tk9.0/). Skip incidental packages
    # like itcl.
    copied = []
    for item in sorted(src_lib.iterdir()):
        name = item.name
        if not (name.startswith(("libtcl", "libtk", "tcl", "tk"))):
            continue
        if item.is_dir():
            shutil.copytree(item, fw_lib / name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, fw_lib / name)
        copied.append(name)
    if not any(name.startswith("libtcl") for name in copied):
        print(f"error: no Tcl library found in {src_lib}", file=sys.stderr)
        return 1

    print(f"tkinter bundled into {fw_lib.parent}: {', '.join(copied)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
