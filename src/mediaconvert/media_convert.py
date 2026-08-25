"""Video/audio conversion backend: ffmpeg for everything, including
video->gif/webp (animated) and video->audio extraction."""

import subprocess
from pathlib import Path

from mediaconvert.categorize import AUDIO_FORMATS
from mediaconvert.control import ConversionControl

_ANIMATED_OUTPUT_FILTER = "fps=15,scale=480:-1:flags=lanczos"

# ffmpeg reads control commands from stdin by default; if stdin is inherited
# from a real terminal it can block forever waiting for keyboard input that
# never comes, with no error and no timeout. stdin=DEVNULL prevents that.
# TIMEOUT_SECONDS is a second line of defense against any other hang.
TIMEOUT_SECONDS = 600

# Re-encoding into webm is unavoidable for H.264/HEVC sources (WebM's
# container spec cannot hold those codecs at all - there is no remux path),
# and libvpx's default settings are extremely slow (measured: a 30s 1080p
# clip did not finish in 3+ minutes). VP8 at these speed-tuned settings
# converted a real 166s 1080p clip in ~18s in testing, versus VP9 at its
# fastest settings (~56s) - VP8 is the better speed/quality tradeoff here.
_WEBM_ENCODE_ARGS = [
    "-c:v", "libvpx", "-deadline", "realtime", "-cpu-used", "16",
    "-crf", "10", "-b:v", "2M", "-c:a", "libvorbis",
]

# Fallback for the common modern container targets when a remux isn't
# possible (source codec incompatible with the target container) - x264's
# default "medium" preset is needlessly slow for a batch converter.
_H264_CONTAINER_TARGETS = {"mp4", "mkv", "mov", "m4v"}
_GENERIC_VIDEO_ENCODE_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac"]


def _try_remux(src: Path, out_path: Path, fmt: str) -> bool:
    """Attempt a zero-cost stream copy into the target container/format.
    Only succeeds when the source's existing codec is actually compatible
    with fmt - ffmpeg itself rejects anything else, so this is always safe
    to attempt first. Returns True on success."""
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if fmt in AUDIO_FORMATS:
        cmd += ["-vn", "-c:a", "copy"]
    else:
        cmd += ["-c", "copy"]
    cmd += [str(out_path)]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            stdin=subprocess.DEVNULL, timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False
    if result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
        return True
    out_path.unlink(missing_ok=True)
    return False


def _run_killable(cmd: list[str], control: ConversionControl | None) -> subprocess.CompletedProcess:
    """Like subprocess.run, but registers the process on control so a Stop
    request from another thread can terminate it immediately instead of
    waiting for a full encode to finish."""
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if control is not None:
        control.set_current_process(proc)
    try:
        stdout, stderr = proc.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise
    finally:
        if control is not None:
            control.set_current_process(None)
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def convert_media(
    src: Path, out_path: Path, fmt: str, control: ConversionControl | None = None,
) -> None:
    """Convert a video or audio file to fmt, writing to out_path.

    Tries a lossless remux first for anything other than gif/webp (which
    always need the animated-output filter applied); falls back to a full
    re-encode only when the source's codec isn't compatible with fmt.

    If control is given and its Stop is requested while the (killable)
    re-encode subprocess is running, the process is terminated and this
    raises RuntimeError like any other failure - the remux attempt itself
    is near-instant and isn't tracked on control.

    Raises RuntimeError on failure.
    """
    if fmt not in ("gif", "webp") and _try_remux(src, out_path, fmt):
        return

    cmd = ["ffmpeg", "-y", "-i", str(src)]

    if fmt in AUDIO_FORMATS:
        # Extraction (source may be video or audio) - drop any video stream.
        cmd += ["-vn"]
    elif fmt == "gif":
        cmd += ["-vf", _ANIMATED_OUTPUT_FILTER]
    elif fmt == "webp":
        cmd += ["-vf", _ANIMATED_OUTPUT_FILTER, "-loop", "0"]
    elif fmt == "webm":
        cmd += _WEBM_ENCODE_ARGS
    elif fmt in _H264_CONTAINER_TARGETS:
        cmd += _GENERIC_VIDEO_ENCODE_ARGS

    cmd += [str(out_path)]

    try:
        result = _run_killable(cmd, control)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg timed out after {TIMEOUT_SECONDS}s converting {src.name}")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-2000:] or f"ffmpeg failed converting {src.name}")
