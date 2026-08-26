"""Image conversion backend: ImageMagick for general formats, libwebp for WebP output."""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_JPEG_EXTENSIONS = {".jpg", ".jpeg", ".jfif"}


@dataclass
class ImageOptions:
    """PNG/JPEG optimization settings, applied to every conversion whose
    output format is png or jpg/jpeg - see convert_image."""

    png_mode: str = "lossless"  # "lossless" or "lossy"
    oxipng_level: int = 4
    pngquant_quality_min: int = 65
    jpeg_quality: int = 85

# Formats cwebp can read directly. Everything else needs a temp-PNG bridge
# through `magick` first (cwebp doesn't understand bmp/avif/heic/etc).
_CWEBP_READABLE = {".png", ".jpg", ".jpeg", ".jfif", ".tif", ".tiff", ".webp"}

# See media_convert.TIMEOUT_SECONDS for why stdin is redirected and a
# timeout is always set on every subprocess call in this module.
TIMEOUT_SECONDS = 600


def _largest_ico_frame_index(src: Path) -> int:
    """Index of the largest frame (by pixel area) in a multi-frame .ico."""
    result = subprocess.run(
        ["magick", "identify", "-format", "%wx%h\n", str(src)],
        capture_output=True, text=True,
        stdin=subprocess.DEVNULL, timeout=TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        # Fall back to frame 0 - an intentional, documented choice rather
        # than an accident of an empty stdout loop.
        return 0
    best_idx = 0
    best_area = -1
    for idx, line in enumerate(result.stdout.strip().splitlines()):
        w, _, h = line.partition("x")
        try:
            area = int(w) * int(h)
        except ValueError:
            # A line that isn't a clean WxH dimension - skip it rather than
            # letting a malformed identify() output crash the conversion.
            continue
        if area > best_area:
            best_area = area
            best_idx = idx
    return best_idx


def _magick_src(src: Path) -> str:
    """The path/frame-selector magick should read from (handles multi-frame .ico)."""
    if src.suffix.lower() == ".ico":
        return f"{src}[{_largest_ico_frame_index(src)}]"
    return str(src)


def _run(cmd: list[str]) -> None:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            stdin=subprocess.DEVNULL, timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{cmd[0]} timed out after {TIMEOUT_SECONDS}s")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Command failed: {' '.join(cmd)}")


def _convert_to_webp(src: Path, magick_src: str, out_path: Path) -> None:
    is_animated_gif = src.suffix.lower() == ".gif"
    if is_animated_gif:
        try:
            result = subprocess.run(
                ["gif2webp", "-lossy", "-q", "85", "-m", "4", str(src), "-o", str(out_path)],
                capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"gif2webp timed out after {TIMEOUT_SECONDS}s")
        if result.returncode == 0:
            return
        # Fall through to cwebp as a defensive fallback if gif2webp fails.

    if src.suffix.lower() in _CWEBP_READABLE:
        _run(["cwebp", "-q", "90", magick_src, "-o", str(out_path)])
    else:
        # cwebp can't read this format directly (e.g. bmp/avif/heic/ico) -
        # bridge through a temp PNG via magick first.
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
            _run(["magick", magick_src, tmp.name])
            _run(["cwebp", "-q", "90", tmp.name, "-o", str(out_path)])


def _optimize_png(src: Path, magick_src: str, out_path: Path, options: ImageOptions) -> None:
    # Get a PNG at out_path first - either the source itself, or a plain
    # magick re-encode when converting from another format - then optimize
    # it in place.
    if src.suffix.lower() == ".png":
        shutil.copy2(src, out_path)
    else:
        _run(["magick", magick_src, str(out_path)])

    if options.png_mode == "lossy":
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
            _run([
                "pngquant", f"--quality={options.pngquant_quality_min}-100",
                "--output", tmp.name, "--force", str(out_path),
            ])
            _run(["oxipng", "-o", str(options.oxipng_level), "--out", str(out_path), tmp.name])
    else:
        _run(["oxipng", "-o", str(options.oxipng_level), str(out_path)])


def _optimize_jpeg(src: Path, magick_src: str, out_path: Path, options: ImageOptions) -> None:
    # jpegoptim optimizes in place, so get a JPEG at out_path first - either
    # a copy of the source, or a plain magick re-encode - then optimize it.
    if src.suffix.lower() in _JPEG_EXTENSIONS:
        shutil.copy2(src, out_path)
    else:
        _run(["magick", magick_src, str(out_path)])
    _run(["jpegoptim", f"--max={options.jpeg_quality}", "--strip-all", str(out_path)])


def convert_image(src: Path, out_path: Path, fmt: str, options: ImageOptions | None = None) -> None:
    """Convert an image file to fmt, writing to out_path.

    Converting to png or jpg/jpeg always runs the result through the
    matching optimizer (oxipng/pngquant or jpegoptim) - see ImageOptions.

    Raises RuntimeError on failure.
    """
    options = options or ImageOptions()
    magick_src = _magick_src(src)
    if fmt == "webp":
        _convert_to_webp(src, magick_src, out_path)
    elif fmt == "png":
        _optimize_png(src, magick_src, out_path, options)
    elif fmt in ("jpg", "jpeg"):
        _optimize_jpeg(src, magick_src, out_path, options)
    else:
        _run(["magick", magick_src, str(out_path)])
