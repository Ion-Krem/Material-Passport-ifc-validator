"""Generate app.ico — multi-resolution icon for the desktop app."""
from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("seguisb.ttf", "seguibd.ttf", "segoeuib.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(int(size * 0.18), 4)

    # Vertical gradient blue → teal
    top = (37, 99, 235)
    bottom = (13, 148, 136)
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(size - 1, 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        grad.putpixel((0, y), (r, g, b))
    grad = grad.resize((size, size))

    # Mask: rounded square
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)

    text = "IFC"
    font = _font(int(size * 0.42))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), text, fill="white", font=font)
    return img


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_icon(s) for s in sizes]
    images[-1].save(
        "app.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    print("Wrote app.ico")


if __name__ == "__main__":
    main()
