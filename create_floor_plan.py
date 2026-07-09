#!/usr/bin/env python3
"""Beautify pharmacy/PVZ zones and labels on top of the original floor plan."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

SOURCE = Path("/workspace/original_page.png")
SCALE = 2

PHARMACY = np.array([198, 232, 196], dtype=np.uint8)
PHARMACY_DEEP = np.array([129, 199, 132], dtype=np.uint8)
PVZ = np.array([187, 222, 251], dtype=np.uint8)
PVZ_DEEP = np.array([144, 202, 249], dtype=np.uint8)
WHITE = np.array([255, 255, 255], dtype=np.uint8)

PHARMACY_ACCENT = (27, 94, 32)
PVZ_ACCENT = (13, 71, 161)
ENTRANCE = (211, 47, 47)
ENTRANCE_LIGHT = (255, 235, 238)
TEXT_DARK = (33, 37, 41)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def scale_box(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return tuple(v * SCALE for v in box)


def classify_pixels(arr: np.ndarray):
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    black = (r < 70) & (g < 70) & (b < 70)
    green_fill = (g > 150) & (r < 120) & (b < 120) & ~black
    blue_fill = (
        (b > 180)
        & (g > 150)
        & (r > 100)
        & (r < 200)
        & ~black
        & ~green_fill
    )
    return black, green_fill, blue_fill


def fill_box(result: np.ndarray, box: tuple[int, int, int, int], color: np.ndarray):
    x0, y0, x1, y1 = box
    result[y0:y1, x0:x1] = color


def apply_zone_gradient(result: np.ndarray, mask: np.ndarray, base: np.ndarray, deep: np.ndarray):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    height = max(y1 - y0, 1)
    width = max(x1 - x0, 1)
    for y in range(y0, y1 + 1):
        row_mask = mask[y]
        if not row_mask.any():
            continue
        ty = (y - y0) / height
        for x in range(x0, x1 + 1):
            if not mask[y, x]:
                continue
            tx = (x - x0) / width
            blend = 0.18 * ty + 0.10 * tx
            color = base * (1 - blend) + deep * blend
            result[y, x] = color.astype(np.uint8)


def beautify_original(source: Path) -> Image.Image:
    original = Image.open(source).convert("RGB")
    if SCALE != 1:
        original = original.resize(
            (original.width * SCALE, original.height * SCALE),
            Image.Resampling.LANCZOS,
        )

    arr = np.array(original)
    result = arr.copy()
    black, green_fill, blue_fill = classify_pixels(arr)

    # Replace only zone fills; walls and geometry stay from the source image.
    result[green_fill] = PHARMACY
    result[blue_fill] = PVZ
    apply_zone_gradient(result, green_fill, PHARMACY, PHARMACY_DEEP)
    apply_zone_gradient(result, blue_fill, PVZ, PVZ_DEEP)

    # Remove old handwritten labels and arrows, then restore walls outside those areas.
    text_mask = np.zeros(arr.shape[:2], dtype=bool)
    clear_regions = [
        scale_box((0, 100, 240, 960)),       # left entrance text + arrow
        scale_box((380, 380, 860, 490)),     # old "Аптека"
        scale_box((1030, 390, 1220, 470)),   # old "ПВЗ"
        scale_box((1270, 160, 1666, 730)),   # right entrance text + arrow
    ]
    for box in clear_regions:
        x0, y0, x1, y1 = box
        text_mask[y0:y1, x0:x1] = True

    green_box = scale_box((210, 231, 902, 561))
    blue_box = scale_box((933, 230, 1246, 972))

    def paint_clear_region(box, color):
        x0, y0, x1, y1 = box
        region = text_mask[y0:y1, x0:x1].copy()
        result[y0:y1, x0:x1][region] = color

    paint_clear_region(green_box, PHARMACY)
    paint_clear_region(blue_box, PVZ)
    fill_box(result, scale_box((0, 100, 240, 960)), WHITE)
    fill_box(result, scale_box((1270, 160, 1666, 730)), WHITE)

    wall_mask = black & ~text_mask
    result[wall_mask] = arr[wall_mask]

    img = Image.fromarray(result)
    draw = ImageDraw.Draw(img)

    font_zone = load_font(34 * SCALE, bold=True)
    font_ent_title = load_font(22 * SCALE, bold=True)
    font_ent_sub = load_font(16 * SCALE)

    def zone_badge(center, title, accent, fill):
        cx, cy = center
        pad_x, pad_y = 18 * SCALE, 10 * SCALE
        bbox = draw.textbbox((0, 0), title, font=font_zone)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        box = (
            cx - tw // 2 - pad_x,
            cy - th // 2 - pad_y,
            cx + tw // 2 + pad_x,
            cy + th // 2 + pad_y,
        )
        draw.rounded_rectangle(box, radius=14 * SCALE, fill=(255, 255, 255), outline=accent, width=3 * SCALE)
        draw.text((cx, cy), title, fill=accent, font=font_zone, anchor="mm")

    zone_badge((560 * SCALE, 395 * SCALE), "АПТЕКА", PHARMACY_ACCENT, PHARMACY)
    zone_badge((1080 * SCALE, 360 * SCALE), "ПВЗ", PVZ_ACCENT, PVZ)

    def entrance_label(text, anchor, direction):
        x, y = anchor
        pad_x, pad_y = 16 * SCALE, 12 * SCALE
        sub = "Вход"
        bbox_t = draw.textbbox((0, 0), text, font=font_ent_title)
        bbox_s = draw.textbbox((0, 0), sub, font=font_ent_sub)
        tw = max(bbox_t[2] - bbox_t[0], bbox_s[2] - bbox_s[0])
        th = (bbox_t[3] - bbox_t[1]) + (bbox_s[3] - bbox_s[1]) + 6 * SCALE
        bw = tw + pad_x * 2 + 42 * SCALE
        bh = th + pad_y * 2

        if direction == "left":
            bx0, by0, bx1, by1 = x - bw, y - bh // 2, x, y + bh // 2
            tip = (bx1 + 28 * SCALE, y)
            base = (bx1 + 6 * SCALE, y)
            arrow = [(tip[0], tip[1]), (tip[0] - 14 * SCALE, tip[1] - 8 * SCALE), (tip[0] - 14 * SCALE, tip[1] + 8 * SCALE)]
        else:
            bx0, by0, bx1, by1 = x, y - bh // 2, x + bw, y + bh // 2
            tip = (bx0 - 28 * SCALE, y)
            base = (bx0 - 6 * SCALE, y)
            arrow = [(tip[0], tip[1]), (tip[0] + 14 * SCALE, tip[1] - 8 * SCALE), (tip[0] + 14 * SCALE, tip[1] + 8 * SCALE)]

        draw.rounded_rectangle(
            (bx0, by0, bx1, by1),
            radius=14 * SCALE,
            fill=ENTRANCE_LIGHT,
            outline=ENTRANCE,
            width=3 * SCALE,
        )
        icon_cx = bx0 + 24 * SCALE
        icon_cy = (by0 + by1) // 2
        draw.rounded_rectangle(
            (icon_cx - 12 * SCALE, icon_cy - 14 * SCALE, icon_cx + 12 * SCALE, icon_cy + 14 * SCALE),
            5 * SCALE,
            fill=ENTRANCE,
        )
        draw.ellipse(
            (icon_cx - 3 * SCALE, icon_cy - 3 * SCALE, icon_cx + 3 * SCALE, icon_cy + 3 * SCALE),
            fill=(255, 255, 255),
        )
        tx = bx0 + 46 * SCALE
        ty = by0 + pad_y - 2 * SCALE
        draw.text((tx, ty), sub, fill=ENTRANCE, font=font_ent_sub)
        draw.text((tx, ty + 20 * SCALE), text, fill=TEXT_DARK, font=font_ent_title)
        draw.line((base[0], base[1], tip[0], tip[1]), fill=ENTRANCE, width=4 * SCALE)
        draw.polygon(arrow, fill=ENTRANCE)

    entrance_label("с улицы Киевская", (340 * SCALE, 420 * SCALE), "left")
    entrance_label("со двора", (1360 * SCALE, 420 * SCALE), "right")

    return img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=70, threshold=2))


def save_pdf(image: Image.Image, output_path: Path) -> None:
    page_w = image.width * 72 / 200
    page_h = image.height * 72 / 200
    c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))
    c.setTitle("Планировка — Аптека и ПВЗ")

    tmp_png = output_path.with_suffix(".png")
    image.save(tmp_png, "PNG", dpi=(200, 200))
    c.drawImage(ImageReader(str(tmp_png)), 0, 0, width=page_w, height=page_h)
    c.showPage()
    c.save()


def main():
    output_pdf = Path("/workspace/Планировка_аптека_ПВЗ.pdf")
    img = beautify_original(SOURCE)
    img.save("/workspace/Планировка_аптека_ПВЗ.png", "PNG")
    save_pdf(img, output_pdf)
    print(f"Saved: {output_pdf}")
    print(f"Saved: /workspace/Планировка_аптека_ПВЗ.png")


if __name__ == "__main__":
    main()
