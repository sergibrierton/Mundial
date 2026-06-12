"""Operaciones de ajuste de color y tono, vectorizadas con numpy.

Todo trabaja sobre arrays float32 RGB en rango [0, 1] en gamma sRGB.
Exposicion y balance de blancos se hacen en luz lineal (mas correcto);
el resto de ajustes se hacen en gamma (mas parecido a Lightroom y mas
agradable a la vista).
"""

from __future__ import annotations

import numpy as np

# Pesos de luminancia Rec.709.
_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


# --------------------------------------------------------------------------
# Conversiones sRGB <-> lineal
# --------------------------------------------------------------------------
def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1.0 / 2.4)) - 0.055)


def luminance(img: np.ndarray) -> np.ndarray:
    """Luminancia HxWx1 en gamma sRGB."""
    return (img @ _LUMA)[..., None]


# --------------------------------------------------------------------------
# Correcciones automaticas ("la parte lista")
# --------------------------------------------------------------------------
def auto_white_balance(img: np.ndarray, strength: float = 0.8) -> np.ndarray:
    """Gray-world suave en luz lineal. Neutraliza dominantes de color
    (tipicas con luces de discoteca) manteniendo algo del ambiente."""
    if strength <= 0:
        return img
    lin = srgb_to_linear(img)
    means = lin.reshape(-1, 3).mean(axis=0)
    means = np.maximum(means, 1e-4)
    g = means[1]
    gains = np.clip(g / means, 0.6, 1.6).astype(np.float32)
    gains = 1.0 + (gains - 1.0) * float(strength)
    lin = lin * gains
    return linear_to_srgb(lin)


def auto_exposure(img: np.ndarray, target: float = 0.42,
                  strength: float = 0.7) -> np.ndarray:
    """Lleva la luminancia mediana hacia un objetivo, para que todas las
    fotos del lote tengan un brillo parecido."""
    if strength <= 0:
        return img
    lin = srgb_to_linear(img)
    luma = lin @ _LUMA
    cur = float(np.median(luma))
    if cur <= 1e-4:
        return img
    tgt = float(srgb_to_linear(np.array([target], dtype=np.float32))[0])
    factor = np.clip(tgt / cur, 0.45, 2.6)
    factor = 1.0 + (factor - 1.0) * float(strength)
    return linear_to_srgb(lin * factor)


# --------------------------------------------------------------------------
# Ajustes del "look" (preset)
# --------------------------------------------------------------------------
def exposure(img: np.ndarray, ev: float) -> np.ndarray:
    if not ev:
        return img
    lin = srgb_to_linear(img) * (2.0 ** float(ev))
    return linear_to_srgb(lin)


def temp_tint(img: np.ndarray, temp: float, tint: float) -> np.ndarray:
    """temp: positivo = mas calido. tint: positivo = mas magenta."""
    if not temp and not tint:
        return img
    lin = srgb_to_linear(img)
    rg = 1.0 + temp * 0.0035
    bg = 1.0 - temp * 0.0035
    gg = 1.0 - tint * 0.0030
    gains = np.array([rg, gg, bg], dtype=np.float32)
    return linear_to_srgb(lin * gains)


def contrast(img: np.ndarray, amount: float) -> np.ndarray:
    """amount en [-100, 100]. Curva en S suave (pivote 0.5)."""
    if not amount:
        return img
    a = float(amount) / 100.0
    if a >= 0:
        smooth = img * img * (3.0 - 2.0 * img)        # smoothstep -> S
        return img * (1.0 - a) + smooth * a
    return np.clip(0.5 + (img - 0.5) * (1.0 + a), 0.0, 1.0)


def tone_regions(img: np.ndarray, highlights=0.0, shadows=0.0,
                 whites=0.0, blacks=0.0) -> np.ndarray:
    """Recupera/realza por zonas tonales, estilo Lightroom (aproximado)."""
    if not any([highlights, shadows, whites, blacks]):
        return img
    lum = luminance(img)
    sh_mask = np.clip(1.0 - 2.0 * lum, 0.0, 1.0)       # zonas oscuras
    hi_mask = np.clip(2.0 * lum - 1.0, 0.0, 1.0)       # zonas claras
    out = img.copy()
    out = out + (shadows / 100.0) * 0.55 * sh_mask
    out = out + (highlights / 100.0) * 0.55 * hi_mask
    out = out + (whites / 100.0) * 0.40 * lum
    out = out + (blacks / 100.0) * 0.40 * (1.0 - lum)
    return np.clip(out, 0.0, 1.0)


def vibrance_saturation(img: np.ndarray, vibrance=0.0,
                        saturation=0.0) -> np.ndarray:
    if not vibrance and not saturation:
        return img
    lum = luminance(img)
    maxc = img.max(axis=2, keepdims=True)
    minc = img.min(axis=2, keepdims=True)
    sat = (maxc - minc) / (maxc + 1e-5)
    vib_factor = 1.0 + (vibrance / 100.0) * (1.0 - sat)
    factor = vib_factor * (1.0 + saturation / 100.0)
    return np.clip(lum + (img - lum) * factor, 0.0, 1.0)


def split_tone(img: np.ndarray, shadows_rgb=None, shadows_strength=0.0,
               highlights_rgb=None, highlights_strength=0.0) -> np.ndarray:
    """Tinte de color en sombras y luces (split toning)."""
    out = img
    lum = luminance(img)
    if shadows_rgb is not None and shadows_strength:
        tint = np.asarray(shadows_rgb, dtype=np.float32) - 0.5
        out = out + shadows_strength * (1.0 - lum) * tint
    if highlights_rgb is not None and highlights_strength:
        tint = np.asarray(highlights_rgb, dtype=np.float32) - 0.5
        out = out + highlights_strength * lum * tint
    return np.clip(out, 0.0, 1.0)


def tone_curve(img: np.ndarray, points) -> np.ndarray:
    """Aplica una curva de tono definida por puntos [[x,y],...] en [0,1]."""
    if not points:
        return img
    pts = sorted(points, key=lambda p: p[0])
    xs = np.array([p[0] for p in pts], dtype=np.float32)
    ys = np.array([p[1] for p in pts], dtype=np.float32)
    grid = np.linspace(0.0, 1.0, 1024, dtype=np.float32)
    lut = np.interp(grid, xs, ys).astype(np.float32)
    idx = np.clip(img * 1023.0, 0, 1023).astype(np.int32)
    return lut[idx]


def vignette(img: np.ndarray, amount: float) -> np.ndarray:
    if not amount:
        return img
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    d = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / np.sqrt(2.0)
    mask = 1.0 - float(amount) * (d ** 2.2)
    return np.clip(img * mask[..., None], 0.0, 1.0)


def grain(img: np.ndarray, amount: float, seed: int = 0) -> np.ndarray:
    if not amount:
        return img
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, float(amount), img.shape[:2]).astype(np.float32)
    return np.clip(img + noise[..., None], 0.0, 1.0)
