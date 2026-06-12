"""Seleccion automatica de la mejor foto entre fotos similares (rafagas).

Agrupa fotos parecidas (ráfagas) y, dentro de cada grupo, puntua cada toma
con criterios de fotografo profesional y elige la mejor:

  - Enfoque / nitidez        (varianza del Laplaciano)
  - Exposicion               (evita quemados y empastados)
  - Contraste / presencia
  - Caras: nitidez de la cara, encuadre y centrado (regla de los tercios)

La deteccion de caras usa OpenCV (Haar) si esta instalado; si no, el resto
de criterios siguen funcionando.
"""

from __future__ import annotations

import os

import numpy as np

from . import loader

# Deteccion de caras opcional (OpenCV).
try:
    import cv2  # type: ignore

    _FACE_CASCADE = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    _HAS_CV2 = not _FACE_CASCADE.empty()
except Exception:  # noqa: BLE001
    cv2 = None
    _FACE_CASCADE = None
    _HAS_CV2 = False

_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def _gray(arr: np.ndarray) -> np.ndarray:
    return arr @ _LUMA


# --------------------------------------------------------------------------
# Hash perceptual (para agrupar fotos parecidas)
# --------------------------------------------------------------------------
def dhash(gray: np.ndarray, size: int = 8) -> int:
    from PIL import Image
    im = Image.fromarray((np.clip(gray, 0, 1) * 255).astype(np.uint8))
    im = im.resize((size + 1, size), Image.LANCZOS)
    g = np.asarray(im, dtype=np.int32)
    diff = g[:, 1:] > g[:, :-1]
    bits = 0
    for b in diff.flatten():
        bits = (bits << 1) | int(b)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# --------------------------------------------------------------------------
# Metricas de calidad
# --------------------------------------------------------------------------
def sharpness(gray: np.ndarray) -> float:
    """Varianza del Laplaciano: mayor = mas nitido/enfocado."""
    g = gray
    lap = (g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
           - 4.0 * g[1:-1, 1:-1])
    return float(lap.var()) * 1000.0


def exposure_score(gray: np.ndarray) -> float:
    """1.0 = exposicion ideal; penaliza quemados y zonas empastadas."""
    frac_black = float((gray < 0.02).mean())
    frac_white = float((gray > 0.98).mean())
    mean = float(gray.mean())
    clip_pen = min(1.0, frac_black * 3.0 + frac_white * 4.0)
    mid_pen = min(1.0, abs(mean - 0.45) * 1.6)
    return max(0.0, 1.0 - 0.7 * clip_pen - 0.3 * mid_pen)


def contrast_score(gray: np.ndarray) -> float:
    return float(np.clip(gray.std() / 0.28, 0.0, 1.0))


def detect_faces(gray: np.ndarray):
    """Lista de (x, y, w, h) de caras detectadas (vacia si no hay OpenCV)."""
    if not _HAS_CV2:
        return []
    g8 = (np.clip(gray, 0, 1) * 255).astype(np.uint8)
    faces = _FACE_CASCADE.detectMultiScale(
        g8, scaleFactor=1.1, minNeighbors=5,
        minSize=(int(g8.shape[1] * 0.04), int(g8.shape[0] * 0.04)))
    return [tuple(int(v) for v in f) for f in faces]


def face_scores(gray: np.ndarray, faces):
    """Devuelve (nitidez_cara, encuadre_centrado) en [0,1] aprox.

    - Nitidez de la cara mas grande (ojos/cara enfocada).
    - Encuadre: premia caras cerca del centro o de los puntos fuertes
      (regla de los tercios) y penaliza caras cortadas por el borde.
    """
    if not faces:
        return 0.0, 0.0
    h, w = gray.shape[:2]
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    fx, fy, fw, fh = faces[0]

    # Nitidez dentro de la cara principal.
    roi = gray[max(0, fy):fy + fh, max(0, fx):fx + fw]
    face_sharp = sharpness(roi) if roi.size > 50 else 0.0

    # Encuadre/centrado: distancia del centroide a los puntos fuertes.
    cx = (fx + fw / 2.0) / w
    cy = (fy + fh / 2.0) / h
    strong = [(0.5, 0.5), (1/3, 1/3), (2/3, 1/3), (1/3, 2/3), (2/3, 2/3)]
    dist = min(np.hypot(cx - sx, cy - sy) for sx, sy in strong)
    center_score = max(0.0, 1.0 - dist * 2.2)

    # Penaliza caras cortadas por el borde del encuadre.
    if fx <= 1 or fy <= 1 or (fx + fw) >= w - 1 or (fy + fh) >= h - 1:
        center_score *= 0.5

    return face_sharp, center_score


def compute_metrics(path: str, thumb_size: int = 1024) -> dict:
    """Calcula todas las metricas de una foto (a baja resolucion)."""
    arr = loader.load_thumb(path, max_size=thumb_size)
    gray = _gray(arr)
    faces = detect_faces(gray)
    f_sharp, f_center = face_scores(gray, faces)
    return {
        "path": path,
        "hash": dhash(gray),
        "sharpness": sharpness(gray),
        "exposure": exposure_score(gray),
        "contrast": contrast_score(gray),
        "n_faces": len(faces),
        "face_sharpness": f_sharp,
        "face_center": f_center,
        "time": loader.read_capture_time(path),
    }


# --------------------------------------------------------------------------
# Agrupado de rafagas y eleccion de la mejor
# --------------------------------------------------------------------------
def group_bursts(metrics: list[dict], hash_thresh: int = 10,
                 time_thresh: float = 2.0) -> list[list[dict]]:
    """Agrupa fotos consecutivas y visualmente parecidas (ráfagas)."""
    if not metrics:
        return []
    items = sorted(metrics, key=lambda m: os.path.basename(m["path"]))
    groups = [[items[0]]]
    for m in items[1:]:
        prev = groups[-1][-1]
        close_visual = hamming(m["hash"], prev["hash"]) <= hash_thresh
        if m["time"] is not None and prev["time"] is not None:
            close_time = abs(m["time"] - prev["time"]) <= time_thresh
            same = close_visual and close_time
        else:
            same = close_visual
        if same:
            groups[-1].append(m)
        else:
            groups.append([m])
    return groups


DEFAULT_WEIGHTS = {
    "sharpness": 0.35,
    "exposure": 0.20,
    "contrast": 0.10,
    "face_sharpness": 0.20,
    "face_center": 0.15,
}


def _normalize(values):
    vals = np.array(values, dtype=np.float32)
    lo, hi = float(vals.min()), float(vals.max())
    if hi - lo < 1e-6:
        return np.ones_like(vals)
    return (vals - lo) / (hi - lo)


def rank_group(group: list[dict], weights=None) -> list[dict]:
    """Puntua y ordena un grupo; añade 'score' a cada item (mejor primero)."""
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    has_faces = any(m["n_faces"] > 0 for m in group)

    # Normaliza metricas relativas dentro del grupo.
    norm = {
        "sharpness": _normalize([m["sharpness"] for m in group]),
        "exposure": _normalize([m["exposure"] for m in group]),
        "contrast": _normalize([m["contrast"] for m in group]),
        "face_sharpness": _normalize([m["face_sharpness"] for m in group]),
        "face_center": _normalize([m["face_center"] for m in group]),
    }
    if not has_faces:        # sin caras, repartimos su peso al resto
        w.pop("face_sharpness", None)
        w.pop("face_center", None)
    total_w = sum(w.values())

    for i, m in enumerate(group):
        s = sum(w[k] * float(norm[k][i]) for k in w) / total_w
        m["score"] = round(s, 4)
    return sorted(group, key=lambda m: m["score"], reverse=True)


def select_best(metrics: list[dict], hash_thresh: int = 10,
                time_thresh: float = 2.0, weights=None):
    """Devuelve (seleccionadas, descartadas, grupos_ordenados)."""
    groups = group_bursts(metrics, hash_thresh, time_thresh)
    ranked = [rank_group(g, weights) for g in groups]
    keepers = [g[0]["path"] for g in ranked]
    rejects = [m["path"] for g in ranked for m in g[1:]]
    return keepers, rejects, ranked


def has_face_detection() -> bool:
    return _HAS_CV2
