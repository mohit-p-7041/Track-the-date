"""Draw the home-screen icon, once, and write every size the app links to.

    python scripts/make_icons.py

The outputs are committed, so this only needs running if the mark changes. It
exists rather than a checked-in binary with no source because in eighteen
months "where did this PNG come from" has an answer.

Why an icon at all: an iPad told to Add to Home Screen with no
`apple-touch-icon` uses a *screenshot of the page* as the button. Ten icons on
ten iPads, each a different blurry screenshot, none of them recognisable at a
glance — and the whole point of the home-screen button is that someone taps it
without reading anything.

The mark is the same coffee cup as the header (`#i-cup` in base.html), drawn
here with Pillow because there is no build step to run an SVG through — Pillow
is already a dependency for the photo pipeline. Two deliberate differences from
the inline glyph: a heavier stroke, because 1.75/24 disappears at 60 physical
pixels, and no rounded corners on the tile, because iOS masks its own and a
pre-rounded tile ends up rounded twice.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "static" / "icons"

FORECOURT = (0, 105, 60)      # --forecourt, the green in app.css
WHITE = (255, 255, 255, 255)

VIEWBOX = 24                  # the sprite's coordinate space, kept so the
S = 64                        # drawing below reads like the SVG path
STROKE = 1.9                  # heavier than the glyph's 1.75 — see the docstring
MARK_FRACTION = 0.62          # how much of the tile the cup fills

# Every size something asks for. 180 is what iOS wants for apple-touch-icon;
# 192 and 512 are the manifest's, for Android's Add to Home Screen; 32 is the
# browser tab on the laptop.
PNG_SIZES = (32, 180, 192, 512)
ICO_SIZES = (16, 32, 48, 64, 128, 256)   # the Windows desktop shortcut


def draw_mark() -> Image.Image:
    """The cup, white on transparent, cropped to its ink."""
    size = VIEWBOX * S
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = round(STROKE * S)

    def u(*vals: float) -> tuple[float, ...]:
        return tuple(v * S for v in vals)

    # Body: M4 8 h11 v5 a5 5 0 0 1-5 5 H9 a5 5 0 0 1-5-5 Z
    d.rounded_rectangle(
        u(4, 8, 15, 18), radius=5 * S, outline=WHITE, width=w,
        corners=(False, False, True, True),
    )
    # Handle: M15 8.5 h2 a3 3 0 0 1 0 6 h-2. A wider loop than the glyph's 2.5
    # radius, or a stroke this heavy closes the hole up into a blob.
    d.line([u(15, 8.5), u(17, 8.5)], fill=WHITE, width=w)
    d.line([u(15, 14.5), u(17, 14.5)], fill=WHITE, width=w)
    d.arc(u(14, 8.5, 20, 14.5), start=270, end=90, fill=WHITE, width=w)
    # Steam: M7.5 2v2.5 M11.5 2v2.5 — as capsules, since Pillow has no round
    # cap. Longer than the glyph's, which at this weight came out as two dots.
    for x in (7.5, 11.5):
        d.rounded_rectangle(
            u(x - STROKE / 2, 1.5, x + STROKE / 2, 5.5), radius=w / 2, fill=WHITE,
        )

    return layer.crop(layer.getbbox())


def tile(px: int, mark: Image.Image) -> Image.Image:
    """One square icon: the mark centred on solid green, no transparency.

    Flat and full-bleed on purpose. iOS rounds and shades it, Android may mask
    it to a circle, and either only looks right if the artwork runs to the edge.
    """
    img = Image.new("RGB", (px, px), FORECOURT)
    width = round(px * MARK_FRACTION)
    height = round(width * mark.height / mark.width)
    scaled = mark.resize((width, height), Image.LANCZOS)
    img.paste(scaled, ((px - width) // 2, (px - height) // 2), scaled)
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    mark = draw_mark()

    for px in PNG_SIZES:
        path = OUT / f"icon-{px}.png"
        tile(px, mark).save(path, "PNG", optimize=True)
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} KB")

    ico = OUT / "app.ico"
    tile(256, mark).save(ico, sizes=[(n, n) for n in ICO_SIZES])
    print(f"  {ico.relative_to(ROOT)}  {ico.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
