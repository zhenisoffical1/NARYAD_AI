"""Фото-заглушки для оценки ИИ: исправное и неисправное оборудование, другой агрегат.

Рисунки условные, но различимы и для pHash, и для мультимодальной модели: насос с лужей
масла и без неё, рама с трещиной и со сварным швом, конвейер вместо насоса. У каждого
случая свой фон и ракурс — иначе разные наряды выглядели бы для pHash одним снимком.
"""

import random
from datetime import datetime
from io import BytesIO
from typing import Literal

import piexif
from PIL import Image, ImageDraw, ImageFilter

from app.config import settings

Scene = Literal["leak", "fixed", "crack", "welded", "motor", "conveyor"]

SIZE = (1200, 900)


def _background(draw: ImageDraw.ImageDraw, rng: random.Random) -> None:
    """Цех: стена, пол и случайные конструкции — уникальные для каждого случая."""
    wall = rng.randint(150, 200)
    draw.rectangle([0, 0, SIZE[0], 560], fill=(wall, wall - 8, wall - 20))
    floor = rng.randint(90, 130)
    draw.rectangle([0, 560, SIZE[0], SIZE[1]], fill=(floor, floor - 5, floor - 12))
    for _ in range(rng.randint(5, 9)):
        x, y = rng.randint(0, 1100), rng.randint(0, 520)
        w, h = rng.randint(60, 260), rng.randint(40, 200)
        tone = rng.randint(60, 230)
        draw.rectangle([x, y, x + w, y + h], fill=(tone, tone, rng.randint(60, 230)))


def _pump(draw: ImageDraw.ImageDraw, dx: int, dy: int) -> None:
    draw.rectangle([300 + dx, 380 + dy, 760 + dx, 600 + dy], fill=(70, 75, 80))  # корпус
    draw.ellipse([700 + dx, 400 + dy, 900 + dx, 580 + dy], fill=(40, 70, 150))  # двигатель
    draw.rectangle([380 + dx, 300 + dy, 440 + dx, 380 + dy], fill=(90, 90, 95))  # патрубок
    draw.rectangle([260 + dx, 600 + dy, 940 + dx, 630 + dy], fill=(50, 50, 50))  # рама


def _frame(draw: ImageDraw.ImageDraw, dx: int, dy: int) -> None:
    draw.rectangle([150 + dx, 420 + dy, 1050 + dx, 500 + dy], fill=(110, 100, 60))
    draw.rectangle([250 + dx, 500 + dy, 310 + dx, 720 + dy], fill=(100, 90, 55))
    draw.rectangle([890 + dx, 500 + dy, 950 + dx, 720 + dy], fill=(100, 90, 55))


def photo(scene: Scene, seed: int, taken_at: datetime | None) -> bytes:
    rng = random.Random(seed)
    image = Image.new("RGB", SIZE)
    draw = ImageDraw.Draw(image)
    _background(draw, rng)
    dx, dy = rng.randint(-120, 120), rng.randint(-60, 60)

    if scene in ("leak", "fixed"):
        _pump(draw, dx, dy)
        if scene == "leak":
            draw.ellipse([330 + dx, 620 + dy, 820 + dx, 760 + dy], fill=(15, 12, 8))
            draw.line([500 + dx, 600 + dy, 505 + dx, 640 + dy], fill=(15, 12, 8), width=10)
        else:
            draw.rectangle([470 + dx, 560 + dy, 540 + dx, 600 + dy], fill=(200, 200, 205))
    elif scene in ("crack", "welded"):
        _frame(draw, dx, dy)
        if scene == "crack":
            points = [(600 + dx + i * 12, 420 + dy + (i % 2) * 20) for i in range(8)]
            draw.line(points, fill=(10, 10, 10), width=6)
        else:
            draw.rectangle([580 + dx, 425 + dy, 700 + dx, 495 + dy], fill=(160, 150, 130))
    elif scene == "motor":
        draw.rectangle([380 + dx, 380 + dy, 820 + dx, 620 + dy], fill=(40, 70, 150))
        draw.rectangle([820 + dx, 470 + dy, 900 + dx, 530 + dy], fill=(160, 160, 160))
    else:  # conveyor — «не то оборудование»
        draw.rectangle([0, 450 + dy, SIZE[0], 520 + dy], fill=(30, 30, 30))
        for x in range(60, SIZE[0], 140):
            draw.ellipse([x, 520 + dy, x + 70, 590 + dy], fill=(140, 140, 140))

    image = image.filter(ImageFilter.GaussianBlur(1.2))
    buf = BytesIO()
    kwargs = {}
    if taken_at is not None:
        stamp = taken_at.astimezone(settings.tz).strftime("%Y:%m:%d %H:%M:%S").encode()
        kwargs["exif"] = piexif.dump({"Exif": {piexif.ExifIFD.DateTimeOriginal: stamp}})
    image.save(buf, "JPEG", quality=88, **kwargs)
    return buf.getvalue()
