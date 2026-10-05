"""
EXIF extraction.

Design per spec section 4: prefer EXIF DateTimeOriginal as the capture date;
if it's missing, fall back to file mtime/ctime and clearly record which
source was used in `capture_date_source` (exif | file_modified | unknown) so
the UI/search can be honest about date confidence later.
"""
import io
from datetime import date, datetime, time
from typing import Any

from PIL import ExifTags, Image

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - HEIC support is optional
    pass

_TAG_NAME_BY_ID = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAG_NAME_BY_ID = {v: k for k, v in ExifTags.GPSTAGS.items()}


def _rational_to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dms_to_decimal(dms: tuple, ref: str) -> float | None:
    try:
        degrees, minutes, seconds = (_rational_to_float(v) for v in dms)
        if degrees is None or minutes is None or seconds is None:
            return None
        decimal = degrees + minutes / 60 + seconds / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except (ValueError, TypeError):
        return None


def _json_safe(value: Any) -> Any:
    """Recursively convert EXIF values (bytes, IFDRational, tuples) to JSON-safe types."""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if hasattr(value, "__float__") and not isinstance(value, (int, float)):
        return _rational_to_float(value)
    return value


def extract_exif(content: bytes) -> dict:
    """
    Returns a dict with: capture_date, capture_time, latitude, longitude,
    camera_make, camera_model, orientation, width, height, exif_json.
    All keys are always present; values are None when not found.
    """
    result: dict[str, Any] = {
        "capture_date": None,
        "capture_time": None,
        "latitude": None,
        "longitude": None,
        "camera_make": None,
        "camera_model": None,
        "orientation": None,
        "width": None,
        "height": None,
        "exif_json": {},
    }

    with Image.open(io.BytesIO(content)) as img:
        result["width"], result["height"] = img.size
        exif = img.getexif()
        if not exif:
            return result

        named = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}

        # DateTimeOriginal/DateTimeDigitized live in the "Exif" sub-IFD, not
        # the top-level IFD — merge it in or every photo falls back to the
        # file-mtime date even when the camera recorded a real date.
        try:
            exif_sub_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            named.update({ExifTags.TAGS.get(k, str(k)): v for k, v in exif_sub_ifd.items()})
        except (KeyError, AttributeError):
            pass

        result["exif_json"] = _json_safe(named)

        result["camera_make"] = named.get("Make")
        result["camera_model"] = named.get("Model")
        result["orientation"] = named.get("Orientation")

        date_str = named.get("DateTimeOriginal") or named.get("DateTime")
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                result["capture_date"] = dt.date()
                result["capture_time"] = dt.time()
            except ValueError:
                pass

        # GPS lives in a nested IFD
        try:
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
        except (KeyError, AttributeError):
            gps_ifd = None

        if gps_ifd:
            gps_named = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in gps_ifd.items()}
            lat = gps_named.get("GPSLatitude")
            lat_ref = gps_named.get("GPSLatitudeRef")
            lon = gps_named.get("GPSLongitude")
            lon_ref = gps_named.get("GPSLongitudeRef")
            if lat and lat_ref:
                result["latitude"] = _dms_to_decimal(lat, lat_ref)
            if lon and lon_ref:
                result["longitude"] = _dms_to_decimal(lon, lon_ref)

    return result


def fallback_capture_date(file_mtime: datetime) -> tuple[date, time, str]:
    """Used when EXIF has no usable date — spec 4 requires we track the source."""
    return file_mtime.date(), file_mtime.time(), "file_modified"
