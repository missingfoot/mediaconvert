from pathlib import Path

from mediaconvert.categorize import (
    AUDIO_FORMATS,
    IMAGE_FORMATS,
    VIDEO_FORMATS,
    category_of,
    split_by_category,
    target_formats,
)


def test_image_formats_expected_members():
    assert {"png", "jpg", "jpeg", "webp", "avif", "heic", "ico", "bmp", "tiff", "gif", "jfif"} <= IMAGE_FORMATS


def test_video_formats_expected_members():
    assert {"mp4", "mkv", "webm", "mov", "avi", "wmv", "swf", "vob", "ogv", "ogg", "ts", "m2ts", "mts", "m4v", "mpeg", "mpg"} <= VIDEO_FORMATS


def test_audio_formats_expected_members():
    assert {"mp3", "wav", "flac", "aac", "opus", "m4a", "m4b", "aiff", "aifc", "voc"} <= AUDIO_FORMATS


def test_category_of_image():
    assert category_of(Path("a.PNG")) == "image"


def test_category_of_video():
    assert category_of(Path("a.mp4")) == "video"


def test_category_of_audio():
    assert category_of(Path("a.WAV")) == "audio"


def test_category_of_unknown_returns_none():
    assert category_of(Path("a.xyz")) is None


def test_split_by_category_all_images():
    paths = [Path("a.png"), Path("b.JPG"), Path("c.webp")]
    groups, ignored = split_by_category(paths)
    assert groups == {"image": paths}
    assert ignored == []


def test_split_by_category_mixed_batch_splits_cleanly():
    a, b, c, d = Path("a.png"), Path("b.mp4"), Path("c.mp3"), Path("d.jpg")
    groups, ignored = split_by_category([a, b, c, d])
    assert groups == {"image": [a, d], "video": [b], "audio": [c]}
    assert ignored == []


def test_split_by_category_unknown_extension_is_ignored():
    known, unknown = Path("a.png"), Path("b.xyz")
    groups, ignored = split_by_category([known, unknown])
    assert groups == {"image": [known]}
    assert ignored == [unknown]


def test_split_by_category_preserves_order_within_group():
    paths = [Path("b.png"), Path("a.png")]
    groups, _ = split_by_category(paths)
    assert groups["image"] == paths


def test_split_by_category_empty_input():
    groups, ignored = split_by_category([])
    assert groups == {}
    assert ignored == []


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
