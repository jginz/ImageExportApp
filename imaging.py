"""Pure image helpers: display window, merge, ROI crop, scale bar. No GUI imports."""
import math
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


def apply_window(img, lo, hi):
    """Stretch lo..hi to 0..255 on an RGB image. hi <= lo is treated as lo + 1."""
    lo = max(0, min(254, int(lo)))
    hi = max(lo + 1, min(255, int(hi)))
    lut = [max(0, min(255, round((v - lo) / (hi - lo) * 255))) for v in range(256)]
    return img.convert("RGB").point(lut * 3)


def composite(channels):
    """Additive merge of RGB channel images, clipped at 255."""
    if not channels:
        return Image.new("RGB", (1, 1))
    out = channels[0].convert("RGB")
    for c in channels[1:]:
        out = ImageChops.add(out, c.convert("RGB"))
    return out


def clamp_roi(roi):
    """Keep a square (x, y, size) ROI, given as fractions of the width, inside the image."""
    x, y, s = roi
    s = max(0.0, min(1.0, s))
    return (max(0.0, min(1.0 - s, x)), max(0.0, min(1.0 - s, y)), s)


def crop_roi(img, roi):
    if roi is None:
        return img
    x, y, s = clamp_roi(roi)
    w, h = img.size
    px, py, ps = round(x * w), round(y * h), max(1, round(s * w))
    return img.crop((px, py, min(w, px + ps), min(h, py + ps)))


def parse_um_per_pixel(txt_path):
    """Read 'N [um/pixel]' from the "X Dimension" line of the scope's sidecar text file."""
    try:
        text = Path(txt_path).read_text(errors="ignore")
    except OSError:
        return None
    for line in text.splitlines():
        if "X Dimension" in line:
            m = re.search(r"([\d.]+)\s*\[um/pixel\]", line)
            return float(m.group(1)) if m else None
    return None


def scale_bar_length_um(um_per_px, width_px):
    """1/2/5 x 10^n micrometres closest to 20% of the image width."""
    target = 0.2 * um_per_px * width_px
    exp = math.floor(math.log10(target))
    cands = [m * 10 ** e for e in (exp - 1, exp, exp + 1) for m in (1, 2, 5)]
    best = min(cands, key=lambda c: abs(c - target))
    return int(best) if best >= 1 else best


def load_font(px, bold=False):
    names = ["Arial Bold.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["Arial.ttf", "arial.ttf", "DejaVuSans.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_scale_bar(img, um_per_px):
    """Return a copy with a white bar and label at the bottom-left."""
    out = img.convert("RGB").copy()
    w, h = out.size
    um = scale_bar_length_um(um_per_px, w)
    bar_px = max(2, round(um / um_per_px))
    bar_h = max(3, h // 120)
    margin = max(6, w // 40)
    font_px = max(10, h // 36)
    font = load_font(font_px)
    d = ImageDraw.Draw(out)
    y1 = h - margin
    d.rectangle((margin, y1 - bar_h, margin + bar_px, y1), fill=(255, 255, 255))
    label = f"{um:g} µm"
    d.text((margin, y1 - bar_h - 4), label, fill=(255, 255, 255), font=font, anchor="ls",
           stroke_width=max(1, font_px // 12), stroke_fill=(0, 0, 0))
    return out
