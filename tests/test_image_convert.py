import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mediaconvert.image_convert import ImageOptions, _largest_ico_frame_index, _run, convert_image


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


def _ok_result():
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def test_convert_png_to_png_lossless_runs_oxipng_only(tmp_path):
    src = tmp_path / "a.png"
    out = tmp_path / "a-1.png"
    _make_png(src)
    options = ImageOptions(png_optimize=True, png_mode="lossless", oxipng_level=3)
    with patch("mediaconvert.image_convert.subprocess.run", return_value=_ok_result()) as mock_run:
        convert_image(src, out, "png", options)
    assert out.exists()  # copied from src before oxipng (mocked) runs on it
    assert mock_run.call_count == 1
    (cmd,), _ = mock_run.call_args
    assert cmd[0] == "oxipng"
    assert "-o" in cmd and cmd[cmd.index("-o") + 1] == "3"
    assert cmd[-1] == str(out)


def test_convert_png_to_png_lossy_runs_pngquant_then_oxipng(tmp_path):
    src = tmp_path / "a.png"
    out = tmp_path / "a-1.png"
    _make_png(src)
    options = ImageOptions(png_optimize=True, png_mode="lossy", pngquant_quality_min=70, oxipng_level=2)
    with patch("mediaconvert.image_convert.subprocess.run", return_value=_ok_result()) as mock_run:
        convert_image(src, out, "png", options)
    assert mock_run.call_count == 2
    (pngquant_cmd,), _ = mock_run.call_args_list[0]
    (oxipng_cmd,), _ = mock_run.call_args_list[1]
    assert pngquant_cmd[0] == "pngquant"
    assert "--quality=70-100" in pngquant_cmd
    assert pngquant_cmd[-1] == str(out)
    assert oxipng_cmd[0] == "oxipng"
    assert "-o" in oxipng_cmd and oxipng_cmd[oxipng_cmd.index("-o") + 1] == "2"
    assert "--out" in oxipng_cmd and oxipng_cmd[oxipng_cmd.index("--out") + 1] == str(out)
    # oxipng must read pngquant's temp output, not the original source.
    assert oxipng_cmd[-1] == pngquant_cmd[pngquant_cmd.index("--output") + 1]


def test_convert_bmp_to_png_still_optimizes(tmp_path):
    png_src = tmp_path / "a.png"
    src = tmp_path / "a.bmp"
    out = tmp_path / "a-1.png"
    _make_png(png_src)
    subprocess.run(["magick", str(png_src), str(src)], check=True, capture_output=True)
    with patch("mediaconvert.image_convert.subprocess.run", return_value=_ok_result()) as mock_run:
        convert_image(src, out, "png", ImageOptions(png_optimize=True, png_mode="lossless", oxipng_level=1))
    assert mock_run.call_count == 2
    (magick_cmd,), _ = mock_run.call_args_list[0]
    (oxipng_cmd,), _ = mock_run.call_args_list[1]
    assert magick_cmd[0] == "magick"
    assert magick_cmd[-1] == str(out)
    assert oxipng_cmd[0] == "oxipng"
    assert oxipng_cmd[-1] == str(out)


def test_convert_jpg_to_jpg_optimizes_with_jpegoptim(tmp_path):
    src = tmp_path / "a.jpg"
    out = tmp_path / "a-1.jpg"
    _make_png(src.with_suffix(".png"))
    subprocess.run(
        ["magick", str(src.with_suffix(".png")), str(src)], check=True, capture_output=True,
    )
    options = ImageOptions(jpeg_optimize=True, jpeg_quality=72)
    with patch("mediaconvert.image_convert.subprocess.run", return_value=_ok_result()) as mock_run:
        convert_image(src, out, "jpg", options)
    assert out.exists()  # copied from src before jpegoptim (mocked) runs on it
    (cmd,), _ = mock_run.call_args
    assert cmd[0] == "jpegoptim"
    assert "--max=72" in cmd
    assert cmd[-1] == str(out)


def test_convert_jpeg_source_to_jpg_target_is_treated_as_same_format(tmp_path):
    src = tmp_path / "a.jpeg"
    out = tmp_path / "a-1.jpg"
    _make_png(src.with_suffix(".png"))
    subprocess.run(
        ["magick", str(src.with_suffix(".png")), str(src)], check=True, capture_output=True,
    )
    with patch("mediaconvert.image_convert.subprocess.run", return_value=_ok_result()) as mock_run:
        convert_image(src, out, "jpg", ImageOptions(jpeg_optimize=True))
    (cmd,), _ = mock_run.call_args
    assert cmd[0] == "jpegoptim"


def test_convert_png_to_png_uses_plain_magick_by_default(tmp_path):
    src = tmp_path / "a.png"
    out = tmp_path / "a-1.png"
    _make_png(src)
    with patch("mediaconvert.image_convert.subprocess.run", return_value=_ok_result()) as mock_run:
        convert_image(src, out, "png", ImageOptions())
    assert mock_run.call_count == 1
    (cmd,), _ = mock_run.call_args
    assert cmd == ["magick", str(src), str(out)]


def test_convert_jpg_to_jpg_uses_plain_magick_by_default(tmp_path):
    src = tmp_path / "a.jpg"
    out = tmp_path / "a-1.jpg"
    _make_png(src.with_suffix(".png"))
    subprocess.run(
        ["magick", str(src.with_suffix(".png")), str(src)], check=True, capture_output=True,
    )
    with patch("mediaconvert.image_convert.subprocess.run", return_value=_ok_result()) as mock_run:
        convert_image(src, out, "jpg", ImageOptions())
    assert mock_run.call_count == 1
    (cmd,), _ = mock_run.call_args
    assert cmd == ["magick", str(src), str(out)]


def test_convert_bmp_to_jpg_still_optimizes(tmp_path):
    png_src = tmp_path / "a.png"
    src = tmp_path / "a.bmp"
    out = tmp_path / "a-1.jpg"
    _make_png(png_src)
    subprocess.run(["magick", str(png_src), str(src)], check=True, capture_output=True)
    with patch("mediaconvert.image_convert.subprocess.run", return_value=_ok_result()) as mock_run:
        convert_image(src, out, "jpg", ImageOptions(jpeg_optimize=True, jpeg_quality=90))
    assert mock_run.call_count == 2
    (magick_cmd,), _ = mock_run.call_args_list[0]
    (jpegoptim_cmd,), _ = mock_run.call_args_list[1]
    assert magick_cmd[0] == "magick"
    assert magick_cmd[-1] == str(out)
    assert jpegoptim_cmd[0] == "jpegoptim"
    assert "--max=90" in jpegoptim_cmd
    assert jpegoptim_cmd[-1] == str(out)
