#!/usr/bin/env python3
"""Create wordless color-teaching slides from a source image."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

SLIDE_SIZE = (1920, 1080)
PADDING_RATIO = 0.06

COLOR_MAP = {
    "white": "#FFFFFF",
    "black": "#000000",
    "red": "#E53935",
    "orange": "#F57C00",
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


@dataclass(frozen=True)
class MotifPalette:
    hex_grid: tuple[int, int, int]
    web_primary: tuple[int, int, int]
    web_accent: tuple[int, int, int]
    burst: tuple[int, int, int]
    burst_alpha: int
    emblem: tuple[int, int, int]
    swoosh: tuple[int, int, int]
    hex_width: int = 2
    web_width: int = 2


def _motif_palette(bg_rgb: tuple[int, int, int]) -> MotifPalette:
    """Return motif colors tuned for visibility on the slide background."""
    r, g, b = bg_rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    if luminance > 200:
        return MotifPalette(
            hex_grid=(120, 168, 210),
            web_primary=(130, 130, 138),
            web_accent=(45, 45, 52),
            burst=(196, 200, 208),
            burst_alpha=150,
            emblem=(88, 98, 112),
            swoosh=(70, 70, 78),
            hex_width=2,
            web_width=2,
        )
    if luminance < 55:
        return MotifPalette(
            hex_grid=(110, 150, 190),
            web_primary=(170, 170, 178),
            web_accent=(220, 220, 228),
            burst=(40, 42, 48),
            burst_alpha=120,
            emblem=(150, 158, 170),
            swoosh=(190, 190, 198),
        )
    return MotifPalette(
        hex_grid=(min(255, r + 40), min(255, g + 40), min(255, b + 55)),
        web_primary=(max(0, r - 40), max(0, g - 40), max(0, b - 35)),
        web_accent=(max(0, r - 70), max(0, g - 70), max(0, b - 60)),
        burst=(min(255, r + 25), min(255, g + 25), min(255, b + 25)),
        burst_alpha=130,
        emblem=(max(0, r - 55), max(0, g - 50), max(0, b - 45)),
        swoosh=(max(0, r - 65), max(0, g - 65), max(0, b - 60)),
    )


def _orange_motif_palette() -> MotifPalette:
    """Fantastic Four / Thing palette on orange backgrounds."""
    return MotifPalette(
        hex_grid=(180, 80, 20),
        web_primary=(120, 45, 18),
        web_accent=(45, 22, 12),
        burst=(255, 190, 90),
        burst_alpha=140,
        emblem=(21, 101, 192),
        swoosh=(62, 30, 12),
        hex_width=2,
        web_width=2,
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


def _draw_corner_web(
    draw: ImageDraw.ImageDraw,
    origin: tuple[float, float],
    angle_deg: float,
    color: tuple[int, int, int],
    accent: tuple[int, int, int],
    size: float = 220,
    line_width: int = 1,
) -> None:
    """Spider-web motif anchored in a corner."""
    ox, oy = origin
    spokes = 10
    max_radius = size
    for i in range(spokes):
        angle = math.radians(angle_deg + i * (360 / spokes))
        ex = ox + max_radius * math.cos(angle)
        ey = oy + max_radius * math.sin(angle)
        draw.line((ox, oy, ex, ey), fill=color, width=line_width)

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
            draw.line(
                (p1[0], p1[1], p2[0], p2[1]),
                fill=accent if ring % 2 else color,
                width=line_width,
            )


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


def _draw_action_swoosh(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    color: tuple[int, int, int],
    width: int = 2,
) -> None:
    if len(points) >= 2:
        draw.line(points, fill=color, width=width, joint="curve")


def _draw_hex_grid(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    color: tuple[int, int, int],
    radius: float = 34,
    line_width: int = 1,
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
            _draw_hexagon(draw, cx, cy, radius, color, width=line_width)


def _draw_ff_four_emblem(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    scale: float,
    primary: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> None:
    """Fantastic Four '4' emblem watermark."""
    radius = 22 * scale
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        outline=accent,
        width=max(2, int(2 * scale)),
    )
    draw.ellipse(
        (cx - radius + 4 * scale, cy - radius + 4 * scale, cx + radius - 4 * scale, cy + radius - 4 * scale),
        fill=primary,
    )
    stroke = max(2, int(2 * scale))
    draw.line((cx - 8 * scale, cy - 10 * scale, cx - 8 * scale, cy + 12 * scale), fill=accent, width=stroke)
    draw.line((cx - 8 * scale, cy - 10 * scale, cx + 10 * scale, cy - 10 * scale), fill=accent, width=stroke)
    draw.line((cx - 8 * scale, cy - 1 * scale, cx + 4 * scale, cy - 1 * scale), fill=accent, width=stroke)
    draw.line((cx + 4 * scale, cy - 10 * scale, cx + 4 * scale, cy + 12 * scale), fill=accent, width=stroke)


def _draw_rock_crack_grid(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    color: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> None:
    """Angular rock-plate pattern inspired by The Thing's skin."""
    step = 88
    for row in range(-1, height // step + 2):
        for col in range(-1, width // step + 2):
            x = col * step + (row % 2) * (step // 2)
            y = row * step
            points = [
                (x, y + 12),
                (x + step * 0.55, y),
                (x + step, y + 18),
                (x + step * 0.72, y + step * 0.55),
                (x + step * 0.35, y + step * 0.62),
                (x + 8, y + step * 0.42),
            ]
            draw.polygon(points, outline=color, width=2)
            crack_x = x + step * 0.5
            crack_y = y + step * 0.3
            draw.line(
                (crack_x, crack_y, crack_x + step * 0.2, crack_y + step * 0.15, crack_x + step * 0.1, crack_y + step * 0.35),
                fill=accent,
                width=2,
            )


def _draw_impact_burst(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    color: tuple[int, int, int],
    accent: tuple[int, int, int],
    size: float = 180,
) -> None:
    """Punch-impact starburst for corners."""
    spikes = 8
    for i in range(spikes):
        angle = math.radians(i * 360 / spikes)
        ex = cx + size * math.cos(angle)
        ey = cy + size * math.sin(angle)
        draw.line((cx, cy, ex, ey), fill=color, width=3)
    inner = size * 0.45
    for i in range(spikes):
        angle = math.radians(i * 360 / spikes + 22.5)
        ex = cx + inner * math.cos(angle)
        ey = cy + inner * math.sin(angle)
        draw.line((cx, cy, ex, ey), fill=accent, width=2)
    draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=accent)


def _draw_comic_burst_layer(
    slide: Image.Image,
    palette: MotifPalette,
) -> None:
    width, height = slide.size
    cx, cy = width / 2, height / 2
    burst_layer = Image.new("RGBA", slide.size, (0, 0, 0, 0))
    burst_draw = ImageDraw.Draw(burst_layer)
    burst_color = (*palette.burst, palette.burst_alpha)
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


def draw_spider_motifs(slide: Image.Image, bg_rgb: tuple[int, int, int]) -> None:
    """Layer superhero motifs that match the center character theme."""
    width, height = slide.size
    draw = ImageDraw.Draw(slide)
    palette = _motif_palette(bg_rgb)
    cx, cy = width / 2, height / 2

    _draw_hex_grid(
        draw,
        width,
        height,
        palette.hex_grid,
        radius=32,
        line_width=palette.hex_width,
    )

    burst_layer = Image.new("RGBA", slide.size, (0, 0, 0, 0))
    burst_draw = ImageDraw.Draw(burst_layer)
    burst_color = (*palette.burst, palette.burst_alpha)
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
        _draw_corner_web(
            draw,
            (x, y),
            angle,
            palette.web_primary,
            palette.web_accent,
            size=260,
            line_width=palette.web_width,
        )

    emblem_spots = [
        (160, 190, 1.5),
        (width - 160, 190, 1.5),
        (160, height - 190, 1.5),
        (width - 160, height - 190, 1.5),
        (320, height / 2, 1.1),
        (width - 320, height / 2, 1.1),
    ]
    for ex, ey, scale in emblem_spots:
        _draw_spider_emblem(draw, ex, ey, scale, palette.emblem)

    swooshes = [
        [(80, 420), (260, 380), (420, 430), (560, 520)],
        [(width - 80, 420), (width - 260, 380), (width - 420, 430), (width - 560, 520)],
        [(120, height - 260), (300, height - 220), (480, height - 280)],
        [(width - 120, height - 260), (width - 300, height - 220), (width - 480, height - 280)],
    ]
    for pts in swooshes:
        _draw_action_swoosh(draw, pts, palette.swoosh, width=3)


def draw_thing_motifs(slide: Image.Image) -> None:
    """Fantastic Four / The Thing motifs for orange slides."""
    width, height = slide.size
    draw = ImageDraw.Draw(slide)
    palette = _orange_motif_palette()

    _draw_rock_crack_grid(draw, width, height, palette.hex_grid, palette.web_accent)
    _draw_comic_burst_layer(slide, palette)
    draw = ImageDraw.Draw(slide)

    corners = [
        (90, 90),
        (width - 90, 90),
        (90, height - 90),
        (width - 90, height - 90),
    ]
    for x, y in corners:
        _draw_impact_burst(draw, x, y, palette.web_primary, palette.web_accent, size=170)

    emblem_spots = [
        (170, 200, 1.3),
        (width - 170, 200, 1.3),
        (170, height - 200, 1.3),
        (width - 170, height - 200, 1.3),
        (310, height / 2, 1.0),
        (width - 310, height / 2, 1.0),
    ]
    for ex, ey, scale in emblem_spots:
        _draw_ff_four_emblem(draw, ex, ey, scale, palette.emblem, palette.web_accent)

    swooshes = [
        [(70, 430), (240, 390), (410, 450), (580, 540)],
        [(width - 70, 430), (width - 240, 390), (width - 410, 450), (width - 580, 540)],
        [(100, height - 250), (290, height - 210), (470, height - 270)],
        [(width - 100, height - 250), (width - 290, height - 210), (width - 470, height - 270)],
    ]
    for pts in swooshes:
        _draw_action_swoosh(draw, pts, palette.swoosh, width=4)


def draw_superhero_motifs(slide: Image.Image, bg_rgb: tuple[int, int, int], color: str) -> None:
    if color.lower() == "orange":
        draw_thing_motifs(slide)
    else:
        draw_spider_motifs(slide, bg_rgb)


def create_slide(
    image_path: Path,
    color: str,
    output_path: Path,
    motifs: bool = True,
) -> None:
    bg_rgb = resolve_color(color)
    slide = Image.new("RGB", SLIDE_SIZE, bg_rgb)

    if motifs:
        draw_superhero_motifs(slide, bg_rgb, color)

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
