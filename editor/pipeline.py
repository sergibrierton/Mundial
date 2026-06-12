"""Tuberia completa: cargar -> corregir -> aplicar look -> exportar."""

from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageFilter

from . import adjustments as adj
from . import loader, watermark
from .lut import CubeLUT


def _downscale(arr: np.ndarray, max_size: int) -> np.ndarray:
    """Reduce el lado largo a `max_size` ANTES de editar (mas rapido)."""
    h, w = arr.shape[:2]
    long_edge = max(h, w)
    if not max_size or long_edge <= max_size:
        return arr
    scale = max_size / float(long_edge)
    im = loader.to_pil(arr).resize(
        (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


def apply_look(arr: np.ndarray, preset: dict, lut: CubeLUT | None,
               seed: int = 0) -> np.ndarray:
    """Aplica correcciones automaticas + preset a un array float [0,1]."""
    p = preset

    if p.get("auto_white_balance"):
        arr = adj.auto_white_balance(arr, p.get("auto_white_balance_strength", 0.8))
    if p.get("auto_exposure"):
        arr = adj.auto_exposure(arr, p.get("auto_exposure_target", 0.42),
                                p.get("auto_exposure_strength", 0.7))

    arr = adj.exposure(arr, p.get("exposure", 0.0))
    arr = adj.temp_tint(arr, p.get("temp", 0.0), p.get("tint", 0.0))
    arr = adj.tone_regions(arr, p.get("highlights", 0.0), p.get("shadows", 0.0),
                           p.get("whites", 0.0), p.get("blacks", 0.0))
    arr = adj.contrast(arr, p.get("contrast", 0.0))
    arr = adj.tone_curve(arr, p.get("tone_curve"))
    arr = adj.vibrance_saturation(arr, p.get("vibrance", 0.0),
                                  p.get("saturation", 0.0))
    arr = adj.split_tone(arr, p.get("split_shadows"),
                         p.get("split_shadows_strength", 0.0),
                         p.get("split_highlights"),
                         p.get("split_highlights_strength", 0.0))

    if lut is not None:
        arr = lut.apply(arr, p.get("lut_strength", 1.0))

    arr = adj.vignette(arr, p.get("vignette", 0.0))
    arr = adj.grain(arr, p.get("grain", 0.0), seed=seed)
    return np.clip(arr, 0.0, 1.0)


def process_image(in_path: str, out_path: str, preset: dict,
                  lut: CubeLUT | None = None, *, max_size: int = 2560,
                  quality: int = 90, wm: dict | None = None,
                  seed: int = 0) -> None:
    """Procesa una foto y la guarda en out_path (JPEG)."""
    arr = loader.load_image(in_path)
    arr = _downscale(arr, max_size)
    arr = apply_look(arr, preset, lut, seed=seed)

    im = loader.to_pil(arr)

    sharpen = float(preset.get("sharpen", 0.0) or 0.0)
    if sharpen > 0:
        im = im.filter(ImageFilter.UnsharpMask(
            radius=1.2, percent=int(sharpen * 120), threshold=2))

    if wm:
        im = _apply_watermark(im, wm)

    loader.save_jpeg(im, out_path, quality=quality)


def _apply_watermark(im: Image.Image, wm: dict) -> Image.Image:
    if wm.get("logo"):
        return watermark.apply_logo(
            im, wm["logo"],
            scale=wm.get("scale", 0.18),
            opacity=wm.get("opacity", 0.85),
            position=wm.get("position", "br"),
            margin=wm.get("margin", 0.035))
    if wm.get("text"):
        return watermark.apply_text(
            im, wm["text"],
            scale=wm.get("scale", 0.045),
            opacity=wm.get("opacity", 0.85),
            position=wm.get("position", "br"),
            margin=wm.get("margin", 0.035),
            font_path=wm.get("font"))
    return im
