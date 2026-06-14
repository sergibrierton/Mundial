"""Localizacion de ffmpeg/ffprobe y sondeo (probe) de archivos de video."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

_FFMPEG = None
_FFPROBE = None

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mts", ".m2ts", ".mkv", ".mxf"}


def is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


def ffmpeg_exe() -> str:
    """Devuelve la ruta a ffmpeg (del sistema o el incluido con imageio-ffmpeg)."""
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    exe = shutil.which("ffmpeg")
    if not exe:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:  # noqa: BLE001
            exe = None
    if not exe:
        raise RuntimeError(
            "No se encontro ffmpeg. Instalalo (https://ffmpeg.org) o "
            "ejecuta: pip install imageio-ffmpeg")
    _FFMPEG = exe
    return exe


def ffprobe_exe() -> str | None:
    """ffprobe del sistema si existe (si no, se sondea con ffmpeg)."""
    global _FFPROBE
    if _FFPROBE is not None:
        return _FFPROBE or None
    _FFPROBE = shutil.which("ffprobe") or ""
    return _FFPROBE or None


def probe(path: str) -> dict:
    """Informacion del video: duration, width, height, fps, has_audio, rotation."""
    fp = ffprobe_exe()
    if fp:
        return _probe_ffprobe(fp, path)
    return _probe_ffmpeg(path)


def _probe_ffprobe(fp: str, path: str) -> dict:
    cmd = [fp, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    data = json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 25.0,
            "has_audio": False, "rotation": 0}
    info["duration"] = float(data.get("format", {}).get("duration", 0.0) or 0.0)
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not info["width"]:
            info["width"] = int(s.get("width", 0))
            info["height"] = int(s.get("height", 0))
            fr = s.get("avg_frame_rate") or s.get("r_frame_rate") or "25/1"
            info["fps"] = _parse_fps(fr)
            info["rotation"] = _rotation(s)
        elif s.get("codec_type") == "audio":
            info["has_audio"] = True
    return info


def _probe_ffmpeg(path: str) -> dict:
    """Sondeo parseando la salida de `ffmpeg -i` (cuando no hay ffprobe)."""
    out = subprocess.run([ffmpeg_exe(), "-i", path],
                         capture_output=True, text=True).stderr
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 25.0,
            "has_audio": False, "rotation": 0}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    if m:
        h, mi, s = m.groups()
        info["duration"] = int(h) * 3600 + int(mi) * 60 + float(s)
    m = re.search(r"Video:.* (\d{2,5})x(\d{2,5})", out)
    if m:
        info["width"], info["height"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?) fps", out)
    if m:
        info["fps"] = float(m.group(1))
    info["has_audio"] = "Audio:" in out
    m = re.search(r"rotate\s*:\s*(\d+)", out)
    if m:
        info["rotation"] = int(m.group(1))
    return info


def _parse_fps(fr: str) -> float:
    try:
        if "/" in fr:
            n, d = fr.split("/")
            return float(n) / float(d) if float(d) else 25.0
        return float(fr)
    except (ValueError, ZeroDivisionError):
        return 25.0


def _rotation(stream: dict) -> int:
    tags = stream.get("tags", {})
    if "rotate" in tags:
        try:
            return int(tags["rotate"]) % 360
        except ValueError:
            pass
    for sd in stream.get("side_data_list", []):
        if "rotation" in sd:
            try:
                return int(-float(sd["rotation"])) % 360
            except (ValueError, TypeError):
                pass
    return 0


def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    """Ejecuta ffmpeg y lanza excepcion si falla."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-12:])
        raise RuntimeError(f"ffmpeg fallo ({proc.returncode}):\n{tail}")
    return proc
