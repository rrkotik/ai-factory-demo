import base64
from io import BytesIO

from PIL import Image, ImageDraw


def image_base64(size=(256, 256), format="PNG", color=None):
    image = Image.new("RGB", size, color or "white")
    if color is None:
        draw = ImageDraw.Draw(image)
        for x in range(0, size[0], 16):
            draw.rectangle((x, 0, x + 7, size[1] - 1), fill="navy")
    output = BytesIO()
    image.save(output, format=format)
    return base64.b64encode(output.getvalue()).decode()


def product_payload(**changes):
    return {
        "title": "Shirt",
        "description": "A cotton shirt",
        "images": [image_base64()],
        **changes,
    }
