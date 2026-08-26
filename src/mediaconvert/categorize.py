"""Format lists and per-file category classification for mediaconvert."""

from pathlib import Path

IMAGE_FORMATS = {
    "avif", "bmp", "gif", "heic", "ico", "jfif", "jpeg", "jpg", "png",
    "tif", "tiff", "webp",
}

VIDEO_FORMATS = {
    "avi", "m2ts", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "mts",
    "ogg", "ogv", "swf", "ts", "vob", "webm", "wmv",
}

AUDIO_FORMATS = {
    "aac", "aifc", "aiff", "flac", "m4a", "m4b", "mp3", "opus", "voc",
    "wav",
}

CATEGORY_ORDER = ["video", "image", "audio"]

_IMAGE_PRIORITY = ["png", "jpg", "jpeg", "webp"]
_VIDEO_PRIORITY = ["mp4", "mov", "webm", "gif"]
_AUDIO_PRIORITY = ["mp3", "wav", "aac", "flac"]


def _ordered(formats: set[str], priority: list[str]) -> list[str]:
    """Priority formats first (in the given order), then the rest alphabetically."""
    rest = sorted(formats - set(priority))
    return [f for f in priority if f in formats] + rest


def category_of(path: Path) -> str | None:
    """Return "image", "video", or "audio" for path's extension, or None if
    the extension isn't recognized."""
    ext = path.suffix.lower().lstrip(".")
    if ext in IMAGE_FORMATS:
        return "image"
    if ext in VIDEO_FORMATS:
        return "video"
    if ext in AUDIO_FORMATS:
        return "audio"
    return None


def split_by_category(paths: list[Path]) -> tuple[dict[str, list[Path]], list[Path]]:
    """Bucket paths by category, preserving input order within each bucket.
    Only categories with at least one matching file appear as keys. Returns
    (groups, ignored) where ignored holds paths with unrecognized
    extensions."""
    groups: dict[str, list[Path]] = {}
    ignored: list[Path] = []
    for path in paths:
        category = category_of(path)
        if category is None:
            ignored.append(path)
        else:
            groups.setdefault(category, []).append(path)
    return groups, ignored


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
