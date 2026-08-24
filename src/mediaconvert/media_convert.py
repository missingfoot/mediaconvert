"""Video/audio conversion backend: ffmpeg for everything, including
video->gif/webp (animated) and video->audio extraction."""

import subprocess
from pathlib import Path

from mediaconvert.categorize import AUDIO_FORMATS


def convert_media(src: Path, out_path: Path, fmt: str) -> None:
    """Convert a video or audio file to fmt, writing to out_path.

    Raises RuntimeError on failure.
    """
    cmd = ["ffmpeg", "-y", "-i", str(src)]

    if fmt in AUDIO_FORMATS:
        # Extraction (source may be video or audio) - drop any video stream.
        cmd += ["-vn"]
    elif fmt == "gif":
        cmd += ["-vf", "fps=15,scale=480:-1:flags=lanczos"]
    elif fmt == "webp":
        cmd += ["-vf", "fps=15,scale=480:-1:flags=lanczos", "-loop", "0"]

    cmd += [str(out_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-2000:] or f"ffmpeg failed converting {src.name}")
