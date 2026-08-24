import subprocess
from pathlib import Path

from mediaconvert.converter import convert_file


def _make_png(path: Path):
    subprocess.run(
        ["magick", "-size", "16x16", "xc:red", str(path)],
        check=True, capture_output=True,
    )


def test_convert_file_success_image(tmp_path):
    src = tmp_path / "a.png"
    _make_png(src)
    result = convert_file(src, "bmp", "image")
    assert result.success is True
    assert result.error is None
    assert result.out_path == tmp_path / "a.bmp"
    assert result.out_path.exists()


def test_convert_file_preserves_mtime(tmp_path):
    import os
    import time

    src = tmp_path / "a.png"
    _make_png(src)
    old_time = time.time() - 5000
    os.utime(src, (old_time, old_time))
    result = convert_file(src, "bmp", "image")
    assert result.out_path.stat().st_mtime == src.stat().st_mtime


def test_convert_file_failure_reports_error_not_exception(tmp_path):
    src = tmp_path / "broken.png"
    src.write_text("not an image")
    result = convert_file(src, "bmp", "image")
    assert result.success is False
    assert result.error is not None
    assert result.out_path is None


def test_convert_file_failure_cleans_up_partial_output(tmp_path):
    src = tmp_path / "broken.png"
    src.write_text("not an image")
    expected_out = tmp_path / "broken.bmp"
    result = convert_file(src, "bmp", "image")
    assert result.success is False
    assert not expected_out.exists()


def test_convert_file_success_audio(tmp_path):
    src = tmp_path / "a.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(src)],
        check=True, capture_output=True,
    )
    result = convert_file(src, "mp3", "audio")
    assert result.success is True
    assert result.error is None
    assert result.out_path == tmp_path / "a.mp3"
    assert result.out_path.exists()


def test_convert_file_collision_gets_suffix(tmp_path):
    src = tmp_path / "a.png"
    _make_png(src)
    (tmp_path / "a.bmp").write_bytes(b"existing")
    result = convert_file(src, "bmp", "image")
    assert result.success is True
    assert result.out_path == tmp_path / "a-1.bmp"
