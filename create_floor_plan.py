#!/usr/bin/env python3
"""Create a polished pharmacy + PVZ floor plan PDF from the source sketch."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# Canvas size (landscape A4 at ~200 dpi)
W, H = 2480, 1754

# Colors
BG = (250, 251, 252)
WALL = (45, 52, 64)
WALL_FILL = (255, 255, 255)
PHARMACY_FILL = (198, 232, 196)
PHARMACY_BORDER = (46, 125, 50)
PHARMACY_ACCENT = (27, 94, 32)
PVZ_FILL = (187, 222, 251)
PVZ_BORDER = (21, 101, 192)
PVZ_ACCENT = (13, 71, 161)
CORRIDOR_FILL = (227, 242, 253)
ENTRANCE = (211, 47, 47)
ENTRANCE_LIGHT = (255, 235, 238)
TEXT_DARK = (33, 37, 41)
TEXT_MUTED = (108, 117, 125)
GRID = (230, 234, 238)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_door(draw, x, y, orientation: str, size: int = 42):
    """Draw a door opening marker."""
    if orientation == "left":
        draw.arc((x, y, x + size, y + size), 0, 90, fill=ENTRANCE, width=4)
        draw.line((x, y + size, x, y), fill=ENTRANCE, width=4)
    elif orientation == "right":
        draw.arc((x - size, y, x, y + size), 90, 180, fill=ENTRANCE, width=4)
        draw.line((x, y + size, x, y), fill=ENTRANCE, width=4)
    elif orientation == "bottom":
        draw.arc((x, y - size, x + size, y), 270, 360, fill=ENTRANCE, width=4)
        draw.line((x, y, x + size, y), fill=ENTRANCE, width=4)


def draw_entrance_label(
    draw,
    text: str,
    anchor: tuple[int, int],
    direction: str,
    font_title,
    font_sub,
):
    x, y = anchor
    pad_x, pad_y = 28, 18
    title = text
    sub = "Вход"

    bbox_t = draw.textbbox((0, 0), title, font=font_title)
    bbox_s = draw.textbbox((0, 0), sub, font=font_sub)
    tw = max(bbox_t[2] - bbox_t[0], bbox_s[2] - bbox_s[0])
    th = (bbox_t[3] - bbox_t[1]) + (bbox_s[3] - bbox_s[1]) + 8
    box_w = tw + pad_x * 2 + 56
    box_h = th + pad_y * 2

    if direction == "left":
        bx0, by0 = x - box_w, y - box_h // 2
        bx1, by1 = x, y + box_h // 2
        arrow_tip = (bx1 + 36, y)
        arrow_base = (bx1 + 8, y)
    elif direction == "right":
        bx0, by0 = x, y - box_h // 2
        bx1, by1 = min(x + box_w, W - 30), y + box_h // 2
        arrow_tip = (bx0 - 36, y)
        arrow_base = (bx0 - 8, y)
    else:
        bx0, by0 = x - box_w // 2, y
        bx1, by1 = x + box_w // 2, y + box_h
        arrow_tip = (x, y - 8)
        arrow_base = (x, y + 8)

    rounded_rect(draw, (bx0, by0, bx1, by1), 18, ENTRANCE_LIGHT, ENTRANCE, 3)

    icon_cx = bx0 + 34
    icon_cy = (by0 + by1) // 2
    draw.rounded_rectangle((icon_cx - 16, icon_cy - 20, icon_cx + 16, icon_cy + 20), 6, fill=ENTRANCE)
    draw.ellipse((icon_cx - 4, icon_cy - 4, icon_cx + 4, icon_cy + 4), fill=(255, 255, 255))

    tx = bx0 + 64
    ty = by0 + pad_y - 2
    draw.text((tx, ty), sub, fill=ENTRANCE, font=font_sub)
    draw.text((tx, ty + 26), title, fill=TEXT_DARK, font=font_title)

    draw.line((arrow_base[0], arrow_base[1], arrow_tip[0], arrow_tip[1]), fill=ENTRANCE, width=5)
    if direction == "left":
        draw.polygon(
            [(arrow_tip[0], arrow_tip[1]), (arrow_tip[0] - 18, arrow_tip[1] - 10), (arrow_tip[0] - 18, arrow_tip[1] + 10)],
            fill=ENTRANCE,
        )
    elif direction == "right":
        draw.polygon(
            [(arrow_tip[0], arrow_tip[1]), (arrow_tip[0] + 18, arrow_tip[1] - 10), (arrow_tip[0] + 18, arrow_tip[1] + 10)],
            fill=ENTRANCE,
        )


def draw_zone_badge(draw, x, y, title, subtitle, fill, accent, font_big, font_small):
    pad = 24
    bbox_t = draw.textbbox((0, 0), title, font=font_big)
    bbox_s = draw.textbbox((0, 0), subtitle, font=font_small)
    tw = max(bbox_t[2] - bbox_t[0], bbox_s[2] - bbox_s[0])
    th = (bbox_t[3] - bbox_t[1]) + (bbox_s[3] - bbox_s[1]) + 10
    bw, bh = tw + pad * 2, th + pad * 2
    rounded_rect(draw, (x - bw // 2, y - bh // 2, x + bw // 2, y + bh // 2), 16, (255, 255, 255, 230), accent, 2)
    draw.text((x - tw // 2, y - th // 2 - 2), title, fill=accent, font=font_big)
    draw.text((x - (bbox_s[2] - bbox_s[0]) // 2, y - th // 2 + 38), subtitle, fill=TEXT_MUTED, font=font_small)


def create_floor_plan() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    font_title = load_font(52, bold=True)
    font_h1 = load_font(44, bold=True)
    font_h2 = load_font(34, bold=True)
    font_body = load_font(28)
    font_small = load_font(24)
    font_zone = load_font(56, bold=True)
    font_zone_sub = load_font(26)

    # Header
    draw.text((120, 70), "Планировка коммерческого помещения", fill=TEXT_DARK, font=font_title)
    draw.text((120, 130), "Аптека и пункт выдачи заказов (ПВЗ)", fill=TEXT_MUTED, font=font_body)
    draw.line((120, 185, W - 120, 185), fill=GRID, width=2)

    # Plan origin and scale (based on source sketch proportions)
    ox, oy = 460, 320
    scale = 1.45
    wall = 14

    def sx(v):
        return ox + v * scale

    def sy(v):
        return oy + v * scale

    # Room geometry traced from source image (relative units)
    outer = (36, 228, 1295, 632)
    apt_left = (210, 231, 554, 561)
    apt_right = (557, 231, 902, 561)
    pvz_main = (905, 228, 1098, 561)
    pvz_lower = (905, 561, 1098, 632)
    corridor = (1248, 228, 1295, 632)

    def rect_rel(r):
        return (sx(r[0]), sy(r[1]), sx(r[2]), sy(r[3]))

    # Subtle floor background
    plan_box = rect_rel(outer)
    rounded_rect(draw, (plan_box[0] - 30, plan_box[1] - 30, plan_box[2] + 30, plan_box[3] + 30), 24, (255, 255, 255), GRID, 2)

    # Zone fills
    for r, fill in [
        (apt_left, PHARMACY_FILL),
        (apt_right, PHARMACY_FILL),
        (pvz_main, PVZ_FILL),
        (pvz_lower, PVZ_FILL),
        (corridor, CORRIDOR_FILL),
    ]:
        x0, y0, x1, y1 = rect_rel(r)
        draw.rectangle((x0 + wall // 2, y0 + wall // 2, x1 - wall // 2, y1 - wall // 2), fill=fill)

    # Internal connection between pvz main and corridor (opening area)
    conn = rect_rel((1098, 228, 1248, 561))
    draw.rectangle((conn[0] + wall // 2, conn[1] + wall // 2, conn[2] - wall // 2, conn[3] - wall // 2), fill=PVZ_FILL)

    # Walls
    def wall_rect(r):
        x0, y0, x1, y1 = rect_rel(r)
        draw.rectangle((x0, y0, x1, y1), fill=WALL_FILL, outline=WALL, width=wall)

    # Outer walls
    x0, y0, x1, y1 = rect_rel(outer)
    draw.rectangle((x0, y0, x1, y1), outline=WALL, width=wall)

    # Internal walls - draw as thick lines
    dividers = [
        ((554, 231), (554, 561)),  # pharmacy split
        ((902, 231), (902, 561)),  # pharmacy / pvz
        ((1098, 231), (1098, 561)),  # pvz internal
        ((1248, 231), (1248, 632)),  # corridor split
        ((905, 561), (1098, 561)),  # horizontal lower pvz
    ]
    for (x_a, y_a), (x_b, y_b) in dividers:
        draw.line((sx(x_a), sy(y_a), sx(x_b), sy(y_b)), fill=WALL, width=wall)

    # Door openings (clear wall segments)
    doors = [
        ((36, 380), (36, 460), "left"),  # Kievskaya entrance
        ((1295, 380), (1295, 460), "right"),  # yard entrance
        ((1098, 480), (1248, 480), "internal"),  # connection to corridor
    ]
    for d in doors:
        if d[2] == "left":
            dx0, dy0, dy1 = sx(d[0][0]), sy(d[0][1]), sy(d[1][1])
            draw.rectangle((dx0 - 2, dy0, dx0 + wall + 8, dy1), fill=PHARMACY_FILL)
            draw_door(draw, dx0 + 8, dy0 + 10, "left", 46)
        elif d[2] == "right":
            dx0, dy0, dy1 = sx(d[0][0]), sy(d[0][1]), sy(d[1][1])
            draw.rectangle((dx0 - wall - 8, dy0, dx0 + 2, dy1), fill=CORRIDOR_FILL)
            draw_door(draw, dx0 - 8, dy0 + 10, "right", 46)

    # Zone labels
    al = rect_rel(apt_left)
    ar = rect_rel(apt_right)
    pm = rect_rel(pvz_main)
    cr = rect_rel(corridor)

    draw_zone_badge(draw, (al[0] + al[2]) // 2, (al[1] + al[3]) // 2, "АПТЕКА", "торговый зал", PHARMACY_FILL, PHARMACY_ACCENT, font_zone, font_zone_sub)
    draw_zone_badge(draw, (ar[0] + ar[2]) // 2, (ar[1] + ar[3]) // 2, "АПТЕКА", "рабочая зона", PHARMACY_FILL, PHARMACY_ACCENT, font_zone, font_zone_sub)
    draw_zone_badge(draw, (pm[0] + pm[2]) // 2, (pm[1] + pm[3]) // 2, "ПВЗ", "пункт выдачи", PVZ_FILL, PVZ_ACCENT, font_zone, font_zone_sub)
    draw.text(((cr[0] + cr[2]) // 2, (cr[1] + cr[3]) // 2), "Коридор", fill=PVZ_ACCENT, font=font_h2, anchor="mm")

    # Entrance labels
    draw_entrance_label(
        draw,
        "с улицы Киевская",
        (sx(36) - 40, sy(420)),
        "left",
        font_h2,
        font_small,
    )
    draw_entrance_label(
        draw,
        "со двора",
        (sx(1295) + 40, sy(420)),
        "right",
        font_h2,
        font_small,
    )

    # Legend
    lx, ly = 120, H - 250
    draw.text((lx, ly - 50), "Обозначения", fill=TEXT_DARK, font=font_h2)
    legend_items = [
        (PHARMACY_FILL, PHARMACY_ACCENT, "Аптека"),
        (PVZ_FILL, PVZ_BORDER, "ПВЗ"),
        (CORRIDOR_FILL, PVZ_BORDER, "Коридор / проход"),
        (ENTRANCE_LIGHT, ENTRANCE, "Вход"),
    ]
    for i, (fill, border, label) in enumerate(legend_items):
        yy = ly + i * 48
        rounded_rect(draw, (lx, yy, lx + 44, yy + 30), 6, fill, border, 2)
        draw.text((lx + 62, yy + 2), label, fill=TEXT_DARK, font=font_body)

    # Footer note
    draw.text((120, H - 70), "Схема составлена на основании исходного эскиза от 09.07.2026", fill=TEXT_MUTED, font=font_small)
    draw.text((W - 120, H - 70), "Масштаб условный", fill=TEXT_MUTED, font=font_small, anchor="rb")

    # Decorative compass
    cx, cy, r = W - 180, 260, 52
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=GRID, width=2)
    draw.line((cx, cy - r + 8, cx, cy + r - 8), fill=TEXT_MUTED, width=2)
    draw.polygon([(cx, cy - r + 8), (cx - 10, cy - r + 28), (cx + 10, cy - r + 28)], fill=ENTRANCE)
    draw.text((cx, cy - r - 18), "С", fill=TEXT_DARK, font=font_small, anchor="mm")

    return img


def save_pdf(image: Image.Image, output_path: Path) -> None:
    page_w, page_h = landscape(A4)
    c = canvas.Canvas(str(output_path), pagesize=landscape(A4))
    c.setTitle("Планировка — Аптека и ПВЗ")

    tmp_png = output_path.with_suffix(".png")
    image.save(tmp_png, "PNG", dpi=(200, 200))

    margin = 18
    avail_w = page_w - 2 * margin
    avail_h = page_h - 2 * margin
    img_ratio = image.width / image.height
    page_ratio = avail_w / avail_h
    if img_ratio > page_ratio:
        draw_w = avail_w
        draw_h = avail_w / img_ratio
    else:
        draw_h = avail_h
        draw_w = avail_h * img_ratio
    x = (page_w - draw_w) / 2
    y = (page_h - draw_h) / 2
    c.drawImage(ImageReader(str(tmp_png)), x, y, width=draw_w, height=draw_h)
    c.showPage()
    c.save()


def main():
    output_pdf = Path("/workspace/Планировка_аптека_ПВЗ.pdf")
    img = create_floor_plan()
    img.save("/workspace/Планировка_аптека_ПВЗ.png", "PNG")
    save_pdf(img, output_pdf)
    print(f"Saved: {output_pdf}")
    print(f"Saved: /workspace/Планировка_аптека_ПВЗ.png")


if __name__ == "__main__":
    main()
