"""Draws the Desktop Friend puppy app icons (same proportions as src/components/Puppy.tsx).

    python scripts/generate-icons.py      (needs Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SS = 4  # supersampling for smooth edges

FUR, PATCH, EAR, MUZZLE, NOSE = "#F6D7B0", "#C98F5E", "#B47A4C", "#FFF4E6", "#3B2A2A"
BLUSH, BLUE, BG1, BG2 = (255, 120, 150, 120), "#2F7BFF", "#DCE8FF", "#B9D0FF"


def puppy_face(size: int, scale: float = 1.0, mono: bool = False) -> Image.Image:
    """Head-only puppy centred in a transparent square. `scale` shrinks it for adaptive-icon safe zones."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = S * scale  # unit
    ox = (S - u) / 2
    oy = (S - u) / 2 + u * 0.04

    def r(x, y, w, h):
        return [ox + x * u, oy + y * u, ox + (x + w) * u, oy + (y + h) * u]

    def col(c):
        return "white" if mono else c

    # head
    d.rounded_rectangle(r(0.12, 0.14, 0.76, 0.66), radius=0.33 * u, fill=col(FUR))
    if not mono:
        d.ellipse(r(0.56, 0.3, 0.22, 0.22), fill=PATCH)
        d.rounded_rectangle(r(0.33, 0.47, 0.34, 0.23), radius=0.115 * u, fill=MUZZLE)
        d.ellipse(r(0.205, 0.53, 0.11, 0.06), fill=BLUSH)
        d.ellipse(r(0.685, 0.53, 0.11, 0.06), fill=BLUSH)
        for cx in (0.375, 0.625):
            d.ellipse(r(cx - 0.055, 0.36, 0.11, 0.11), fill=NOSE)
            d.ellipse(r(cx - 0.0, 0.375, 0.04, 0.04), fill="white")
        d.rounded_rectangle(r(0.445, 0.48, 0.11, 0.075), radius=0.035 * u, fill=NOSE)
        d.ellipse(r(0.465, 0.49, 0.03, 0.02), fill=(255, 255, 255, 140))
        w = max(2, int(0.014 * u))
        d.arc(r(0.43, 0.52, 0.075, 0.06), start=10, end=170, fill=NOSE, width=w)
        d.arc(r(0.495, 0.52, 0.075, 0.06), start=10, end=170, fill=NOSE, width=w)
    else:
        # cut-out eyes and nose so the silhouette still reads as a face
        for cx in (0.375, 0.625):
            d.ellipse(r(cx - 0.055, 0.36, 0.11, 0.11), fill=(0, 0, 0, 0))
        d.rounded_rectangle(r(0.445, 0.48, 0.11, 0.075), radius=0.035 * u, fill=(0, 0, 0, 0))
    # floppy ears (rotated rounded rects)
    for x, angle in ((0.02, -16), (0.73, 16)):
        ear = Image.new("RGBA", (int(0.25 * u), int(0.44 * u)), (0, 0, 0, 0))
        ImageDraw.Draw(ear).rounded_rectangle([0, 0, ear.width - 1, ear.height - 1], radius=0.12 * u, fill=col(EAR))
        ear = ear.rotate(angle, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(ear, (int(ox + x * u - (ear.width - 0.25 * u) / 2), int(oy + 0.12 * u)))
    if not mono:
        d.rounded_rectangle(r(0.3, 0.79, 0.4, 0.06), radius=0.03 * u, fill=BLUE)
        d.ellipse(r(0.47, 0.815, 0.06, 0.06), fill="#FFC94D", outline="#E0A800", width=max(1, int(0.006 * u)))
    return img.resize((size, size), Image.LANCZOS)


def gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BG1)
    top, bottom = Image.new("RGB", (1, 2)), None
    top.putpixel((0, 0), tuple(int(BG1[i : i + 2], 16) for i in (1, 3, 5)))
    top.putpixel((0, 1), tuple(int(BG2[i : i + 2], 16) for i in (1, 3, 5)))
    return top.resize((size, size), Image.BICUBIC)


def main() -> None:
    size = 1024
    icon = gradient(size).convert("RGBA")
    icon.alpha_composite(puppy_face(size, 0.86))
    icon.convert("RGB").save(ASSETS / "icon.png")
    # Android adaptive icon: foreground must stay inside the central 66% safe zone
    puppy_face(size, 0.62).save(ASSETS / "android-icon-foreground.png")
    gradient(size).save(ASSETS / "android-icon-background.png")
    puppy_face(size, 0.62, mono=True).save(ASSETS / "android-icon-monochrome.png")
    fav = gradient(48).convert("RGBA")
    fav.alpha_composite(puppy_face(48, 0.9))
    fav.save(ASSETS / "favicon.png")
    print("icons written to", ASSETS)


if __name__ == "__main__":
    main()
