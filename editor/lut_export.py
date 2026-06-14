"""Exporta un preset (.json) a un LUT 3D .cube.

Esto permite aplicar EXACTAMENTE el mismo look de color a los videos (con
ffmpeg `lut3d`) que a las fotos. Solo se hornea la parte de COLOR/TONO del
preset; los efectos espaciales (vineta, grano) y las auto-correcciones se
aplican aparte, porque no son representables como un LUT.
"""

from __future__ import annotations

import numpy as np

from .lut import CubeLUT
from .pipeline import apply_color_look


def build_cube(preset: dict, size: int = 33,
               input_lut: CubeLUT | None = None) -> tuple[int, np.ndarray]:
    """Devuelve (size, tabla NxNxNx3) con el look horneado, ordenada [b,g,r]."""
    vals = np.linspace(0.0, 1.0, size, dtype=np.float32)
    rr = vals.reshape(1, 1, size)
    gg = vals.reshape(1, size, 1)
    bb = vals.reshape(size, 1, 1)
    grid = np.zeros((size, size, size, 3), dtype=np.float32)  # [b, g, r, 3]
    grid[..., 0] = np.broadcast_to(rr, (size, size, size))
    grid[..., 1] = np.broadcast_to(gg, (size, size, size))
    grid[..., 2] = np.broadcast_to(bb, (size, size, size))

    flat = grid.reshape(-1, 1, 3)
    out = apply_color_look(flat, preset, input_lut).reshape(size, size, size, 3)
    return size, out


def write_cube(preset: dict, path: str, size: int = 33,
               input_lut: CubeLUT | None = None) -> None:
    size, table = build_cube(preset, size, input_lut)
    name = preset.get("name", "Mundial")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"# LUT generado por Mundial desde el preset: {name}\n")
        fh.write(f'TITLE "{name}"\n')
        fh.write(f"LUT_3D_SIZE {size}\n")
        fh.write("DOMAIN_MIN 0.0 0.0 0.0\n")
        fh.write("DOMAIN_MAX 1.0 1.0 1.0\n")
        # En .cube el rojo varia mas rapido, luego verde, luego azul.
        for b in range(size):
            for g in range(size):
                for r in range(size):
                    c = table[b, g, r]
                    fh.write(f"{c[0]:.6f} {c[1]:.6f} {c[2]:.6f}\n")
