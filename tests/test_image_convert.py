import subprocess
from pathlib import Path

import pytest

from mediaconvert.image_convert import convert_image


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


def test_convert_failure_raises_runtime_error(tmp_path):
    src = tmp_path / "not_an_image.png"
    src.write_text("this is not an image")
    out = tmp_path / "out.bmp"
    with pytest.raises(RuntimeError):
        convert_image(src, out, "bmp")
