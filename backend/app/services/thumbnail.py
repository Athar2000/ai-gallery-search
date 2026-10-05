import io

from PIL import Image, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pass

THUMBNAIL_MAX_DIMENSION = 480
THUMBNAIL_JPEG_QUALITY = 82


def generate_thumbnail(content: bytes) -> bytes:
    """
    Returns JPEG bytes for a thumbnail no larger than THUMBNAIL_MAX_DIMENSION
    on its longest side, rotated according to EXIF orientation so it always
    displays right-side-up regardless of camera orientation metadata.
    """
    with Image.open(io.BytesIO(content)) as img:
        img = ImageOps.exif_transpose(img)  # bakes rotation in, then strips the tag
        img = img.convert("RGB")
        img.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=THUMBNAIL_JPEG_QUALITY)
        return buffer.getvalue()
