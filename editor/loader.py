"""Carga y guardado de imagenes (RAW de Sony y JPEG/PNG)."""

from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageOps

# Extensiones RAW habituales (Sony usa .ARW).
RAW_EXTS = {
    ".arw", ".sr2", ".srf",          # Sony
    ".cr2", ".cr3", ".nef", ".raf",  # otras marcas, por si acaso
    ".rw2", ".orf", ".dng", ".pef",
}
JPEG_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}

SUPPORTED_EXTS = RAW_EXTS | JPEG_EXTS


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXTS


def is_raw(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in RAW_EXTS


def load_image(path: str) -> np.ndarray:
    """Devuelve un array float32 RGB en rango [0, 1], gamma sRGB.

    Para RAW se hace el demosaico con balance de blancos de camara y SIN
    auto-brillo, para que el resultado sea consistente entre fotos y sea
    nuestra tuberia la que controle exposicion y color.
    """
    if is_raw(path):
        return _load_raw(path)
    return _load_ldr(path)


def _load_raw(path: str) -> np.ndarray:
    import rawpy  # import perezoso: solo se necesita para RAW

    with rawpy.imread(path) as raw:
        rgb16 = raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=True,
            output_bps=16,
            gamma=(2.222, 4.5),          # curva sRGB estandar
            output_color=rawpy.ColorSpace.sRGB,
            highlight_mode=rawpy.HighlightMode.Clip,
        )
    return (rgb16.astype(np.float32) / 65535.0)


def _load_ldr(path: str) -> np.ndarray:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)   # respeta la orientacion EXIF
        im = im.convert("RGB")
        arr = np.asarray(im, dtype=np.float32) / 255.0
    return arr


def load_thumb(path: str, max_size: int = 1024) -> np.ndarray:
    """Carga rapida y reducida para analisis (culling). Para RAW decodifica
    a media resolucion, mucho mas rapido que la calidad completa."""
    if is_raw(path):
        import rawpy

        with rawpy.imread(path) as raw:
            rgb8 = raw.postprocess(
                use_camera_wb=True, no_auto_bright=True,
                half_size=True, output_bps=8,
                output_color=rawpy.ColorSpace.sRGB)
        im = Image.fromarray(rgb8, mode="RGB")
    else:
        im = Image.open(path)
        im = ImageOps.exif_transpose(im).convert("RGB")

    long_edge = max(im.size)
    if long_edge > max_size:
        scale = max_size / float(long_edge)
        im = im.resize((max(1, int(im.width * scale)),
                        max(1, int(im.height * scale))), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32) / 255.0


def read_capture_time(path: str):
    """Devuelve el timestamp EXIF de captura (float) o None."""
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            for tag in (36867, 36868, 306):  # DateTimeOriginal/Digitized/DateTime
                val = exif.get(tag)
                if val:
                    import time as _t
                    return _t.mktime(_t.strptime(str(val), "%Y:%m:%d %H:%M:%S"))
    except Exception:
        pass
    return None


def to_pil(arr: np.ndarray) -> Image.Image:
    """Convierte un array float [0,1] a una imagen PIL de 8 bits."""
    arr = np.clip(arr, 0.0, 1.0)
    return Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8), mode="RGB")


def save_jpeg(im: Image.Image, path: str, quality: int = 90) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    im.save(
        path,
        format="JPEG",
        quality=int(quality),
        optimize=True,
        progressive=True,
        subsampling=1,           # 4:2:2, buen equilibrio para redes
        icc_profile=None,
    )
