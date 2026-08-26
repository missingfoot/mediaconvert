"""Top-level per-file conversion: dispatch to a backend, resolve output
path, preserve mtime, and report success/failure without raising."""

from dataclasses import dataclass
from pathlib import Path

from mediaconvert.control import ConversionControl
from mediaconvert.image_convert import ImageOptions, convert_image
from mediaconvert.media_convert import convert_media
from mediaconvert.naming import copy_mtime, resolve_output_path


@dataclass
class ConversionResult:
    src: Path
    out_path: Path | None
    success: bool
    error: str | None


def convert_file(
    src: Path,
    fmt: str,
    category: str,
    out_dir: Path | None = None,
    control: ConversionControl | None = None,
    image_options: ImageOptions | None = None,
) -> ConversionResult:
    """Convert src to fmt, writing into out_dir (or next to src if out_dir is
    None). Never raises - failures are reported in the result.

    control, if given, is only meaningful for video/audio (image conversions
    finish too fast to be worth making killable) - see convert_media."""
    out_path = resolve_output_path(src, fmt, out_dir)
    try:
        if category == "image":
            convert_image(src, out_path, fmt, image_options)
        else:
            convert_media(src, out_path, fmt, control=control)
        copy_mtime(src, out_path)
        return ConversionResult(src=src, out_path=out_path, success=True, error=None)
    except Exception as e:
        out_path.unlink(missing_ok=True)
        return ConversionResult(src=src, out_path=None, success=False, error=str(e))
