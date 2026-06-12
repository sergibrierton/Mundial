"""Soporte opcional de LUTs .cube (3D) con interpolacion trilineal.

Permite usar cualquier LUT cinematografico (.cube) descargado de internet
o exportado desde Lightroom/DaVinci como base del 'look'.
"""

from __future__ import annotations

import numpy as np


class CubeLUT:
    def __init__(self, size: int, table: np.ndarray,
                 domain_min=(0, 0, 0), domain_max=(1, 1, 1)):
        # table con forma (size, size, size, 3); indexado [b, g, r] -> RGB
        self.size = size
        self.table = table.astype(np.float32)
        self.dmin = np.asarray(domain_min, dtype=np.float32)
        self.dmax = np.asarray(domain_max, dtype=np.float32)

    @classmethod
    def load(cls, path: str) -> "CubeLUT":
        size = None
        dmin = [0.0, 0.0, 0.0]
        dmax = [1.0, 1.0, 1.0]
        rows = []
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                key = line.split()[0].upper()
                if key == "LUT_3D_SIZE":
                    size = int(line.split()[1])
                elif key == "DOMAIN_MIN":
                    dmin = [float(x) for x in line.split()[1:4]]
                elif key == "DOMAIN_MAX":
                    dmax = [float(x) for x in line.split()[1:4]]
                elif key in ("TITLE", "LUT_1D_SIZE", "LUT_3D_INPUT_RANGE"):
                    continue
                else:
                    parts = line.split()
                    if len(parts) == 3:
                        try:
                            rows.append([float(parts[0]),
                                         float(parts[1]),
                                         float(parts[2])])
                        except ValueError:
                            continue
        if size is None:
            raise ValueError(f"{path}: no es un LUT 3D .cube valido (falta LUT_3D_SIZE)")
        data = np.asarray(rows, dtype=np.float32)
        if data.shape[0] != size ** 3:
            raise ValueError(f"{path}: se esperaban {size**3} filas, hay {data.shape[0]}")
        # En .cube el rojo es el indice que varia mas rapido.
        table = data.reshape(size, size, size, 3)  # [b, g, r, 3]
        return cls(size, table, dmin, dmax)

    def apply(self, img: np.ndarray, strength: float = 1.0) -> np.ndarray:
        """Aplica el LUT a un array float RGB [0,1] con interpolacion trilineal."""
        if strength <= 0:
            return img
        n = self.size
        rng = np.maximum(self.dmax - self.dmin, 1e-6)
        norm = np.clip((img - self.dmin) / rng, 0.0, 1.0)
        coord = norm * (n - 1)
        i0 = np.floor(coord).astype(np.int32)
        i1 = np.minimum(i0 + 1, n - 1)
        f = (coord - i0).astype(np.float32)

        r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]
        r1, g1, b1 = i1[..., 0], i1[..., 1], i1[..., 2]
        fr = f[..., 0:1]; fg = f[..., 1:2]; fb = f[..., 2:3]
        t = self.table

        c000 = t[b0, g0, r0]; c100 = t[b0, g0, r1]
        c010 = t[b0, g1, r0]; c110 = t[b0, g1, r1]
        c001 = t[b1, g0, r0]; c101 = t[b1, g0, r1]
        c011 = t[b1, g1, r0]; c111 = t[b1, g1, r1]

        c00 = c000 * (1 - fr) + c100 * fr
        c10 = c010 * (1 - fr) + c110 * fr
        c01 = c001 * (1 - fr) + c101 * fr
        c11 = c011 * (1 - fr) + c111 * fr
        c0 = c00 * (1 - fg) + c10 * fg
        c1 = c01 * (1 - fg) + c11 * fg
        out = c0 * (1 - fb) + c1 * fb

        if strength < 1.0:
            out = img * (1.0 - strength) + out * strength
        return np.clip(out, 0.0, 1.0)
