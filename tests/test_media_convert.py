import subprocess
from pathlib import Path
from unittest.mock import patch

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


def _ffprobe_video_codec(path: Path) -> str:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


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


def test_convert_media_redirects_stdin_and_sets_timeout(tmp_path):
    with patch("mediaconvert.media_convert.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        convert_media(tmp_path / "in.mp4", tmp_path / "out.mp4", "mp4")
    _, kwargs = mock_run.call_args
    assert kwargs.get("stdin") == subprocess.DEVNULL
    assert kwargs.get("timeout")


def test_convert_media_timeout_reports_as_failure_not_hang(tmp_path):
    with patch("mediaconvert.media_convert.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)):
        with pytest.raises(RuntimeError, match="timed out"):
            convert_media(tmp_path / "in.mp4", tmp_path / "out.mp4", "mp4")


def test_convert_media_uses_remux_when_codec_compatible(tmp_path):
    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"remuxed")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("mediaconvert.media_convert.subprocess.run", side_effect=fake_run) as mock_run:
        convert_media(tmp_path / "in.mp4", tmp_path / "out.mkv", "mkv")

    assert mock_run.call_count == 1
    cmd = mock_run.call_args[0][0]
    assert "copy" in cmd


def test_convert_media_falls_back_to_reencode_when_remux_fails(tmp_path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "copy" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="incompatible codec")
        Path(cmd[-1]).write_bytes(b"encoded")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("mediaconvert.media_convert.subprocess.run", side_effect=fake_run):
        convert_media(tmp_path / "in.mp4", tmp_path / "out.webm", "webm")

    assert len(calls) == 2
    assert "copy" in calls[0]
    assert "libvpx" in calls[1]


def test_convert_media_remux_attempt_never_raises_on_timeout(tmp_path):
    # The remux attempt itself must not propagate a timeout - it should be
    # treated as "remux not possible" so the re-encode fallback still runs.
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "copy" in cmd:
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)
        Path(cmd[-1]).write_bytes(b"encoded")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("mediaconvert.media_convert.subprocess.run", side_effect=fake_run):
        convert_media(tmp_path / "in.mp4", tmp_path / "out.webm", "webm")

    assert len(calls) == 2


def test_convert_mp4_to_mkv_remuxes_without_reencoding(tmp_path):
    src = tmp_path / "a.mp4"
    out = tmp_path / "a.mkv"
    _make_video(src)
    src_codec = _ffprobe_video_codec(src)
    convert_media(src, out, "mkv")
    assert out.exists()
    assert _ffprobe_video_codec(out) == src_codec


def test_convert_mp4_to_webm_uses_fast_vp8_codec(tmp_path):
    src = tmp_path / "a.mp4"
    out = tmp_path / "a.webm"
    _make_video(src)
    convert_media(src, out, "webm")
    assert out.exists()
    assert _ffprobe_video_codec(out) == "vp8"
