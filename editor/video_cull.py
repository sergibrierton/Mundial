"""Analisis y seleccion de clips de video.

Para cada video muestrea fotogramas y los puntua con criterios de editor
profesional (enfoque, exposicion, estabilidad/movimiento de camara y caras),
da una nota global y sugiere el mejor tramo (para recortar lo bueno).
"""

from __future__ import annotations

import os
import tempfile

import numpy as np

from . import culling, ffmpeg_tools as ff, loader

_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def extract_frames(path: str, n: int, out_dir: str, width: int = 480) -> list[str]:
    """Extrae n fotogramas repartidos por el video, a baja resolucion."""
    info = ff.probe(path)
    dur = max(0.1, info["duration"])
    fps = max(0.1, n / dur)
    pattern = os.path.join(out_dir, "f_%04d.png")
    ff.run([ff.ffmpeg_exe(), "-y", "-i", path,
            "-vf", f"fps={fps:.4f},scale={width}:-2", "-frames:v", str(n),
            pattern])
    return sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir)
                  if f.endswith(".png"))


def analyze_video(path: str, n_samples: int = 12) -> dict:
    """Devuelve metricas y un tramo recomendado (best_segment) del video."""
    info = ff.probe(path)
    dur = max(0.1, info["duration"])

    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(path, n_samples, tmp)
        grays, per = [], []
        for fp in frames:
            arr = loader.load_thumb(fp, max_size=480)
            gray = arr @ _LUMA
            grays.append(gray)
            faces = culling.detect_faces(gray)
            f_sharp, f_center = culling.face_scores(gray, faces)
            per.append({
                "sharpness": culling.sharpness(gray),
                "exposure": culling.exposure_score(gray),
                "n_faces": len(faces),
                "face_sharpness": f_sharp,
                "face_center": f_center,
            })

    if not per:
        return {"path": path, "score": 0.0, "duration": dur,
                "best_segment": (0.0, dur), "width": info["width"],
                "height": info["height"], "n_faces": 0, "stability": 0.0,
                "sharpness": 0.0, "exposure": 0.0}

    # Estabilidad: poco movimiento "global" entre fotogramas = mas estable.
    motion = []
    for a, b in zip(grays[:-1], grays[1:]):
        if a.shape == b.shape:
            motion.append(float(np.abs(a - b).mean()))
    stability = float(np.clip(1.0 - (np.mean(motion) if motion else 0.0) * 6.0,
                              0.0, 1.0))

    sharp = float(np.median([p["sharpness"] for p in per]))
    expo = float(np.median([p["exposure"] for p in per]))
    faces = max(p["n_faces"] for p in per)
    face_sharp = float(np.median([p["face_sharpness"] for p in per]))

    # Nota global (0-1). El enfoque y la estabilidad mandan en video.
    sharp_n = float(np.clip(sharp / 1.2, 0.0, 1.0))
    fsharp_n = float(np.clip(face_sharp / 40.0, 0.0, 1.0))
    if faces > 0:
        score = (0.30 * sharp_n + 0.25 * stability + 0.20 * expo +
                 0.25 * fsharp_n)
    else:
        score = (0.45 * sharp_n + 0.30 * stability + 0.25 * expo)

    best = _best_segment(per, grays, dur)

    return {
        "path": path,
        "score": round(score, 4),
        "duration": round(dur, 2),
        "best_segment": best,
        "width": info["width"],
        "height": info["height"],
        "n_faces": faces,
        "stability": round(stability, 3),
        "sharpness": round(sharp, 3),
        "exposure": round(expo, 3),
    }


def _best_segment(per, grays, dur):
    """Encuentra la ventana contigua de mejor calidad para recortar."""
    n = len(per)
    if n <= 2 or dur <= 3.0:
        return (0.0, round(dur, 2))

    good = np.array([0.6 * np.clip(p["sharpness"] / 1.2, 0, 1) +
                     0.4 * p["exposure"] for p in per], dtype=np.float32)
    # Ventana de ~60% de las muestras (minimo 3).
    win = max(3, int(n * 0.6))
    best_i, best_avg = 0, -1.0
    for i in range(0, n - win + 1):
        avg = float(good[i:i + win].mean())
        if avg > best_avg:
            best_avg, best_i = avg, i
    start = best_i / n * dur
    end = (best_i + win) / n * dur
    return (round(max(0.0, start), 2), round(min(dur, end), 2))
