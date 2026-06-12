#!/usr/bin/env python3
"""Mundial – seleccion automatica de las mejores fotos (rafagas).

Analiza una carpeta, agrupa fotos parecidas (ráfagas) y elige la mejor de
cada grupo segun criterios profesionales (enfoque, exposicion, encuadre y
caras centradas). Copia las elegidas a una carpeta y escribe un informe CSV.

Ejemplos
--------
  # Selecciona las mejores y deja las descartadas aparte
  python cull.py -i ./fotos_raw -o ./seleccionadas --move-rejects

  # Encadenar con la edicion:
  python cull.py -i ./fotos_raw -o ./seleccionadas
  python auto_edit.py -i ./seleccionadas -o ./editadas \
      --preset presets/mundial_neon.json --text "MUNDIAL"
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from editor import culling, loader


def _metrics_worker(args):
    path, thumb = args
    try:
        return culling.compute_metrics(path, thumb_size=thumb), None
    except Exception as exc:  # noqa: BLE001
        return {"path": path}, str(exc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Selecciona la mejor foto de cada rafaga (Mundial).")
    ap.add_argument("-i", "--input", required=True, help="Carpeta de entrada.")
    ap.add_argument("-o", "--output", required=True,
                    help="Carpeta para las fotos seleccionadas.")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--hash-thresh", type=int, default=10,
                    help="Umbral de similitud para agrupar (0-64, menor = mas estricto).")
    ap.add_argument("--time-thresh", type=float, default=2.0,
                    help="Segundos entre fotos para considerarlas misma rafaga.")
    ap.add_argument("--thumb", type=int, default=1024,
                    help="Resolucion de analisis (px lado largo).")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--move", action="store_true",
                    help="Mover en vez de copiar las seleccionadas.")
    ap.add_argument("--move-rejects", action="store_true",
                    help="Copiar las descartadas a <output>/descartadas.")
    ap.add_argument("--report", default=None,
                    help="Ruta del CSV de informe (por defecto <output>/seleccion.csv).")
    a = ap.parse_args(argv)

    if not os.path.isdir(a.input):
        print(f"ERROR: no existe la carpeta: {a.input}", file=sys.stderr)
        return 2

    # Reutiliza el recolector del editor.
    from auto_edit import collect_images
    files = collect_images(a.input, a.recursive)
    if not files:
        print("No se han encontrado fotos compatibles.")
        return 1

    if not culling.has_face_detection():
        print("AVISO: OpenCV no disponible -> sin criterio de caras "
              "(instala opencv-python-headless para activarlo).")

    os.makedirs(a.output, exist_ok=True)
    print(f"Analizando {len(files)} fotos (paralelo: {a.jobs})...")

    t0 = time.time()
    metrics = []
    errors = 0
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futs = {ex.submit(_metrics_worker, (f, a.thumb)): f for f in files}
        done = 0
        for fut in as_completed(futs):
            m, err = fut.result()
            done += 1
            if err:
                errors += 1
                print(f"[{done}/{len(files)}] FALLO {os.path.basename(m['path'])}: {err}",
                      file=sys.stderr)
            else:
                metrics.append(m)

    keepers, rejects, groups = culling.select_best(
        metrics, hash_thresh=a.hash_thresh, time_thresh=a.time_thresh)

    # Copiar/mover seleccionadas.
    op = shutil.move if a.move else shutil.copy2
    for src in keepers:
        op(src, os.path.join(a.output, os.path.basename(src)))

    if a.move_rejects and rejects:
        rej_dir = os.path.join(a.output, "descartadas")
        os.makedirs(rej_dir, exist_ok=True)
        for src in rejects:
            (shutil.move if a.move else shutil.copy2)(
                src, os.path.join(rej_dir, os.path.basename(src)))

    # Informe CSV.
    report = a.report or os.path.join(a.output, "seleccion.csv")
    with open(report, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["grupo", "elegida", "archivo", "score", "nitidez",
                     "exposicion", "contraste", "caras", "nitidez_cara",
                     "centrado"])
        for gi, g in enumerate(groups, 1):
            for rank, m in enumerate(g):
                wr.writerow([gi, "SI" if rank == 0 else "no",
                             os.path.basename(m["path"]),
                             m.get("score", ""), round(m["sharpness"], 2),
                             round(m["exposure"], 3), round(m["contrast"], 3),
                             m["n_faces"], round(m["face_sharpness"], 2),
                             round(m["face_center"], 3)])

    dt = time.time() - t0
    n_bursts = sum(1 for g in groups if len(g) > 1)
    print("-" * 60)
    print(f"Grupos: {len(groups)} ({n_bursts} rafagas)  |  "
          f"elegidas: {len(keepers)}  |  descartadas: {len(rejects)}")
    print(f"Tiempo: {dt:.1f}s. Seleccionadas en: {a.output}")
    print(f"Informe: {report}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
