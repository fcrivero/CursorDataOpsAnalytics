#!/usr/bin/env python3
"""Create wordless color-teaching slides from a source image."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

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


def create_slide(image_path: Path, color: str, output_path: Path) -> None:
    bg_rgb = resolve_color(color)
    slide = Image.new("RGB", SLIDE_SIZE, bg_rgb)

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
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"Source image not found: {image_path}")

    color_key = args.color.lower().lstrip("#")
    output_path = Path(args.output or f"presentation/colors/{color_key}.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    create_slide(image_path, args.color, output_path)
    print(f"Created slide: {output_path}")


if __name__ == "__main__":
    main()
