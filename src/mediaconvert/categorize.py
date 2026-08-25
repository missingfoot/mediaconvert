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

_IMAGE_PRIORITY = ["png", "jpg", "jpeg", "webp"]
_VIDEO_PRIORITY = ["mp4", "mov", "webm", "gif"]
_AUDIO_PRIORITY = ["mp3", "wav", "aac", "flac"]


def _ordered(formats: set[str], priority: list[str]) -> list[str]:
    """Priority formats first (in the given order), then the rest alphabetically."""
    rest = sorted(formats - set(priority))
    return [f for f in priority if f in formats] + rest


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
            "Can't mix images, video, and audio in one batch, please try again"
        )
    return categories.pop()


def target_formats(category: str) -> list[str]:
    """Selectable output formats for a batch of the given category, most
    common formats first."""
    if category == "image":
        return _ordered(IMAGE_FORMATS, _IMAGE_PRIORITY)
    if category == "audio":
        return _ordered(AUDIO_FORMATS, _AUDIO_PRIORITY)
    if category == "video":
        video_and_gif = _ordered(VIDEO_FORMATS | {"gif", "webp"}, _VIDEO_PRIORITY)
        return video_and_gif + _ordered(AUDIO_FORMATS, _AUDIO_PRIORITY)
    raise ValueError(f"Unknown category: {category}")
