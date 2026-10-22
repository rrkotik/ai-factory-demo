"""Local listing checks. No network access until every deterministic check passes."""

import base64
import binascii
import re
import unicodedata
from io import BytesIO
from typing import Protocol

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

from app.schemas import ProductInput, ProductVerification
from app.service import DependencyUnavailable

# Deliberately small English examples, not a comprehensive moderation policy.
SWEAR_WORDS = frozenset({"fuck", "shit"})
RESTRICTED_WORDS = frozenset({"cocaine", "explosives"})
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024
MIN_IMAGE_SIDE = 256
MAX_IMAGE_SIDE = 4096
IMAGE_MIMES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


class ProductReviewer(Protocol):
    def review(self, product: ProductInput, images: list[str]) -> list[str]:
        """Return rejection comments, or an empty list when all checks pass."""
        ...


def check_text(value: str, field: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    comments = []
    if not any(character.isalnum() for character in normalized):
        comments.append(f"{field} must contain letters or numbers.")
    if any(
        unicodedata.category(character).startswith("C")
        and not (field == "Description" and character in "\n\t")
        for character in normalized
    ):
        comments.append(f"{field} contains invalid control or invisible characters.")
    tokens = set(re.findall(r"[^\W_]+", normalized))
    for words, label in ((SWEAR_WORDS, "swear"), (RESTRICTED_WORDS, "restricted")):
        for word in sorted(tokens & words):
            comments.append(f"{field} contains a {label} word: {word}.")
    return comments


def decode_image(value: str) -> tuple[bytes, str | None]:
    declared_mime = None
    if value.startswith("data:"):
        header, separator, value = value.partition(",")
        if not separator or header not in {f"data:{mime};base64" for mime in IMAGE_MIMES.values()}:
            raise ValueError("Use a base64 JPEG, PNG, or WebP image data URL.")
        declared_mime = header[5:-7]
    if len(value) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise ValueError("Decoded image must be at most 5 MiB.")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 image data.") from exc
    if not decoded:
        raise ValueError("Image data is empty.")
    if len(decoded) > MAX_IMAGE_BYTES:
        raise ValueError("Decoded image must be at most 5 MiB.")
    return decoded, declared_mime


def inspect_image(data: bytes, declared_mime: str | None) -> tuple[str, list[str]]:
    """Verify the file before loading pixels; bound dimensions before decompression."""
    try:
        with Image.open(BytesIO(data)) as image:
            mime = IMAGE_MIMES.get(image.format)
            if mime is None:
                raise ValueError("Unsupported image format; use JPEG, PNG, or WebP.")
            if declared_mime is not None and declared_mime != mime:
                raise ValueError("Declared image MIME type does not match its format.")
            if not all(MIN_IMAGE_SIDE <= side <= MAX_IMAGE_SIDE for side in image.size):
                raise ValueError("Image dimensions must be 256–4096 pixels on each side.")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Animated images are not supported.")
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            # Composite transparency onto white so invisible RGB detail cannot pass.
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            background.alpha_composite(rgba)
            gray = background.convert("L")
            gray.thumbnail((256, 256))
            brightness = ImageStat.Stat(gray).mean[0]
            edges = gray.filter(ImageFilter.FIND_EDGES).crop(
                (1, 1, gray.width - 1, gray.height - 1)
            )
            edge_strength = ImageStat.Stat(edges).mean[0]
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid or corrupted image file.") from exc

    comments = []
    if brightness < 5:
        comments.append("Image is too dark to inspect.")
    elif brightness > 250:
        comments.append("Image is too bright to inspect.")
    if edge_strength < 1:
        comments.append("Image has too little detail; it may be blank or severely blurred.")
    return mime, comments


class ProductVerifier:
    def __init__(self, reviewer: ProductReviewer | None = None):
        self.reviewer = reviewer

    def verify(self, product: ProductInput) -> ProductVerification:
        comments = check_text(product.title, "Title") + check_text(
            product.description, "Description"
        )
        images = []
        total_bytes = 0
        for index, value in enumerate(product.images, start=1):
            try:
                data, declared_mime = decode_image(value)
                total_bytes += len(data)
                if total_bytes > MAX_TOTAL_IMAGE_BYTES:
                    comments.append("Total decoded image size must be at most 20 MiB.")
                    break
                mime, issues = inspect_image(data, declared_mime)
                comments.extend(f"Image {index}: {issue}" for issue in issues)
                images.append(f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}")
            except ValueError as exc:
                comments.append(f"Image {index}: {exc}")
        if comments:
            return ProductVerification(status="rejected", comments=comments)
        if self.reviewer is None:
            raise DependencyUnavailable("Product review is not configured")
        comments = self.reviewer.review(product, images)
        return ProductVerification(status="rejected" if comments else "approved", comments=comments)
