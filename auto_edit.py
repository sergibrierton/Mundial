#!/usr/bin/env python3
"""Mundial – edicion fotografica automatica por lotes.

Coge una carpeta de fotos sin editar (RAW .ARW de Sony o JPEG), les aplica
un 'look' consistente definido en un preset, opcionalmente una marca de
agua, y exporta JPEG listos para publicar.

Ejemplos
--------
  # Editar toda una carpeta con el preset neon y marca de agua de texto
  python auto_edit.py -i ./fotos_raw -o ./editadas \
      --preset presets/mundial_neon.json --text "MUNDIAL"

  # Con logo de la discoteca y salida a 2048px de lado largo
  python auto_edit.py -i ./fotos_raw -o ./editadas \
      --preset presets/mundial_warm.json --logo assets/logo.png \
      --max-size 2048

  # Usando un LUT cinematografico .cube
  python auto_edit.py -i ./fotos_raw -o ./editadas \
      --preset presets/mundial_neon.json --lut assets/look.cube
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from editor import loader
from editor.lut import CubeLUT
from editor.pipeline import process_image
from editor.preset import load_preset


def collect_images(input_dir: str, recursive: bool) -> list[str]:
    files = []
    if recursive:
        for root, _dirs, names in os.walk(input_dir):
            for n in names:
                p = os.path.join(root, n)
                if loader.is_supported(p):
                    files.append(p)
    else:
        for n in os.listdir(input_dir):
            p = os.path.join(input_dir, n)
            if os.path.isfile(p) and loader.is_supported(p):
                files.append(p)
    return sorted(files)


def _worker(args):
    (in_path, out_path, preset, lut_path, max_size, quality, wm, seed) = args
    lut = CubeLUT.load(lut_path) if lut_path else None
    try:
        process_image(in_path, out_path, preset, lut, max_size=max_size,
                      quality=quality, wm=wm, seed=seed)
        return (in_path, True, "")
    except Exception as exc:  # noqa: BLE001 - reportamos por foto, no abortamos
        return (in_path, False, str(exc))


def _cull_metrics_worker(args):
    from editor import culling
    path, thumb = args
    try:
        return culling.compute_metrics(path, thumb_size=thumb), None
    except Exception as exc:  # noqa: BLE001
        return {"path": path}, str(exc)


def _cull_files(files: list[str], a) -> list[str]:
    """Selecciona la mejor foto de cada rafaga y devuelve solo esas rutas."""
    from editor import culling

    if not culling.has_face_detection():
        print("AVISO: OpenCV no disponible -> seleccion sin criterio de caras.")
    print(f"Seleccionando mejores tomas entre {len(files)} fotos...")

    metrics = []
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(_cull_metrics_worker, (f, 1024)) for f in files]
        for fut in as_completed(futs):
            m, err = fut.result()
            if err:
                # Si no se pudo analizar, la conservamos por seguridad.
                m["_keep"] = True
            metrics.append(m)

    analyzable = [m for m in metrics if "hash" in m]
    forced = [m["path"] for m in metrics if m.get("_keep")]
    keepers, rejects, groups = culling.select_best(
        analyzable, hash_thresh=a.cull_hash_thresh,
        time_thresh=a.cull_time_thresh)
    n_bursts = sum(1 for g in groups if len(g) > 1)
    print(f"  -> {len(groups)} grupos ({n_bursts} rafagas), "
          f"{len(keepers)} elegidas, {len(rejects)} descartadas.")
    return sorted(set(keepers) | set(forced))


def build_watermark(a) -> dict | None:
    if a.logo:
        return {"logo": a.logo, "scale": a.wm_scale or 0.18,
                "opacity": a.wm_opacity, "position": a.wm_pos,
                "margin": a.wm_margin}
    if a.text:
        return {"text": a.text, "scale": a.wm_scale or 0.045,
                "opacity": a.wm_opacity, "position": a.wm_pos,
                "margin": a.wm_margin, "font": a.font}
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Edicion fotografica automatica por lotes (Mundial).")
    ap.add_argument("-i", "--input", required=True, help="Carpeta de entrada.")
    ap.add_argument("-o", "--output", required=True, help="Carpeta de salida.")
    ap.add_argument("--preset", required=True, help="Archivo .json del preset.")
    ap.add_argument("--lut", help="LUT .cube opcional.")
    ap.add_argument("--max-size", type=int, default=2560,
                    help="Lado largo de la imagen de salida en px (0 = original).")
    ap.add_argument("--quality", type=int, default=90,
                    help="Calidad JPEG (1-100).")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="Procesos en paralelo.")
    ap.add_argument("--recursive", action="store_true",
                    help="Buscar fotos en subcarpetas.")
    ap.add_argument("--overwrite", action="store_true",
                    help="Reprocesar aunque ya exista la salida.")
    ap.add_argument("--suffix", default="",
                    help="Sufijo para el nombre de salida (ej. _mundial).")

    # Seleccion previa de mejores fotos (rafagas)
    ap.add_argument("--cull", action="store_true",
                    help="Antes de editar, elige la mejor foto de cada rafaga.")
    ap.add_argument("--cull-hash-thresh", type=int, default=10,
                    help="Umbral de similitud para agrupar rafagas (0-64).")
    ap.add_argument("--cull-time-thresh", type=float, default=2.0,
                    help="Segundos entre fotos para considerarlas misma rafaga.")

    # Marca de agua
    ap.add_argument("--logo", help="PNG con transparencia para la marca de agua.")
    ap.add_argument("--text", help="Texto de marca de agua (si no hay logo).")
    ap.add_argument("--wm-pos", default="br",
                    choices=["br", "bl", "tr", "tl", "center"],
                    help="Posicion de la marca de agua.")
    ap.add_argument("--wm-opacity", type=float, default=0.85)
    ap.add_argument("--wm-scale", type=float, default=0.0,
                    help="Tamano relativo (logo: ancho; texto: alto).")
    ap.add_argument("--wm-margin", type=float, default=0.035)
    ap.add_argument("--font", help="Ruta a una fuente .ttf para el texto.")

    a = ap.parse_args(argv)

    if not os.path.isdir(a.input):
        print(f"ERROR: no existe la carpeta de entrada: {a.input}", file=sys.stderr)
        return 2
    if a.lut and not os.path.isfile(a.lut):
        print(f"ERROR: no existe el LUT: {a.lut}", file=sys.stderr)
        return 2

    preset = load_preset(a.preset)
    wm = build_watermark(a)
    os.makedirs(a.output, exist_ok=True)

    files = collect_images(a.input, a.recursive)
    if not files:
        print("No se han encontrado fotos compatibles en la carpeta.")
        return 1

    if a.cull:
        files = _cull_files(files, a)
        if not files:
            print("La seleccion no dejo ninguna foto.")
            return 1

    # Validacion temprana del LUT (mejor fallar ahora que en cada worker).
    if a.lut:
        CubeLUT.load(a.lut)

    print(f"Preset:  {preset.get('name')} — {preset.get('description', '')}")
    print(f"Fotos:   {len(files)}  |  paralelo: {a.jobs}  |  salida: {a.output}")
    if wm:
        print(f"Marca:   {'logo ' + a.logo if a.logo else 'texto ' + repr(a.text)} "
              f"({a.wm_pos})")
    print("-" * 60)

    tasks = []
    for idx, in_path in enumerate(files):
        stem = os.path.splitext(os.path.basename(in_path))[0]
        out_path = os.path.join(a.output, f"{stem}{a.suffix}.jpg")
        if os.path.exists(out_path) and not a.overwrite:
            continue
        tasks.append((in_path, out_path, preset, a.lut, a.max_size,
                      a.quality, wm, idx))

    if not tasks:
        print("Todo estaba ya procesado (usa --overwrite para rehacer).")
        return 0

    t0 = time.time()
    ok = err = 0
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futures = {ex.submit(_worker, t): t[0] for t in tasks}
        done = 0
        total = len(futures)
        for fut in as_completed(futures):
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
    print(f"Listo: {ok} editadas, {err} con error en {dt:.1f}s "
          f"({dt / max(1, ok):.2f}s/foto). Carpeta: {a.output}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
