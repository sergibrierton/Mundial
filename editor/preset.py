"""Carga de presets (.json) con valores por defecto."""

from __future__ import annotations

import json

DEFAULTS = {
    "name": "Sin nombre",
    "description": "",

    # Correcciones automaticas
    "auto_white_balance": True,
    "auto_white_balance_strength": 0.8,
    "auto_exposure": True,
    "auto_exposure_target": 0.42,
    "auto_exposure_strength": 0.7,

    # Look
    "exposure": 0.0,
    "temp": 0.0,
    "tint": 0.0,
    "contrast": 0.0,
    "highlights": 0.0,
    "shadows": 0.0,
    "whites": 0.0,
    "blacks": 0.0,
    "vibrance": 0.0,
    "saturation": 0.0,
    "split_shadows": None,
    "split_shadows_strength": 0.0,
    "split_highlights": None,
    "split_highlights_strength": 0.0,
    "tone_curve": None,
    "vignette": 0.0,
    "grain": 0.0,

    # LUT opcional
    "lut": None,
    "lut_strength": 1.0,

    # Nitidez de salida (web)
    "sharpen": 0.6,
}


def load_preset(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    preset = dict(DEFAULTS)
    preset.update(data)
    return preset
