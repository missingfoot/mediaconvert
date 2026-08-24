import subprocess
from pathlib import Path

import pytest

from mediaconvert.media_convert import convert_media


def _make_video(path: Path, duration="1", has_audio=True):
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=64x64:rate=10",
    ]
    if has_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
        cmd += ["-shortest"]
    cmd += [str(path)]
    subprocess.run(cmd, check=True, capture_output=True)


def _ffprobe_streams(path: Path) -> list[str]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip().splitlines()


def test_convert_mp4_to_webm(tmp_path):
    src = tmp_path / "a.mp4"
    out = tmp_path / "a.webm"
    _make_video(src)
    convert_media(src, out, "webm")
    assert out.exists()
    assert out.stat().st_size > 0


def test_convert_video_to_gif(tmp_path):
    src = tmp_path / "a.mp4"
    out = tmp_path / "a.gif"
    _make_video(src)
    convert_media(src, out, "gif")
    assert out.exists()
    result = subprocess.run(
        ["magick", "identify", "-format", "%m\n", str(out)],
        check=True, capture_output=True, text=True,
    )
    frames = result.stdout.strip().splitlines()
    assert frames and set(frames) == {"GIF"}


def test_convert_video_to_webp_animated(tmp_path):
    src = tmp_path / "a.mp4"
    out = tmp_path / "a.webp"
    _make_video(src)
    convert_media(src, out, "webp")
    assert out.exists()


def test_convert_video_to_audio_extracts_audio_only(tmp_path):
    src = tmp_path / "a.mp4"
    out = tmp_path / "a.mp3"
    _make_video(src, has_audio=True)
    convert_media(src, out, "mp3")
    assert out.exists()
    streams = _ffprobe_streams(out)
    assert streams == ["audio"]


def test_convert_audio_to_audio(tmp_path):
    src = tmp_path / "a.wav"
    out = tmp_path / "a.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(src)],
        check=True, capture_output=True,
    )
    convert_media(src, out, "mp3")
    assert out.exists()
    streams = _ffprobe_streams(out)
    assert streams == ["audio"]


def test_convert_failure_raises_runtime_error(tmp_path):
    src = tmp_path / "not_a_video.mp4"
    src.write_text("this is not a video")
    out = tmp_path / "out.webm"
    with pytest.raises(RuntimeError):
        convert_media(src, out, "webm")
