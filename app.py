#!/usr/bin/env python3
"""Mundial Studio – interfaz visual para previsualizar el look y editar.

App web local. Arranca con:

    python app.py            # abre http://127.0.0.1:5000

Permite:
  - Ver fotos/videos de una carpeta y probar presets/LUTs en vivo.
  - Cargar referencias para comparar el estilo.
  - Colocar la marca de agua arrastrandola sobre la imagen.
  - Corregir foto/video individualmente (cualquier ajuste) y guardarlo.
  - Exportar la carpeta entera con el look y los retoques aplicados.
"""

from __future__ import annotations

import glob
import io
import json
import os
import threading
import time
import webbrowser

from flask import (Flask, jsonify, request, send_file, send_from_directory)
from PIL import Image

from editor import loader, watermark as wm_mod
from editor.lut import CubeLUT
from editor.preset import DEFAULTS, load_preset
from editor.pipeline import apply_look, _apply_watermark

ROOT = os.path.dirname(os.path.abspath(__file__))
PRESET_DIR = os.path.join(ROOT, "presets")
ASSET_DIR = os.path.join(ROOT, "assets")
REF_DIR = os.path.join(ASSET_DIR, "_referencias")
os.makedirs(REF_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)

# Cache en memoria de imagenes base (para previsualizar rapido).
_CACHE: dict[str, tuple[float, "Image.Image"]] = {}
_CACHE_MAX = 24
_EXPORT = {"running": False, "done": 0, "total": 0, "msg": "", "errors": 0}


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def merge_params(params: dict) -> dict:
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (params or {}).items() if k in DEFAULTS})
    return p


def wm_from_ui(w: dict | None) -> dict | None:
    if not w or w.get("type") in (None, "none"):
        return None
    out = {"opacity": float(w.get("opacity", 0.85)),
           "scale": float(w.get("scale", 0.16)),
           "margin": float(w.get("margin", 0.04)),
           "position": w.get("position", "br")}
    if w.get("xy"):
        out["xy"] = (float(w["xy"][0]), float(w["xy"][1]))
    if w.get("type") == "logo" and w.get("logo"):
        out["logo"] = _safe_path(w["logo"])
    elif w.get("type") == "text" and w.get("text"):
        out["text"] = str(w["text"])
        if w.get("font"):
            out["font"] = _safe_path(w["font"])
    else:
        return None
    return out


def _safe_path(p: str) -> str:
    return os.path.abspath(p)


def _base_photo(path: str, max_size: int = 1400) -> Image.Image:
    key = f"{path}|{max_size}"
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    cached = _CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    arr = loader.load_thumb(path, max_size=max_size)
    im = loader.to_pil(arr)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = (mtime, im)
    return im


def _base_video_frame(path: str, t: float, max_size: int = 1280) -> Image.Image:
    from editor import ffmpeg_tools as ff
    key = f"{path}|{round(t, 2)}|{max_size}"
    cached = _CACHE.get(key)
    if cached:
        return cached[1]
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "f.jpg")
        subprocess.run([ff.ffmpeg_exe(), "-y", "-ss", f"{t:.2f}", "-i", path,
                        "-frames:v", "1", "-vf", f"scale={max_size}:-2",
                        out], capture_output=True)
        im = Image.open(out).convert("RGB")
        im.load()
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = (0, im)
    return im


def _center_crop(im: Image.Image, ratio_w: int, ratio_h: int) -> Image.Image:
    target = ratio_w / ratio_h
    w, h = im.size
    cur = w / h
    if cur > target:                       # demasiado ancho -> recorta lados
        nw = int(h * target)
        x = (w - nw) // 2
        return im.crop((x, 0, x + nw, h))
    nh = int(w / target)                   # demasiado alto -> recorta arriba/abajo
    y = (h - nh) // 2
    return im.crop((0, y, w, y + nh))


ASPECT_RATIOS = {"reel": (9, 16), "story": (9, 16), "tiktok": (9, 16),
                 "vertical": (9, 16), "feed": (4, 5), "portrait": (4, 5),
                 "square": (1, 1), "landscape": (16, 9), "youtube": (16, 9)}


def render_preview(path: str, kind: str, params: dict, wm: dict | None,
                   t: float = 0.0, aspect: str = "keep") -> bytes:
    if kind == "video":
        base = _base_video_frame(path, t)
    else:
        base = _base_photo(path)

    if aspect in ASPECT_RATIOS:
        base = _center_crop(base, *ASPECT_RATIOS[aspect])

    import numpy as np
    arr = np.asarray(base, dtype=np.float32) / 255.0
    out = apply_look(arr, params, None)
    im = loader.to_pil(out)
    if wm:
        im = _apply_watermark(im, wm)

    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    buf.seek(0)
    return buf.read()


# --------------------------------------------------------------------------
# Rutas estaticas
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(os.path.join(ROOT, "webui"), "index.html")


@app.route("/webui/<path:fname>")
def webui(fname):
    return send_from_directory(os.path.join(ROOT, "webui"), fname)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
@app.route("/api/presets")
def api_presets():
    out = []
    for fp in sorted(glob.glob(os.path.join(PRESET_DIR, "*.json"))):
        try:
            data = load_preset(fp)
            out.append({"file": fp, "name": data.get("name", os.path.basename(fp)),
                        "description": data.get("description", ""), "params": data})
        except Exception:  # noqa: BLE001
            continue
    return jsonify(out)


@app.route("/api/open", methods=["POST"])
def api_open():
    folder = (request.json or {}).get("folder", "").strip()
    if not folder or not os.path.isdir(folder):
        return jsonify({"error": f"No existe la carpeta: {folder}"}), 400
    from editor import ffmpeg_tools as ff
    photos, videos = [], []
    for n in sorted(os.listdir(folder)):
        p = os.path.join(folder, n)
        if not os.path.isfile(p):
            continue
        if loader.is_supported(p):
            photos.append(p)
        elif ff.is_video(p):
            videos.append(p)
    return jsonify({"folder": folder, "photos": photos, "videos": videos})


@app.route("/api/file")
def api_file():
    path = request.args.get("path", "")
    if not os.path.isfile(path):
        return ("", 404)
    return send_file(os.path.abspath(path))


@app.route("/api/thumb")
def api_thumb():
    path = request.args.get("path", "")
    if not os.path.isfile(path):
        return ("", 404)
    from editor import ffmpeg_tools as ff
    try:
        if ff.is_video(path):
            im = _base_video_frame(path, 0.5, max_size=320)
        else:
            im = _base_photo(path, max_size=320)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=80)
        buf.seek(0)
        return send_file(buf, mimetype="image/jpeg")
    except Exception as exc:  # noqa: BLE001
        return (str(exc), 500)


@app.route("/api/render", methods=["POST"])
def api_render():
    d = request.json or {}
    path = d.get("path", "")
    if not os.path.isfile(path):
        return jsonify({"error": "archivo no encontrado"}), 404
    try:
        data = render_preview(path, d.get("kind", "photo"),
                              merge_params(d.get("params")),
                              wm_from_ui(d.get("watermark")),
                              float(d.get("time", 0.0)),
                              d.get("aspect", "keep"))
        return send_file(io.BytesIO(data), mimetype="image/jpeg")
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


@app.route("/api/video_info")
def api_video_info():
    path = request.args.get("path", "")
    if not os.path.isfile(path):
        return jsonify({"error": "no encontrado"}), 404
    from editor import ffmpeg_tools as ff
    info = ff.probe(path)
    try:
        from editor.video_cull import analyze_video
        an = analyze_video(path, n_samples=8)
        info["best_segment"] = an["best_segment"]
        info["score"] = an["score"]
    except Exception:  # noqa: BLE001
        info["best_segment"] = [0.0, info.get("duration", 0.0)]
        info["score"] = None
    return jsonify(info)


@app.route("/api/save_preset", methods=["POST"])
def api_save_preset():
    d = request.json or {}
    name = (d.get("name") or "Mi preset").strip()
    params = merge_params(d.get("params"))
    params["name"] = name
    params["description"] = d.get("description", "")
    safe = "".join(c if c.isalnum() or c in "-_" else "_"
                   for c in name.lower())
    fp = os.path.join(PRESET_DIR, f"{safe or 'preset'}.json")
    with open(fp, "w", encoding="utf-8") as fh:
        json.dump(params, fh, indent=2, ensure_ascii=False)
    return jsonify({"file": fp, "name": name})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    kind = request.args.get("kind", "logo")
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "sin archivo"}), 400
    folder = REF_DIR if kind == "reference" else ASSET_DIR
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f.filename)
    f.save(dest)
    return jsonify({"path": os.path.abspath(dest)})


@app.route("/api/export", methods=["POST"])
def api_export():
    if _EXPORT["running"]:
        return jsonify({"error": "Ya hay una exportacion en curso"}), 409
    d = request.json or {}
    threading.Thread(target=_run_export, args=(d,), daemon=True).start()
    return jsonify({"started": True})


@app.route("/api/export_status")
def api_export_status():
    return jsonify(_EXPORT)


def _run_export(d: dict):
    from editor.pipeline import process_image
    _EXPORT.update(running=True, done=0, total=0, msg="Preparando...", errors=0)
    try:
        kind = d.get("kind", "photo")
        out_dir = d.get("output") or os.path.join(d.get("folder", "."), "editadas")
        os.makedirs(out_dir, exist_ok=True)
        params = merge_params(d.get("params"))
        overrides = d.get("overrides", {})
        wm = wm_from_ui(d.get("watermark"))
        files = d.get("files", [])
        _EXPORT["total"] = len(files)

        if kind == "video":
            from editor.lut_export import write_cube
            from editor.video import process_video
            lut = os.path.join(out_dir, "_look.cube")
            write_cube(params, lut, size=33)
            aspect = d.get("aspect", "keep")
            fit = d.get("fit", "crop")
            for i, f in enumerate(files, 1):
                _EXPORT["msg"] = os.path.basename(f)
                ov = overrides.get(f, {})
                trim = ov.get("trim")
                try:
                    process_video(f, os.path.join(
                        out_dir, os.path.splitext(os.path.basename(f))[0] + ".mp4"),
                        lut_path=lut, aspect=aspect, fit=fit, watermark=wm,
                        vignette=params.get("vignette", 0.0),
                        grain=params.get("grain", 0.0), trim=trim)
                except Exception:  # noqa: BLE001
                    _EXPORT["errors"] += 1
                _EXPORT["done"] = i
        else:
            max_size = int(d.get("max_size", 2048))
            quality = int(d.get("quality", 90))
            for i, f in enumerate(files, 1):
                _EXPORT["msg"] = os.path.basename(f)
                p = merge_params(overrides.get(f) or d.get("params"))
                try:
                    process_image(f, os.path.join(
                        out_dir, os.path.splitext(os.path.basename(f))[0] + ".jpg"),
                        p, None, max_size=max_size, quality=quality, wm=wm, seed=i)
                except Exception:  # noqa: BLE001
                    _EXPORT["errors"] += 1
                _EXPORT["done"] = i
        _EXPORT["msg"] = f"Listo: {len(files) - _EXPORT['errors']} ok en {out_dir}"
    except Exception as exc:  # noqa: BLE001
        _EXPORT["msg"] = f"Error: {exc}"
    finally:
        _EXPORT["running"] = False


def main():
    port = int(os.environ.get("PORT", "5000"))
    url = f"http://127.0.0.1:{port}"
    print(f"\n  Mundial Studio -> {url}\n")
    try:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    except Exception:  # noqa: BLE001
        pass
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
