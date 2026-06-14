#!/usr/bin/env python3
"""Mundial – edicion de video por lotes con el mismo look que las fotos.

Coge una carpeta de videos sin editar, les aplica el look del preset (via
LUT), los reencuadra al formato de redes que quieras (Reels 9:16, feed 4:5,
cuadrado, 16:9...), puede recortar automaticamente el mejor tramo, descartar
los clips malos (movidos/desenfocados) y poner la marca de agua.

Ejemplos
--------
  # Reels verticales con el look neon, recorte automatico y logo
  python video_edit.py -i ./videos -o ./videos_editados \
      --preset presets/mundial_neon.json --aspect reel \
      --cull --auto-trim --logo assets/logo.png

  # Usando un LUT .cube ya existente, formato cuadrado, marca de texto
  python video_edit.py -i ./videos -o ./out --lut assets/neon.cube \
      --aspect square --text "MUNDIAL"
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from editor import ffmpeg_tools as ff
from editor import video as vid
from editor.lut_export import write_cube
from editor.preset import load_preset


def collect_videos(input_path: str, recursive: bool) -> list[str]:
    if os.path.isfile(input_path):
        return [input_path] if ff.is_video(input_path) else []
    out = []
    if recursive:
        for root, _d, names in os.walk(input_path):
            out += [os.path.join(root, n) for n in names
                    if ff.is_video(os.path.join(root, n))]
    else:
        out += [os.path.join(input_path, n) for n in os.listdir(input_path)
                if ff.is_video(os.path.join(input_path, n))]
    return sorted(out)


def _analyze_worker(path):
    from editor.video_cull import analyze_video
    try:
        return analyze_video(path), None
    except Exception as exc:  # noqa: BLE001
        return {"path": path}, str(exc)


def _process_worker(args):
    (in_path, out_path, kwargs) = args
    try:
        vid.process_video(in_path, out_path, **kwargs)
        return (in_path, True, "")
    except Exception as exc:  # noqa: BLE001
        return (in_path, False, str(exc))


def build_watermark(a):
    if a.logo:
        return {"logo": a.logo, "scale": a.wm_scale or 0.16,
                "opacity": a.wm_opacity, "position": a.wm_pos,
                "margin": a.wm_margin}
    if a.text:
        return {"text": a.text, "scale": a.wm_scale or 0.05,
                "opacity": a.wm_opacity, "position": a.wm_pos,
                "margin": a.wm_margin, "font": a.font}
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Edicion de video por lotes (Mundial).")
    ap.add_argument("-i", "--input", required=True,
                    help="Carpeta (o archivo) de video.")
    ap.add_argument("-o", "--output", required=True, help="Carpeta de salida.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--preset", help="Preset .json (se genera el LUT solo).")
    g.add_argument("--lut", help="LUT .cube ya existente.")

    ap.add_argument("--aspect", default="keep", choices=list(vid.ASPECTS.keys()),
                    help="Formato de salida (reel/feed/square/landscape/keep...).")
    ap.add_argument("--fit", default="crop", choices=["crop", "pad"],
                    help="crop = recorta al centro; pad = rellena con fondo borroso.")
    ap.add_argument("--crf", type=int, default=18, help="Calidad H.264 (menor = mejor).")
    ap.add_argument("--x264-preset", default="medium")
    ap.add_argument("--sharpen", type=float, default=0.5)
    ap.add_argument("--vignette", type=float, default=None,
                    help="Vineta (por defecto, la del preset).")
    ap.add_argument("--grain", type=float, default=None,
                    help="Grano (por defecto, el del preset).")

    # Seleccion / recorte
    ap.add_argument("--cull", action="store_true",
                    help="Analiza y descarta clips malos (movidos/desenfocados).")
    ap.add_argument("--min-score", type=float, default=0.35,
                    help="Nota minima para conservar un clip al usar --cull.")
    ap.add_argument("--auto-trim", action="store_true",
                    help="Recorta cada clip a su mejor tramo.")

    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--overwrite", action="store_true")

    # Marca de agua
    ap.add_argument("--logo")
    ap.add_argument("--text")
    ap.add_argument("--wm-pos", default="br",
                    choices=["br", "bl", "tr", "tl", "center"])
    ap.add_argument("--wm-opacity", type=float, default=0.85)
    ap.add_argument("--wm-scale", type=float, default=0.0)
    ap.add_argument("--wm-margin", type=float, default=0.04)
    ap.add_argument("--font")

    a = ap.parse_args(argv)

    if not os.path.exists(a.input):
        print(f"ERROR: no existe: {a.input}", file=sys.stderr)
        return 2

    videos = collect_videos(a.input, a.recursive)
    if not videos:
        print("No se han encontrado videos compatibles.")
        return 1

    os.makedirs(a.output, exist_ok=True)

    # --- Look: preparar el LUT ---
    preset = load_preset(a.preset) if a.preset else None
    lut_path = a.lut
    tmp_lut = None
    if a.preset:
        tmp_lut = os.path.join(a.output, "_look.cube")
        write_cube(preset, tmp_lut, size=33)
        lut_path = tmp_lut
        print(f"Look:    {preset.get('name')} -> LUT {tmp_lut}")
    elif a.lut:
        print(f"Look:    LUT {a.lut}")

    vignette = a.vignette if a.vignette is not None else (
        preset.get("vignette", 0.0) if preset else 0.0)
    grain = a.grain if a.grain is not None else (
        preset.get("grain", 0.0) if preset else 0.0)
    wm = build_watermark(a)

    print(f"Videos:  {len(videos)}  |  formato: {a.aspect} ({a.fit})  |  "
          f"paralelo: {a.jobs}")
    if wm:
        print(f"Marca:   {'logo ' + a.logo if a.logo else 'texto ' + repr(a.text)}")
    print("-" * 60)

    # --- Analisis / seleccion ---
    segments = {}
    analysis = {}
    if a.cull or a.auto_trim:
        print("Analizando clips...")
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            futs = {ex.submit(_analyze_worker, v): v for v in videos}
            for fut in as_completed(futs):
                res, err = fut.result()
                if err:
                    print(f"  aviso: no se pudo analizar "
                          f"{os.path.basename(res['path'])}: {err}",
                          file=sys.stderr)
                    continue
                analysis[res["path"]] = res

        report = os.path.join(a.output, "analisis_video.csv")
        with open(report, "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["archivo", "nota", "conservado", "duracion",
                         "tramo_ini", "tramo_fin", "nitidez", "estabilidad",
                         "exposicion", "caras"])
            kept = []
            for v in videos:
                r = analysis.get(v)
                if not r:
                    kept.append(v)  # si no se pudo analizar, conservar
                    continue
                keep = (not a.cull) or r["score"] >= a.min_score
                if keep:
                    kept.append(v)
                    if a.auto_trim:
                        segments[v] = r["best_segment"]
                wr.writerow([os.path.basename(v), r["score"],
                             "SI" if keep else "no", r["duration"],
                             r["best_segment"][0], r["best_segment"][1],
                             r["sharpness"], r["stability"], r["exposure"],
                             r["n_faces"]])
        dropped = len(videos) - len(kept)
        print(f"  conservados: {len(kept)}  |  descartados: {dropped}  "
              f"|  informe: {report}")
        videos = kept

    # --- Procesado ---
    tasks = []
    for v in videos:
        stem = os.path.splitext(os.path.basename(v))[0]
        out_path = os.path.join(a.output, f"{stem}.mp4")
        if os.path.exists(out_path) and not a.overwrite:
            continue
        kwargs = dict(lut_path=lut_path, aspect=a.aspect, fit=a.fit,
                      watermark=wm, crf=a.crf, x264_preset=a.x264_preset,
                      sharpen=a.sharpen, vignette=vignette, grain=grain,
                      trim=segments.get(v))
        tasks.append((v, out_path, kwargs))

    if not tasks:
        print("Todo estaba ya procesado (usa --overwrite para rehacer).")
        return 0

    t0 = time.time()
    ok = err = 0
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(_process_worker, t): t[0] for t in tasks}
        done, total = 0, len(futs)
        for fut in as_completed(futs):
            in_path, success, msg = fut.result()
            done += 1
            name = os.path.basename(in_path)
            if success:
                ok += 1
                print(f"[{done}/{total}] OK   {name}")
            else:
                err += 1
                print(f"[{done}/{total}] FALLO {name}: {msg}", file=sys.stderr)

    dt = time.time() - t0
    print("-" * 60)
    print(f"Listo: {ok} videos, {err} con error en {dt:.1f}s. Carpeta: {a.output}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
