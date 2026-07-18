from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError


MIN_IMAGE_SIDE = 900
MIN_BRIGHTNESS = 45.0
MAX_BRIGHTNESS = 248.0
MIN_CONTRAST = 22.0
MIN_EDGE_VARIANCE = 110.0


@dataclass(frozen=True)
class PhotoQualityResult:
    acceptable: bool
    width: int
    height: int
    brightness: float
    contrast: float
    sharpness: float
    issues: tuple[str, ...]


def assess_homework_photo(image_bytes: bytes) -> PhotoQualityResult:
    if not image_bytes:
        raise ValueError("Файл изображения пустой.")

    try:
        with Image.open(BytesIO(image_bytes)) as source:
            source.load()
            image = source.convert("L")
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("Не удалось открыть изображение.") from error

    width, height = image.size
    statistics = ImageStat.Stat(image)
    brightness = float(statistics.mean[0])
    contrast = float(statistics.stddev[0])

    edges = image.filter(ImageFilter.FIND_EDGES)
    border = max(1, min(width, height) // 50)
    if width > border * 2 and height > border * 2:
        edges = edges.crop((border, border, width - border, height - border))
    sharpness = float(ImageStat.Stat(edges).var[0])

    issues = []
    if min(width, height) < MIN_IMAGE_SIDE:
        issues.append("Поднесите камеру ближе: текст слишком мелкий.")
    if brightness < MIN_BRIGHTNESS:
        issues.append("Фото слишком тёмное: добавьте освещение.")
    elif brightness > MAX_BRIGHTNESS:
        issues.append("Фото пересвечено: уберите яркий блик.")
    if contrast < MIN_CONTRAST:
        issues.append("Текст слабо отличается от фона.")
    if sharpness < MIN_EDGE_VARIANCE:
        issues.append("Фото выглядит размытым: удерживайте камеру ровно.")

    return PhotoQualityResult(
        acceptable=not issues,
        width=width,
        height=height,
        brightness=brightness,
        contrast=contrast,
        sharpness=sharpness,
        issues=tuple(issues),
    )
