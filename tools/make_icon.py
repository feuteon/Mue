"""Génère assets/mue.ico et assets/mue.png (icône de l'appli) avec Pillow.
Usage : python tools/make_icon.py"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 1024
OUT = Path(__file__).resolve().parents[1] / "assets"

C1 = (124, 247, 198)   # menthe
C2 = (142, 124, 255)   # violet
C3 = (255, 139, 200)   # rose


def gradient(size: int) -> Image.Image:
    """Dégradé diagonal irisé menthe -> violet -> rose."""
    g = Image.new("RGB", (size, size))
    px = g.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            if t < 0.6:
                u = t / 0.6
                a, b = C1, C2
            else:
                u = (t - 0.6) / 0.4
                a, b = C2, C3
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
    return g


def rounded_mask(size: int, box, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=radius, fill=255)
    return m


def make() -> Image.Image:
    small = gradient(256).resize((S, S), Image.Resampling.BICUBIC)
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    tile.paste(small, (0, 0), rounded_mask(S, (40, 40, S - 40, S - 40), 230))

    # Carte arrière (l'ancienne peau) : blanc translucide
    back = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(back).rounded_rectangle((250, 214, 600, 664), radius=64, fill=(255, 255, 255, 95))
    tile = Image.alpha_composite(tile, back)

    # Ombre portée de la carte avant
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((424, 380, 774, 830), radius=64, fill=(30, 10, 70, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    tile = Image.alpha_composite(tile, sh)

    # Carte avant (la nouvelle peau) avec coin replié
    x0, y0, x1, y1, fold = 404, 360, 754, 810, 118
    front = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(front)
    d.rounded_rectangle((x0, y0, x1, y1), radius=64, fill=(255, 255, 255, 255))
    cut = Image.new("L", (S, S), 255)
    ImageDraw.Draw(cut).polygon([(x1 - fold, y0 - 2), (x1 + 2, y0 - 2), (x1 + 2, y0 + fold)], fill=0)
    front.putalpha(ImageChops.multiply(front.getchannel("A"), cut))
    # le rabat
    flap = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(flap).polygon([(x1 - fold, y0), (x1 - fold, y0 + fold - 18), (x1 - 18, y0 + fold)],
                                 fill=(206, 196, 255, 255))
    front = Image.alpha_composite(front, flap)
    # deux lignes « contenu » en dégradé
    lines = Image.new("L", (S, S), 0)
    ld = ImageDraw.Draw(lines)
    ld.rounded_rectangle((x0 + 62, y0 + 200, x1 - 62, y0 + 248), radius=24, fill=255)
    ld.rounded_rectangle((x0 + 62, y0 + 300, x1 - 140, y0 + 348), radius=24, fill=255)
    front.paste(small.convert("RGBA"), (0, 0), lines)
    tile = Image.alpha_composite(tile, front)
    return tile


def main() -> None:
    OUT.mkdir(exist_ok=True)
    img = make()
    img.resize((512, 512), Image.Resampling.LANCZOS).save(OUT / "mue.png")
    img.resize((256, 256), Image.Resampling.LANCZOS).save(
        OUT / "mue.ico", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("OK ->", OUT)


if __name__ == "__main__":
    main()
