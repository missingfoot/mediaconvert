import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mediaconvert.control import ConversionControl
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
    with patch("mediaconvert.media_convert.subprocess.run") as mock_run, \
         patch("mediaconvert.media_convert.subprocess.Popen") as mock_popen:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        mock_proc = mock_popen.return_value
        mock_proc.communicate.return_value = ("", "")
        mock_proc.returncode = 0
        convert_media(tmp_path / "in.mp4", tmp_path / "out.mp4", "mp4")

    # remux attempt still goes through subprocess.run with stdin/timeout
    _, run_kwargs = mock_run.call_args
    assert run_kwargs.get("stdin") == subprocess.DEVNULL
    assert run_kwargs.get("timeout")

    # re-encode fallback uses a killable Popen: stdin redirected on
    # construction, timeout enforced on communicate()
    _, popen_kwargs = mock_popen.call_args
    assert popen_kwargs.get("stdin") == subprocess.DEVNULL
    _, communicate_kwargs = mock_proc.communicate.call_args
    assert communicate_kwargs.get("timeout")


def test_convert_media_timeout_reports_as_failure_not_hang(tmp_path):
    with patch("mediaconvert.media_convert.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)), \
         patch("mediaconvert.media_convert.subprocess.Popen") as mock_popen:
        mock_popen.return_value.communicate.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)
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


class _FakePopen:
    """Records the command it was constructed with and writes a fake output
    file on communicate(), like a fast, always-successful ffmpeg call."""

    instances: list[list[str]] = []

    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.returncode = 0
        _FakePopen.instances.append(cmd)

    def communicate(self, timeout=None):
        Path(self.cmd[-1]).write_bytes(b"encoded")
        return ("", "")


def test_convert_media_falls_back_to_reencode_when_remux_fails(tmp_path):
    remux_calls = []

    def fake_run(cmd, **kwargs):
        remux_calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="incompatible codec")

    _FakePopen.instances = []
    with patch("mediaconvert.media_convert.subprocess.run", side_effect=fake_run), \
         patch("mediaconvert.media_convert.subprocess.Popen", _FakePopen):
        convert_media(tmp_path / "in.mp4", tmp_path / "out.webm", "webm")

    assert len(remux_calls) == 1
    assert "copy" in remux_calls[0]
    assert len(_FakePopen.instances) == 1
    assert "libvpx" in _FakePopen.instances[0]


def test_convert_media_remux_attempt_never_raises_on_timeout(tmp_path):
    # The remux attempt itself must not propagate a timeout - it should be
    # treated as "remux not possible" so the re-encode fallback still runs.
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)

    _FakePopen.instances = []
    with patch("mediaconvert.media_convert.subprocess.run", side_effect=fake_run), \
         patch("mediaconvert.media_convert.subprocess.Popen", _FakePopen):
        convert_media(tmp_path / "in.mp4", tmp_path / "out.webm", "webm")

    assert len(_FakePopen.instances) == 1


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


def test_convert_media_stop_terminates_running_reencode(tmp_path):
    # A long, high-motion source so the re-encode (measured ~3s for this
    # exact clip at our speed-tuned VP8 settings) takes long enough to
    # reliably stop mid-flight rather than finishing before we can react.
    src = tmp_path / "a.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "mandelbrot=size=854x480:rate=30",
         "-t", "60", "-c:v", "libx264", "-preset", "veryfast", str(src)],
        check=True, capture_output=True,
    )
    out = tmp_path / "a.webm"  # webm forces the re-encode path, never a remux
    control = ConversionControl()

    result_holder = {}

    def run_conversion():
        try:
            convert_media(src, out, "webm", control=control)
            result_holder["error"] = None
        except RuntimeError as e:
            result_holder["error"] = str(e)

    thread = threading.Thread(target=run_conversion)
    start = time.time()
    thread.start()
    time.sleep(0.5)  # let ffmpeg actually start
    control.request_stop()
    thread.join(timeout=10)
    elapsed = time.time() - start

    assert not thread.is_alive(), "convert_media did not return after stop"
    assert elapsed < 8, f"stop took too long to take effect: {elapsed:.1f}s"
    assert result_holder["error"] is not None, "a killed process should be reported as a failure"


def test_convert_media_no_control_still_works(tmp_path):
    # control is optional - existing call sites without it must keep working.
    src = tmp_path / "a.mp4"
    out = tmp_path / "a.webm"
    _make_video(src)
    convert_media(src, out, "webm")
    assert out.exists()
