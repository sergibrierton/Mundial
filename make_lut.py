#!/usr/bin/env python3
"""Genera un LUT .cube a partir de un preset, para usarlo en video (o en
cualquier editor: DaVinci, Premiere, Lightroom...).

  python make_lut.py --preset presets/mundial_neon.json -o assets/neon.cube
"""

from __future__ import annotations

import argparse

from editor.lut_export import write_cube
from editor.preset import load_preset


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Exporta un preset a LUT .cube.")
    ap.add_argument("--preset", required=True, help="Archivo .json del preset.")
    ap.add_argument("-o", "--output", required=True, help="Ruta del .cube.")
    ap.add_argument("--size", type=int, default=33,
                    help="Resolucion del LUT (17/33/65). 33 es lo habitual.")
    a = ap.parse_args(argv)

    preset = load_preset(a.preset)
    write_cube(preset, a.output, size=a.size)
    print(f"LUT generado: {a.output}  (size {a.size}, preset '{preset.get('name')}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
