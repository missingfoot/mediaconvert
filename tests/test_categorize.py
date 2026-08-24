from pathlib import Path

import pytest

from mediaconvert.categorize import (
    IMAGE_FORMATS,
    VIDEO_FORMATS,
    AUDIO_FORMATS,
    MixedCategoryError,
    categorize,
    target_formats,
)


def test_image_formats_expected_members():
    assert {"png", "jpg", "jpeg", "webp", "avif", "heic", "ico", "bmp", "tiff", "gif", "jfif"} <= IMAGE_FORMATS


def test_video_formats_expected_members():
    assert {"mp4", "mkv", "webm", "mov", "avi", "wmv", "swf", "vob", "ogv", "ogg", "ts", "m2ts", "mts", "m4v", "mpeg", "mpg"} <= VIDEO_FORMATS


def test_audio_formats_expected_members():
    assert {"mp3", "wav", "flac", "aac", "opus", "m4a", "m4b", "aiff", "aifc", "voc"} <= AUDIO_FORMATS


def test_categorize_all_images():
    paths = [Path("a.png"), Path("b.JPG"), Path("c.webp")]
    assert categorize(paths) == "image"


def test_categorize_all_video():
    paths = [Path("a.mp4"), Path("b.mkv")]
    assert categorize(paths) == "video"


def test_categorize_all_audio():
    paths = [Path("a.mp3"), Path("b.WAV")]
    assert categorize(paths) == "audio"


def test_categorize_mixed_raises():
    paths = [Path("a.png"), Path("b.mp4")]
    with pytest.raises(MixedCategoryError):
        categorize(paths)


def test_categorize_unknown_extension_raises():
    with pytest.raises(MixedCategoryError):
        categorize([Path("a.xyz")])


def test_target_formats_image_is_just_image_formats():
    assert set(target_formats("image")) == IMAGE_FORMATS


def test_target_formats_audio_is_just_audio_formats():
    assert set(target_formats("audio")) == AUDIO_FORMATS


def test_target_formats_video_adds_gif_webp_and_audio():
    formats = set(target_formats("video"))
    assert VIDEO_FORMATS <= formats
    assert "gif" in formats
    assert "webp" in formats
    assert AUDIO_FORMATS <= formats
