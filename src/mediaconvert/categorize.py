"""Format lists and batch category detection for mediaconvert."""

from pathlib import Path

IMAGE_FORMATS = {
    "avif", "bmp", "gif", "heic", "ico", "jfif", "jpeg", "jpg", "png",
    "tiff", "webp",
}

VIDEO_FORMATS = {
    "avi", "m2ts", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "mts",
    "ogg", "ogv", "swf", "ts", "vob", "webm", "wmv",
}

AUDIO_FORMATS = {
    "aac", "aifc", "aiff", "flac", "m4a", "m4b", "mp3", "opus", "voc",
    "wav",
}

class MixedCategoryError(Exception):
    """Raised when a batch mixes categories or contains an unknown extension."""


def _category_of(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in IMAGE_FORMATS:
        return "image"
    if ext in VIDEO_FORMATS:
        return "video"
    if ext in AUDIO_FORMATS:
        return "audio"
    raise MixedCategoryError(f"Unrecognized file type: {path.name}")


def categorize(paths: list[Path]) -> str:
    """Return "image", "video", or "audio" for a batch, or raise MixedCategoryError."""
    categories = {_category_of(p) for p in paths}
    if len(categories) != 1:
        raise MixedCategoryError(
            "Can't mix images, video, and audio in one batch"
        )
    return categories.pop()


def target_formats(category: str) -> list[str]:
    """Selectable output formats for a batch of the given category."""
    if category == "image":
        return sorted(IMAGE_FORMATS)
    if category == "audio":
        return sorted(AUDIO_FORMATS)
    if category == "video":
        return sorted(VIDEO_FORMATS | {"gif", "webp"} | AUDIO_FORMATS)
    raise ValueError(f"Unknown category: {category}")
