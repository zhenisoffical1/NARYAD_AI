"""Хранение фото: нормализация, превью, время съёмки из EXIF, перцептивный хэш."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import imagehash
import piexif
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings
from app.errors import Invalid

_EXIF_DATETIME_TAGS = (
    ("Exif", piexif.ExifIFD.DateTimeOriginal),
    ("Exif", piexif.ExifIFD.DateTimeDigitized),
    ("0th", piexif.ImageIFD.DateTime),
)


@dataclass(frozen=True, slots=True)
class StoredPhoto:
    path: str  # относительно MEDIA_DIR
    thumb_path: str
    taken_at: datetime | None
    phash: str
    width: int
    height: int
    size_bytes: int


def exif_taken_at(data: bytes) -> datetime | None:
    """Время съёмки из EXIF.

    Камера пишет местное время без часового пояса — считаем его временем предприятия.
    """
    try:
        exif = piexif.load(data)
    except Exception:
        return None
    for ifd, tag in _EXIF_DATETIME_TAGS:
        raw = exif.get(ifd, {}).get(tag)
        if not raw:
            continue
        try:
            text = raw.decode() if isinstance(raw, bytes) else str(raw)
            local = datetime.strptime(text.strip("\x00 "), "%Y:%m:%d %H:%M:%S")
            return local.replace(tzinfo=settings.tz).astimezone(UTC)
        except ValueError:
            continue
    return None


def compute_phash(image: Image.Image) -> str:
    return str(imagehash.phash(image))


def phash_distance(a: str, b: str) -> int:
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))


def _fit(image: Image.Image, max_side: int) -> Image.Image:
    copy = image.copy()
    copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return copy


def store_photo(data: bytes, order_id: int) -> StoredPhoto:
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise Invalid(f"Фото больше {settings.max_upload_mb} МБ. Сделайте снимок заново.")
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise Invalid("Файл не похож на фотографию. Загрузите JPEG, PNG или HEIC-снимок.") from exc

    taken_at = exif_taken_at(data)
    upright = ImageOps.exif_transpose(image).convert("RGB")
    full = _fit(upright, settings.photo_max_side)
    thumb = _fit(upright, settings.thumb_max_side)

    folder = Path("orders") / str(order_id)
    (settings.media_dir / folder).mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex
    rel_path = (folder / f"{name}.jpg").as_posix()
    rel_thumb = (folder / f"{name}_thumb.jpg").as_posix()

    full_buf = BytesIO()
    full.save(full_buf, "JPEG", quality=82, optimize=True)
    (settings.media_dir / rel_path).write_bytes(full_buf.getvalue())
    thumb.save(settings.media_dir / rel_thumb, "JPEG", quality=75, optimize=True)

    return StoredPhoto(
        path=rel_path,
        thumb_path=rel_thumb,
        taken_at=taken_at,
        phash=compute_phash(full),
        width=full.width,
        height=full.height,
        size_bytes=full_buf.tell(),
    )


def media_url(rel_path: str) -> str:
    return f"/media/{rel_path}"


def delete_files(*rel_paths: str) -> None:
    for rel in rel_paths:
        (settings.media_dir / rel).unlink(missing_ok=True)
