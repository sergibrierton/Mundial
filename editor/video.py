"""Procesado de video con ffmpeg: grade (LUT), reencuadre, recorte y marca
de agua. Comparte el mismo look que las fotos via LUT .cube."""

from __future__ import annotations

import os

from . import ffmpeg_tools as ff

# Formatos de salida habituales en redes (ancho x alto).
ASPECTS = {
    "keep": None,                 # mantiene el original, solo grade
    "reel": (1080, 1920),         # 9:16 vertical (Reels / Stories / TikTok)
    "story": (1080, 1920),
    "tiktok": (1080, 1920),
    "vertical": (1080, 1920),
    "feed": (1080, 1350),         # 4:5 (feed Instagram)
    "portrait": (1080, 1350),
    "square": (1080, 1080),       # 1:1
    "landscape": (1920, 1080),    # 16:9
    "youtube": (1920, 1080),
}

_POS = {
    "br": ("W-w-{m}", "H-h-{m}"),
    "bl": ("{m}", "H-h-{m}"),
    "tr": ("W-w-{m}", "{m}"),
    "tl": ("{m}", "{m}"),
    "center": ("(W-w)/2", "(H-h)/2"),
}


def _reframe_chain(w: int, h: int, fit: str) -> str:
    if fit == "pad":
        # Rellena con el propio fondo desenfocado (no recorta nada).
        return (f"split[bgsrc][fgsrc];"
                f"[bgsrc]scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},gblur=sigma=25[bg];"
                f"[fgsrc]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    # crop (por defecto): escala para cubrir y recorta al centro.
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}")


def build_filter_complex(aspect: str, fit: str, lut_path: str | None,
                         sharpen: float, vignette: float, grain: float,
                         out_size, watermark: dict | None,
                         has_logo: bool) -> tuple[str, str]:
    """Construye el grafo de filtros. Devuelve (filter_complex, label_salida)."""
    pre = []
    if lut_path:
        lp = lut_path.replace("\\", "/").replace(":", "\\:")
        pre.append(f"lut3d=file='{lp}':interp=tetrahedral")
    if vignette and vignette > 0:
        pre.append("vignette=angle=PI/5")
    if grain and grain > 0:
        pre.append(f"noise=alls={max(1, int(grain * 120))}:allf=t")
    pre_str = ",".join(pre) if pre else "null"

    graph = [f"[0:v]{pre_str}[graded]"]

    target = ASPECTS.get(aspect)
    if target:
        w, h = target
        graph.append(f"[graded]{_reframe_chain(w, h, fit)}[ref]")
    else:
        graph.append("[graded]null[ref]")

    post = []
    if sharpen and sharpen > 0:
        post.append(f"unsharp=5:5:{sharpen:.2f}:5:5:0.0")
    post.append("format=yuv420p")
    graph.append(f"[ref]{','.join(post)}[styled]")

    out_w, out_h = (target if target else out_size)

    if watermark and has_logo:
        wm = watermark
        scale = wm.get("scale", 0.18)
        margin = int(out_w * wm.get("margin", 0.04))
        lw = max(1, int(out_w * scale))
        opacity = wm.get("opacity", 0.85)
        xexpr, yexpr = _POS.get(wm.get("position", "br"), _POS["br"])
        xexpr = xexpr.format(m=margin)
        yexpr = yexpr.format(m=margin)
        graph.append(
            f"[1:v]scale={lw}:-1,format=rgba,"
            f"colorchannelmixer=aa={opacity}[lg]")
        graph.append(f"[styled][lg]overlay={xexpr}:{yexpr}[v]")
    elif watermark and watermark.get("text"):
        wm = watermark
        fs = max(12, int(out_h * wm.get("scale", 0.05)))
        margin = int(out_w * wm.get("margin", 0.04))
        opacity = wm.get("opacity", 0.85)
        text = wm["text"].replace(":", "\\:").replace("'", "")
        # drawtext usa text_w/text_h para posicionar.
        pos_map = {
            "br": (f"w-text_w-{margin}", f"h-text_h-{margin}"),
            "bl": (f"{margin}", f"h-text_h-{margin}"),
            "tr": (f"w-text_w-{margin}", f"{margin}"),
            "tl": (f"{margin}", f"{margin}"),
            "center": ("(w-text_w)/2", "(h-text_h)/2"),
        }
        xx, yy = pos_map.get(wm.get("position", "br"), pos_map["br"])
        font = wm.get("font") or _default_font()
        fontarg = f"fontfile='{font}':" if font else ""
        graph.append(
            f"[styled]drawtext={fontarg}text='{text}':"
            f"fontcolor=white@{opacity}:fontsize={fs}:"
            f"shadowcolor=black@0.6:shadowx=2:shadowy=2:x={xx}:y={yy}[v]")
    else:
        graph.append("[styled]null[v]")

    return ";".join(graph), "[v]"


def _default_font() -> str | None:
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf",
              "C:/Windows/Fonts/arialbd.ttf"):
        if os.path.exists(f):
            return f
    return None


def process_video(in_path: str, out_path: str, *, lut_path: str | None = None,
                  aspect: str = "keep", fit: str = "crop",
                  watermark: dict | None = None, crf: int = 18,
                  x264_preset: str = "medium", sharpen: float = 0.5,
                  vignette: float = 0.0, grain: float = 0.0,
                  trim: tuple | None = None) -> None:
    """Procesa un video y lo guarda como MP4 (H.264 + AAC)."""
    info = ff.probe(in_path)
    has_logo = bool(watermark and watermark.get("logo"))

    fc, out_label = build_filter_complex(
        aspect, fit, lut_path, sharpen, vignette, grain,
        (info["width"], info["height"]), watermark, has_logo)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    cmd = [ff.ffmpeg_exe(), "-y"]
    if trim:
        cmd += ["-ss", f"{trim[0]:.3f}"]
    cmd += ["-i", in_path]
    if has_logo:
        cmd += ["-i", watermark["logo"]]
    if trim:
        cmd += ["-t", f"{max(0.1, trim[1] - trim[0]):.3f}"]

    cmd += ["-filter_complex", fc, "-map", out_label]
    if info["has_audio"]:
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", x264_preset,
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]

    ff.run(cmd)
