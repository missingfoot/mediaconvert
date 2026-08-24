"""Image conversion backend: ImageMagick for general formats, libwebp for WebP output."""

import subprocess
import tempfile
from pathlib import Path


def _largest_ico_frame_index(src: Path) -> int:
    """Index of the largest frame (by pixel area) in a multi-frame .ico."""
    result = subprocess.run(
        ["magick", "identify", "-format", "%wx%h\n", str(src)],
        capture_output=True, text=True,
    )
    best_idx = 0
    best_area = -1
    for idx, line in enumerate(result.stdout.strip().splitlines()):
        w, _, h = line.partition("x")
        area = int(w) * int(h)
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Command failed: {' '.join(cmd)}")


def _convert_to_webp(src: Path, magick_src: str, out_path: Path) -> None:
    is_animated_gif = src.suffix.lower() == ".gif"
    if is_animated_gif:
        result = subprocess.run(
            ["gif2webp", "-lossy", "-q", "85", "-m", "4", str(src), "-o", str(out_path)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return
        # Fall through to cwebp if gif2webp fails (e.g. non-animated .gif).

    if magick_src == str(src):
        cwebp_src = str(src)
        _run(["cwebp", "-q", "90", cwebp_src, "-o", str(out_path)])
    else:
        # magick_src references a frame index (e.g. an .ico) - cwebp needs a
        # real file, so extract that frame to a temp PNG first.
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
            _run(["magick", magick_src, tmp.name])
            _run(["cwebp", "-q", "90", tmp.name, "-o", str(out_path)])


def convert_image(src: Path, out_path: Path, fmt: str) -> None:
    """Convert an image file to fmt, writing to out_path.

    Raises RuntimeError on failure.
    """
    magick_src = _magick_src(src)
    if fmt == "webp":
        _convert_to_webp(src, magick_src, out_path)
    else:
        _run(["magick", magick_src, str(out_path)])
