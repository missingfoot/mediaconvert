import os
import time
from pathlib import Path

from mediaconvert.naming import resolve_output_path, copy_mtime


def test_resolve_output_path_no_collision(tmp_path):
    src = tmp_path / "photo.png"
    src.write_bytes(b"x")
    out = resolve_output_path(src, "webp")
    assert out == tmp_path / "photo.webp"


def test_resolve_output_path_collision_suffixes(tmp_path):
    src = tmp_path / "photo.png"
    src.write_bytes(b"x")
    (tmp_path / "photo.webp").write_bytes(b"existing")
    out = resolve_output_path(src, "webp")
    assert out == tmp_path / "photo-1.webp"


def test_resolve_output_path_multiple_collisions(tmp_path):
    src = tmp_path / "photo.png"
    src.write_bytes(b"x")
    (tmp_path / "photo.webp").write_bytes(b"existing")
    (tmp_path / "photo-1.webp").write_bytes(b"existing")
    out = resolve_output_path(src, "webp")
    assert out == tmp_path / "photo-2.webp"


def test_resolve_output_path_same_format_as_source_still_gets_suffix(tmp_path):
    src = tmp_path / "photo.png"
    src.write_bytes(b"x")
    out = resolve_output_path(src, "png")
    assert out == tmp_path / "photo-1.png"


def test_copy_mtime(tmp_path):
    src = tmp_path / "a.png"
    dst = tmp_path / "b.webp"
    src.write_bytes(b"x")
    dst.write_bytes(b"y")
    old_time = time.time() - 10000
    os.utime(src, (old_time, old_time))
    copy_mtime(src, dst)
    assert dst.stat().st_mtime == src.stat().st_mtime
