"""Generate AgriGPT PWA icons: flat leaf sprout on onyx (Mercury branding).

Full-bleed onyx square with the glyph inside the maskable safe zone (center
~62%), so one file serves both `any` and `maskable` purposes.
"""
from PIL import Image, ImageDraw

ONYX = (34, 197, 94, 255)      # #22c55e leaf tile (light-theme brand)
LEAF = (255, 255, 255, 255)    # white glyph
OUT = "../frontend/public"

SS = 4  # supersample factor for smooth edges


def make_icon(size: int) -> Image.Image:
    w = size * SS
    img = Image.new("RGBA", (w, w), ONYX)

    # --- glyph geometry in unit space, scaled to the maskable safe zone ---
    # Safe zone: central 62% => glyph spans 0.19..0.81 of the canvas.
    pad = 0.19 * w
    gw = w - 2 * pad

    # Stem: rounded vertical bar from bottom-center of the glyph box.
    stem_w = 0.075 * gw
    stem_h = 0.52 * gw
    stem_x = w / 2 - stem_w / 2
    stem_y = pad + gw - 0.06 * gw - stem_h
    img.paste(LEAF, (round(stem_x), round(stem_y), round(stem_x + stem_w), round(stem_y + stem_h)))

    # Left leaf: circle clipped to a leaf-ish lens via mask.
    def leaf(cx, cy, r, squash):
        m = Image.new("L", (w, w), 0)
        d = ImageDraw.Draw(m)
        d.ellipse(
            (cx - r, cy - r * squash, cx + r, cy + r * squash),
            fill=255,
        )
        return m

    r = 0.26 * gw
    left = leaf(pad + r * 0.9, pad + gw * 0.40, r, 0.62)
    right = leaf(pad + gw - r * 0.9, pad + gw * 0.28, r * 0.82, 0.62)

    green = Image.new("RGBA", (w, w), LEAF)
    img.paste(green, (0, 0), left)
    img.paste(green, (0, 0), right)

    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    for s in (192, 512):
        make_icon(s).save(f"{OUT}/icon-{s}.png")
        print(f"wrote {OUT}/icon-{s}.png")
