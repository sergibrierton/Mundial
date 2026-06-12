"""Marca de agua: logo PNG (con transparencia) o texto."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

_POSITIONS = {"br", "bl", "tr", "tl", "center"}


def _xy(pos, base_w, base_h, mark_w, mark_h, margin_px):
    if pos == "br":
        return base_w - mark_w - margin_px, base_h - mark_h - margin_px
    if pos == "bl":
        return margin_px, base_h - mark_h - margin_px
    if pos == "tr":
        return base_w - mark_w - margin_px, margin_px
    if pos == "tl":
        return margin_px, margin_px
    return (base_w - mark_w) // 2, (base_h - mark_h) // 2  # center


def apply_logo(im: Image.Image, logo_path: str, scale: float = 0.18,
               opacity: float = 0.85, position: str = "br",
               margin: float = 0.035) -> Image.Image:
    """Pega un logo PNG escalado a `scale` (fraccion del ancho)."""
    base = im.convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")

    target_w = max(1, int(base.width * scale))
    ratio = target_w / logo.width
    logo = logo.resize((target_w, max(1, int(logo.height * ratio))),
                       Image.LANCZOS)

    if opacity < 1.0:
        alpha = logo.split()[3].point(lambda a: int(a * opacity))
        logo.putalpha(alpha)

    margin_px = int(base.width * margin)
    x, y = _xy(position, base.width, base.height,
               logo.width, logo.height, margin_px)
    base.alpha_composite(logo, (x, y))
    return base.convert("RGB")


def apply_text(im: Image.Image, text: str, scale: float = 0.045,
               opacity: float = 0.85, position: str = "br",
               margin: float = 0.035, font_path: str | None = None,
               color=(255, 255, 255)) -> Image.Image:
    """Marca de agua de texto (si no hay logo). `scale` = altura relativa."""
    base = im.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(10, int(base.height * scale))
    font = None
    for candidate in filter(None, [font_path,
                                   "DejaVuSans-Bold.ttf",
                                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]):
        try:
            font = ImageFont.truetype(candidate, font_size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin_px = int(base.width * margin)
    x, y = _xy(position, base.width, base.height, tw, th, margin_px)
    y -= bbox[1]

    a = int(255 * opacity)
    # sombra sutil para que se lea sobre cualquier fondo
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, int(a * 0.6)))
    draw.text((x, y), text, font=font, fill=(*color, a))

    return Image.alpha_composite(base, overlay).convert("RGB")
