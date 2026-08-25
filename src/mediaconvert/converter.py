"""Top-level per-file conversion: dispatch to a backend, resolve output
path, preserve mtime, and report success/failure without raising."""

from dataclasses import dataclass
from pathlib import Path

from mediaconvert.image_convert import convert_image
from mediaconvert.media_convert import convert_media
from mediaconvert.naming import copy_mtime, resolve_output_path


@dataclass
class ConversionResult:
    src: Path
    out_path: Path | None
    success: bool
    error: str | None


def convert_file(src: Path, fmt: str, category: str, out_dir: Path | None = None) -> ConversionResult:
    """Convert src to fmt, writing into out_dir (or next to src if out_dir is
    None). Never raises - failures are reported in the result."""
    out_path = resolve_output_path(src, fmt, out_dir)
    try:
        if category == "image":
            convert_image(src, out_path, fmt)
        else:
            convert_media(src, out_path, fmt)
        copy_mtime(src, out_path)
        return ConversionResult(src=src, out_path=out_path, success=True, error=None)
    except RuntimeError as e:
        out_path.unlink(missing_ok=True)
        return ConversionResult(src=src, out_path=None, success=False, error=str(e))
