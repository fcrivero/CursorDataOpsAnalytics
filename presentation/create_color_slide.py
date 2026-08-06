#!/usr/bin/env python3
"""Create wordless color-teaching slides from a source image."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

SLIDE_SIZE = (1920, 1080)
PADDING_RATIO = 0.06

COLOR_MAP = {
    "white": "#FFFFFF",
    "black": "#000000",
    "red": "#E53935",
    "orange": "#FB8C00",
    "yellow": "#FDD835",
    "green": "#43A047",
    "blue": "#1E88E5",
    "purple": "#8E24AA",
    "pink": "#EC407A",
    "brown": "#6D4C41",
    "gray": "#9E9E9E",
    "grey": "#9E9E9E",
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def resolve_color(color: str) -> tuple[int, int, int]:
    lowered = color.lower()
    if lowered in COLOR_MAP:
        return hex_to_rgb(COLOR_MAP[lowered])
    if color.startswith("#"):
        return hex_to_rgb(color)
    raise ValueError(f"Unknown color: {color}")


def _motif_palette(bg_rgb: tuple[int, int, int]) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    """Return subtle motif colors that stay harmonious with the slide background."""
    r, g, b = bg_rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    if luminance > 200:
        return (
            (max(0, r - 18), max(0, g - 18), max(0, b - 12)),
            (max(0, r - 28), max(0, g - 28), max(0, b - 20)),
            (max(0, r - 38), max(0, g - 38), max(0, b - 30)),
        )
    if luminance < 55:
        return (
            (min(255, r + 22), min(255, g + 22), min(255, b + 22)),
            (min(255, r + 14), min(255, g + 14), min(255, b + 14)),
            (min(255, r + 8), min(255, g + 8), min(255, b + 8)),
        )
    return (
        (min(255, r + 30), min(255, g + 30), min(255, b + 30)),
        (min(255, r + 18), min(255, g + 18), min(255, b + 18)),
        (max(0, r - 18), max(0, g - 18), max(0, b - 18)),
    )


def _draw_hexagon(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    radius: float,
    color: tuple[int, int, int],
    width: int = 1,
) -> None:
    points = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, outline=color, width=width)


def _draw_hex_grid(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    color: tuple[int, int, int],
    radius: float = 34,
) -> None:
    """Future Foundation-style hex grid."""
    step_x = radius * 1.75
    step_y = radius * math.sqrt(3)
    cols = int(width / step_x) + 3
    rows = int(height / step_y) + 3
    for row in range(rows):
        for col in range(cols):
            cx = col * step_x + (row % 2) * (step_x / 2) - radius
            cy = row * step_y - radius
            _draw_hexagon(draw, cx, cy, radius, color, width=1)


def _draw_corner_web(
    draw: ImageDraw.ImageDraw,
    origin: tuple[float, float],
    angle_deg: float,
    color: tuple[int, int, int],
    accent: tuple[int, int, int],
    size: float = 220,
) -> None:
    """Spider-web motif anchored in a corner."""
    ox, oy = origin
    spokes = 10
    max_radius = size
    for i in range(spokes):
        angle = math.radians(angle_deg + i * (360 / spokes))
        ex = ox + max_radius * math.cos(angle)
        ey = oy + max_radius * math.sin(angle)
        draw.line((ox, oy, ex, ey), fill=color, width=1)

    rings = 5
    for ring in range(1, rings + 1):
        radius = max_radius * ring / rings
        points = []
        for i in range(spokes):
            angle = math.radians(angle_deg + i * (360 / spokes))
            points.append((ox + radius * math.cos(angle), oy + radius * math.sin(angle)))
        for i in range(spokes):
            p1 = points[i]
            p2 = points[(i + 1) % spokes]
            draw.line((p1[0], p1[1], p2[0], p2[1]), fill=accent if ring % 2 else color, width=1)


def _draw_spider_emblem(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    scale: float,
    color: tuple[int, int, int],
) -> None:
    """Minimal spider emblem watermark."""
    body_w = 8 * scale
    body_h = 14 * scale
    draw.ellipse(
        (cx - body_w, cy - body_h, cx + body_w, cy + body_h),
        outline=color,
        width=max(1, int(scale)),
    )
    leg_angles = [-70, -40, -15, 15, 40, 70, 110, 145, 170, 195, 220, 250]
    leg_len = 28 * scale
    for angle in leg_angles:
        rad = math.radians(angle)
        ex = cx + leg_len * math.cos(rad)
        ey = cy + leg_len * math.sin(rad)
        mx = cx + (leg_len * 0.45) * math.cos(rad) + (6 * scale) * math.cos(rad + math.pi / 2)
        my = cy + (leg_len * 0.45) * math.sin(rad) + (6 * scale) * math.sin(rad + math.pi / 2)
        draw.line((cx, cy, mx, my, ex, ey), fill=color, width=max(1, int(scale * 0.8)))


def _draw_comic_burst(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    color: tuple[int, int, int],
    inner_radius: float = 120,
    outer_radius: float = 520,
    rays: int = 36,
) -> None:
    """Soft comic-book radial burst behind the hero."""
    for i in range(rays):
        a1 = math.radians(i * 360 / rays)
        a2 = math.radians((i + 0.45) * 360 / rays)
        points = [
            (cx + inner_radius * math.cos(a1), cy + inner_radius * math.sin(a1)),
            (cx + outer_radius * math.cos(a1), cy + outer_radius * math.sin(a1)),
            (cx + outer_radius * math.cos(a2), cy + outer_radius * math.sin(a2)),
            (cx + inner_radius * math.cos(a2), cy + inner_radius * math.sin(a2)),
        ]
        if i % 2 == 0:
            draw.polygon(points, fill=color)


def _draw_action_swoosh(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    color: tuple[int, int, int],
    width: int = 2,
) -> None:
    if len(points) >= 2:
        draw.line(points, fill=color, width=width, joint="curve")


def draw_superhero_motifs(slide: Image.Image, bg_rgb: tuple[int, int, int]) -> None:
    """Layer subtle superhero motifs that match the center character theme."""
    width, height = slide.size
    draw = ImageDraw.Draw(slide)
    light, medium, strong = _motif_palette(bg_rgb)
    cx, cy = width / 2, height / 2

    _draw_hex_grid(draw, width, height, light, radius=32)

    burst_layer = Image.new("RGBA", slide.size, (0, 0, 0, 0))
    burst_draw = ImageDraw.Draw(burst_layer)
    burst_color = (*light, 90)
    for i in range(28):
        a1 = math.radians(i * 360 / 28)
        a2 = math.radians((i + 0.55) * 360 / 28)
        inner, outer = 140, 560
        points = [
            (cx + inner * math.cos(a1), cy + inner * math.sin(a1)),
            (cx + outer * math.cos(a1), cy + outer * math.sin(a1)),
            (cx + outer * math.cos(a2), cy + outer * math.sin(a2)),
            (cx + inner * math.cos(a2), cy + inner * math.sin(a2)),
        ]
        if i % 2 == 0:
            burst_draw.polygon(points, fill=burst_color)
    slide.paste(burst_layer, (0, 0), burst_layer)

    corners = [
        (0, 0, 45),
        (width, 0, 135),
        (0, height, -45),
        (width, height, -135),
    ]
    for x, y, angle in corners:
        _draw_corner_web(draw, (x, y), angle, medium, strong, size=240)

    emblem_spots = [
        (160, 190, 1.4),
        (width - 160, 190, 1.4),
        (160, height - 190, 1.4),
        (width - 160, height - 190, 1.4),
        (320, height / 2, 1.0),
        (width - 320, height / 2, 1.0),
    ]
    for ex, ey, scale in emblem_spots:
        _draw_spider_emblem(draw, ex, ey, scale, light)

    swooshes = [
        [(80, 420), (260, 380), (420, 430), (560, 520)],
        [(width - 80, 420), (width - 260, 380), (width - 420, 430), (width - 560, 520)],
        [(120, height - 260), (300, height - 220), (480, height - 280)],
        [(width - 120, height - 260), (width - 300, height - 220), (width - 480, height - 280)],
    ]
    for pts in swooshes:
        _draw_action_swoosh(draw, pts, medium, width=2)

    border_inset = 28
    draw.rounded_rectangle(
        (border_inset, border_inset, width - border_inset, height - border_inset),
        radius=18,
        outline=medium,
        width=2,
    )


def create_slide(
    image_path: Path,
    color: str,
    output_path: Path,
    motifs: bool = True,
) -> None:
    bg_rgb = resolve_color(color)
    slide = Image.new("RGB", SLIDE_SIZE, bg_rgb)

    if motifs:
        draw_superhero_motifs(slide, bg_rgb)

    with Image.open(image_path) as source:
        img = source.convert("RGBA")

    pad_w = int(SLIDE_SIZE[0] * PADDING_RATIO)
    pad_h = int(SLIDE_SIZE[1] * PADDING_RATIO)
    max_w = SLIDE_SIZE[0] - 2 * pad_w
    max_h = SLIDE_SIZE[1] - 2 * pad_h

    scale = min(max_w / img.width, max_h / img.height)
    new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    img = img.resize(new_size, Image.Resampling.LANCZOS)

    x = (SLIDE_SIZE[0] - img.width) // 2
    y = (SLIDE_SIZE[1] - img.height) // 2
    slide.paste(img, (x, y), img)
    slide.save(output_path, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a wordless color-teaching slide.")
    parser.add_argument("color", help="Color name (e.g. white) or hex (e.g. #FFFFFF)")
    parser.add_argument(
        "--image",
        default="presentation/source/reference.png",
        help="Path to the source image",
    )
    parser.add_argument(
        "--output",
        help="Output PNG path (default: presentation/colors/<color>.png)",
    )
    parser.add_argument(
        "--no-motifs",
        action="store_true",
        help="Skip superhero background motifs",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"Source image not found: {image_path}")

    color_key = args.color.lower().lstrip("#")
    output_path = Path(args.output or f"presentation/colors/{color_key}.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    create_slide(image_path, args.color, output_path, motifs=not args.no_motifs)
    print(f"Created slide: {output_path}")


if __name__ == "__main__":
    main()
