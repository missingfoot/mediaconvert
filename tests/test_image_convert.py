import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mediaconvert.image_convert import _largest_ico_frame_index, _run, convert_image


def _make_png(path: Path, size="32x32", color="red"):
    subprocess.run(
        ["magick", "-size", size, f"xc:{color}", str(path)],
        check=True, capture_output=True,
    )


def _make_ico(path: Path):
    # Two frames: 16x16 and 32x32 - the 32x32 one should be picked.
    small = path.with_suffix(".small.png")
    large = path.with_suffix(".large.png")
    _make_png(small, "16x16", "blue")
    _make_png(large, "32x32", "green")
    subprocess.run(
        ["magick", str(small), str(large), str(path)],
        check=True, capture_output=True,
    )


def _make_animated_gif(path: Path):
    frame1 = path.with_suffix(".f1.png")
    frame2 = path.with_suffix(".f2.png")
    _make_png(frame1, "16x16", "red")
    _make_png(frame2, "16x16", "blue")
    subprocess.run(
        ["magick", "-delay", "10", str(frame1), str(frame2), str(path)],
        check=True, capture_output=True,
    )


def test_convert_png_to_bmp(tmp_path):
    src = tmp_path / "a.png"
    out = tmp_path / "a.bmp"
    _make_png(src)
    convert_image(src, out, "bmp")
    assert out.exists()
    identify = subprocess.run(
        ["magick", "identify", "-format", "%m", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert identify.stdout.strip() == "BMP"


def test_convert_png_to_webp_uses_cwebp(tmp_path):
    src = tmp_path / "a.png"
    out = tmp_path / "a.webp"
    _make_png(src)
    convert_image(src, out, "webp")
    assert out.exists()
    identify = subprocess.run(
        ["magick", "identify", "-format", "%m", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert identify.stdout.strip() == "WEBP"


def test_convert_animated_gif_to_webp_uses_gif2webp(tmp_path):
    src = tmp_path / "a.gif"
    out = tmp_path / "a.webp"
    _make_animated_gif(src)
    convert_image(src, out, "webp")
    assert out.exists()
    # gif2webp output on an animated source stays animated (multi-frame);
    # cwebp on a flattened frame would not.
    frames = subprocess.run(
        ["magick", "identify", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert len(frames.stdout.strip().splitlines()) > 1


def test_convert_ico_picks_largest_frame(tmp_path):
    src = tmp_path / "a.ico"
    out = tmp_path / "a.png"
    _make_ico(src)
    convert_image(src, out, "png")
    assert out.exists()
    identify = subprocess.run(
        ["magick", "identify", "-format", "%wx%h", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert identify.stdout.strip() == "32x32"


def test_convert_ico_to_webp_picks_largest_frame(tmp_path):
    src = tmp_path / "a.ico"
    out = tmp_path / "a.webp"
    _make_ico(src)
    convert_image(src, out, "webp")
    assert out.exists()
    identify = subprocess.run(
        ["magick", "identify", "-format", "%wx%h,%m", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert identify.stdout.strip() == "32x32,WEBP"


def test_convert_bmp_to_webp(tmp_path):
    png_src = tmp_path / "a.png"
    src = tmp_path / "a.bmp"
    out = tmp_path / "a.webp"
    _make_png(png_src)
    subprocess.run(
        ["magick", str(png_src), str(src)],
        check=True, capture_output=True,
    )
    convert_image(src, out, "webp")
    assert out.exists()
    identify = subprocess.run(
        ["magick", "identify", "-format", "%m", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert identify.stdout.strip() == "WEBP"


def _magick_supports_avif() -> bool:
    result = subprocess.run(
        ["magick", "-list", "format"], capture_output=True, text=True,
    )
    return "AVIF" in result.stdout


@pytest.mark.skipif(not _magick_supports_avif(), reason="magick build lacks AVIF support")
def test_convert_avif_to_webp(tmp_path):
    png_src = tmp_path / "a.png"
    src = tmp_path / "a.avif"
    out = tmp_path / "a.webp"
    _make_png(png_src)
    subprocess.run(
        ["magick", str(png_src), str(src)],
        check=True, capture_output=True,
    )
    convert_image(src, out, "webp")
    assert out.exists()
    identify = subprocess.run(
        ["magick", "identify", "-format", "%m", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert identify.stdout.strip() == "WEBP"


def test_convert_failure_raises_runtime_error(tmp_path):
    src = tmp_path / "not_an_image.png"
    src.write_text("this is not an image")
    out = tmp_path / "out.bmp"
    with pytest.raises(RuntimeError):
        convert_image(src, out, "bmp")


def test_largest_ico_frame_index_handles_malformed_identify_output(tmp_path):
    src = tmp_path / "a.ico"
    src.write_bytes(b"stub")
    fake_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="not-a-dimension\n", stderr="")
    with patch("mediaconvert.image_convert.subprocess.run", return_value=fake_result):
        assert _largest_ico_frame_index(src) == 0


def test_run_redirects_stdin_and_sets_timeout():
    with patch("mediaconvert.image_convert.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        _run(["magick", "a", "b"])
    _, kwargs = mock_run.call_args
    assert kwargs.get("stdin") == subprocess.DEVNULL
    assert kwargs.get("timeout")


def test_run_timeout_reports_as_failure_not_hang():
    with patch("mediaconvert.image_convert.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="magick", timeout=1)):
        with pytest.raises(RuntimeError, match="timed out"):
            _run(["magick", "a", "b"])
