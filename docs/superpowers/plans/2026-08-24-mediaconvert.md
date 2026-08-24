# mediaconvert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `mediaconvert`, a drag-and-drop PySide6 desktop app that converts images, video, or audio files (one category at a time) to a chosen output format using ImageMagick, libwebp, and ffmpeg as backends.

**Architecture:** A small Python package (`src/mediaconvert/`) with pure-logic modules (category detection, output-path naming) that are unit tested directly, conversion modules that shell out to `magick`/`cwebp`/`gif2webp`/`ffmpeg` and are tested against real tiny sample files (these tools are already installed — no mocking), and a PySide6 UI module that wires it all together. Packaged the same way as the sibling `clipcut` app: a thin `/usr/bin/mediaconvert` launcher + `.desktop` file, built via PKGBUILD, versioned by bumping only the PKGBUILD patch number.

**Tech Stack:** Python 3, PySide6 6.11 (`import PySide6`), pytest, subprocess calls to `magick` (imagemagick 7.1.2), `cwebp`/`gif2webp` (libwebp-utils 1.6.0), `ffmpeg` (9.0.1).

**Spec:** `docs/superpowers/specs/2026-08-24-mediaconvert-design.md`

## Global Constraints

- UI is ImageOptim-style: dashed drop-zone empty state → flat file-list view on drop, with a toolbar above the list (info label + "Convert to:" dropdown) and an ImageOptim-shaped bottom bar (`+` / status label / action button) (spec: UI flow #1-3, #6).
- One target format applies to the whole batch, not per-file (spec: UI flow #5).
- A batch must be a single category (image, video, or audio); mixed categories are rejected outright, shown as an inline message in place of the file list, never auto-split (spec: UI flow #4).
- Video batches may target video formats, `gif`, `webp` (animated via ffmpeg), or any audio format (extraction) (spec: UI flow #5).
- File rows show icon + filename + status text only (`Ready`/`Converting…`/`Done`/`Failed: <reason>`) — no size or savings column (spec: UI flow #2).
- Output file: same directory/basename as source, new extension; on name collision try `-1`, `-2`, ... suffixes; output mtime is set to match the source file's mtime (spec: Output behavior).
- WebP output always goes through `cwebp`/`gif2webp`, never `magick ... output.webp` directly (spec: Format lists).
- `.ico` source: pick the single largest embedded frame (by pixel area via `magick identify -format "%wx%h\n"`), not every frame (spec: Format lists).
- Image formats: avif, bmp, gif, heic, ico, jfif, jpeg/jpg, png, tiff, webp.
- Video formats: avi, m2ts, m4v, mkv, mov, mp4, mpeg/mpg, mts, ogg, ogv, swf, ts, vob, webm, wmv.
- Audio formats: aac, aifc, aiff, flac, m4a, m4b, mp3, opus, voc, wav.
- No right-click/service-menu integration; launcher app only (spec: Out of scope).
- No per-file format pickers, no trim/crop/bitrate controls, no auto-splitting mixed batches (spec: Out of scope).
- No automated GUI test suite planned — manual verification only for the UI module, matching clipcut's convention (spec: Testing).

---

## File Structure

- `src/mediaconvert/__init__.py` — empty, marks package.
- `src/mediaconvert/categorize.py` — format lists per category + `categorize(paths)` batch validation.
- `src/mediaconvert/naming.py` — `resolve_output_path(src, fmt)` (collision-avoiding path) + `copy_mtime(src, dst)`.
- `src/mediaconvert/image_convert.py` — `convert_image(src, out_path, fmt)`: magick/cwebp/gif2webp/ico-frame logic ported from `convert-image.sh`.
- `src/mediaconvert/media_convert.py` — `convert_media(src, out_path, fmt)`: ffmpeg-based video/audio conversion, including video→gif/webp and video→audio extraction.
- `src/mediaconvert/converter.py` — `convert_file(src, fmt)`: dispatches to image/media converter by category, resolves output path, copies mtime, returns a result object.
- `src/mediaconvert/ui.py` — `MainWindow` (PySide6): drop zone, file list, format dropdown, Convert button, per-file status.
- `src/mediaconvert/__main__.py` — `main()` entry point, creates `QApplication`, shows `MainWindow`.
- `src/mediaconvert.desktop` — desktop entry (mirrors `clipcut.desktop`).
- `mediaconvert` (repo root) — thin launcher script installed to `/usr/bin/mediaconvert`.
- `PKGBUILD` — Arch package build script.
- `tests/test_categorize.py`, `tests/test_naming.py`, `tests/test_image_convert.py`, `tests/test_media_convert.py`, `tests/test_converter.py`.

---

## Task 1: Category detection and format lists

**Files:**
- Create: `src/mediaconvert/__init__.py` (empty)
- Create: `src/mediaconvert/categorize.py`
- Test: `tests/test_categorize.py`

**Interfaces:**
- Produces: `IMAGE_FORMATS: set[str]`, `VIDEO_FORMATS: set[str]`, `AUDIO_FORMATS: set[str]` (all lowercase, no leading dot). `class MixedCategoryError(Exception)`. `categorize(paths: list[Path]) -> str` returns `"image"`, `"video"`, or `"audio"`; raises `MixedCategoryError` if `paths` span more than one category or contains an unrecognized extension. `target_formats(category: str) -> list[str]` returns the selectable output formats for a batch of that category (video adds `gif`, `webp`, and all audio formats on top of `VIDEO_FORMATS`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_categorize.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_categorize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mediaconvert'`

- [ ] **Step 3: Write the implementation**

Create `src/mediaconvert/__init__.py` (empty file).

Create `src/mediaconvert/categorize.py`:

```python
"""Format lists and batch category detection for mediaconvert."""

from pathlib import Path

IMAGE_FORMATS = {
    "avif", "bmp", "gif", "heic", "ico", "jfif", "jpeg", "jpg", "png",
    "tiff", "webp",
}

VIDEO_FORMATS = {
    "avi", "m2ts", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "mts",
    "ogg", "ogv", "swf", "ts", "vob", "webm", "wmv",
}

AUDIO_FORMATS = {
    "aac", "aifc", "aiff", "flac", "m4a", "m4b", "mp3", "opus", "voc",
    "wav",
}

_ALL_FORMATS = IMAGE_FORMATS | VIDEO_FORMATS | AUDIO_FORMATS


class MixedCategoryError(Exception):
    """Raised when a batch mixes categories or contains an unknown extension."""


def _category_of(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in IMAGE_FORMATS:
        return "image"
    if ext in VIDEO_FORMATS:
        return "video"
    if ext in AUDIO_FORMATS:
        return "audio"
    raise MixedCategoryError(f"Unrecognized file type: {path.name}")


def categorize(paths: list[Path]) -> str:
    """Return "image", "video", or "audio" for a batch, or raise MixedCategoryError."""
    categories = {_category_of(p) for p in paths}
    if len(categories) != 1:
        raise MixedCategoryError(
            "Can't mix images, video, and audio in one batch"
        )
    return categories.pop()


def target_formats(category: str) -> list[str]:
    """Selectable output formats for a batch of the given category."""
    if category == "image":
        return sorted(IMAGE_FORMATS)
    if category == "audio":
        return sorted(AUDIO_FORMATS)
    if category == "video":
        return sorted(VIDEO_FORMATS | {"gif", "webp"} | AUDIO_FORMATS)
    raise ValueError(f"Unknown category: {category}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_categorize.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/mediaconvert
git add src/mediaconvert/__init__.py src/mediaconvert/categorize.py tests/test_categorize.py
git commit -m "Add category detection and format lists"
```

---

## Task 2: Output path naming and mtime preservation

**Files:**
- Create: `src/mediaconvert/naming.py`
- Test: `tests/test_naming.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `resolve_output_path(src: Path, fmt: str) -> Path` (does not create the file — just computes the non-colliding path). `copy_mtime(src: Path, dst: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_naming.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_naming.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mediaconvert.naming'`

- [ ] **Step 3: Write the implementation**

Create `src/mediaconvert/naming.py`:

```python
"""Output path resolution and mtime preservation for mediaconvert."""

import os
from pathlib import Path


def resolve_output_path(src: Path, fmt: str) -> Path:
    """Same dir/basename as src with a new extension; -1, -2, ... on collision.

    Always returns a path distinct from src, even when fmt matches src's
    extension (self-conversion still produces a numbered sibling, never
    overwrites the source).
    """
    directory = src.parent
    name = src.stem
    candidate = directory / f"{name}.{fmt}"
    if candidate == src or candidate.exists():
        i = 1
        while True:
            candidate = directory / f"{name}-{i}.{fmt}"
            if candidate != src and not candidate.exists():
                return candidate
            i += 1
    return candidate


def copy_mtime(src: Path, dst: Path) -> None:
    """Set dst's mtime (and atime) to match src's, like `touch -r`."""
    stat = os.stat(src)
    os.utime(dst, (stat.st_atime, stat.st_mtime))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_naming.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/mediaconvert
git add src/mediaconvert/naming.py tests/test_naming.py
git commit -m "Add output path naming and mtime preservation"
```

---

## Task 3: Image conversion backend

**Files:**
- Create: `src/mediaconvert/image_convert.py`
- Test: `tests/test_image_convert.py`

**Interfaces:**
- Consumes: nothing from Tasks 1-2 (works on raw `src`/`out_path`/`fmt` args; category routing happens in Task 5).
- Produces: `convert_image(src: Path, out_path: Path, fmt: str) -> None`, raising `RuntimeError` with a descriptive message on failure. Used by `converter.py` (Task 5).

This task requires generating real tiny sample images in tests (PNG, animated GIF, and an ICO with two frames) using `magick`, since these binaries are already installed and we want real integration coverage rather than mocked subprocess calls.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_image_convert.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_image_convert.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mediaconvert.image_convert'`

- [ ] **Step 3: Write the implementation**

Create `src/mediaconvert/image_convert.py`:

```python
"""Image conversion backend: ImageMagick for general formats, libwebp for WebP output."""

import subprocess
import tempfile
from pathlib import Path


def _largest_ico_frame_index(src: Path) -> int:
    """Index of the largest frame (by pixel area) in a multi-frame .ico."""
    result = subprocess.run(
        ["magick", "identify", "-format", "%wx%h\n", str(src)],
        capture_output=True, text=True,
    )
    best_idx = 0
    best_area = -1
    for idx, line in enumerate(result.stdout.strip().splitlines()):
        w, _, h = line.partition("x")
        area = int(w) * int(h)
        if area > best_area:
            best_area = area
            best_idx = idx
    return best_idx


def _magick_src(src: Path) -> str:
    """The path/frame-selector magick should read from (handles multi-frame .ico)."""
    if src.suffix.lower() == ".ico":
        return f"{src}[{_largest_ico_frame_index(src)}]"
    return str(src)


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Command failed: {' '.join(cmd)}")


def _convert_to_webp(src: Path, magick_src: str, out_path: Path) -> None:
    is_animated_gif = src.suffix.lower() == ".gif"
    if is_animated_gif:
        result = subprocess.run(
            ["gif2webp", "-lossy", "-q", "85", "-m", "4", str(src), "-o", str(out_path)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return
        # Fall through to cwebp if gif2webp fails (e.g. non-animated .gif).

    if magick_src == str(src):
        cwebp_src = str(src)
        _run(["cwebp", "-q", "90", cwebp_src, "-o", str(out_path)])
    else:
        # magick_src references a frame index (e.g. an .ico) - cwebp needs a
        # real file, so extract that frame to a temp PNG first.
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
            _run(["magick", magick_src, tmp.name])
            _run(["cwebp", "-q", "90", tmp.name, "-o", str(out_path)])


def convert_image(src: Path, out_path: Path, fmt: str) -> None:
    """Convert an image file to fmt, writing to out_path.

    Raises RuntimeError on failure.
    """
    magick_src = _magick_src(src)
    if fmt == "webp":
        _convert_to_webp(src, magick_src, out_path)
    else:
        _run(["magick", magick_src, str(out_path)])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_image_convert.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/mediaconvert
git add src/mediaconvert/image_convert.py tests/test_image_convert.py
git commit -m "Add image conversion backend (magick + libwebp)"
```

---

## Task 4: Video/audio conversion backend

**Files:**
- Create: `src/mediaconvert/media_convert.py`
- Test: `tests/test_media_convert.py`

**Interfaces:**
- Consumes: `AUDIO_FORMATS` from `mediaconvert.categorize` (Task 1) to decide whether an ffmpeg target is audio-only (drop video stream).
- Produces: `convert_media(src: Path, out_path: Path, fmt: str) -> None`, raising `RuntimeError` on failure. Used by `converter.py` (Task 5).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_media_convert.py`:

```python
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
        ["magick", "identify", "-format", "%m", str(out)],
        check=True, capture_output=True, text=True,
    )
    assert result.stdout.strip() == "GIF"


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_media_convert.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mediaconvert.media_convert'`

- [ ] **Step 3: Write the implementation**

Create `src/mediaconvert/media_convert.py`:

```python
"""Video/audio conversion backend: ffmpeg for everything, including
video->gif/webp (animated) and video->audio extraction."""

import subprocess
from pathlib import Path

from mediaconvert.categorize import AUDIO_FORMATS


def convert_media(src: Path, out_path: Path, fmt: str) -> None:
    """Convert a video or audio file to fmt, writing to out_path.

    Raises RuntimeError on failure.
    """
    cmd = ["ffmpeg", "-y", "-i", str(src)]

    if fmt in AUDIO_FORMATS:
        # Extraction (source may be video or audio) - drop any video stream.
        cmd += ["-vn"]
    elif fmt == "gif":
        cmd += ["-vf", "fps=15,scale=480:-1:flags=lanczos"]
    elif fmt == "webp":
        cmd += ["-vf", "fps=15,scale=480:-1:flags=lanczos", "-loop", "0"]

    cmd += [str(out_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-2000:] or f"ffmpeg failed converting {src.name}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_media_convert.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/mediaconvert
git add src/mediaconvert/media_convert.py tests/test_media_convert.py
git commit -m "Add video/audio conversion backend (ffmpeg)"
```

---

## Task 5: Top-level converter (dispatch + naming + mtime)

**Files:**
- Create: `src/mediaconvert/converter.py`
- Test: `tests/test_converter.py`

**Interfaces:**
- Consumes: `categorize` (Task 1, used indirectly via category param), `resolve_output_path`/`copy_mtime` (Task 2), `convert_image` (Task 3), `convert_media` (Task 4).
- Produces: `@dataclass ConversionResult(src: Path, out_path: Path | None, success: bool, error: str | None)`. `convert_file(src: Path, fmt: str, category: str) -> ConversionResult` — never raises; catches backend `RuntimeError` and reports it in the result. Used by `ui.py` (Task 6).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_converter.py`:

```python
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


def test_convert_file_collision_gets_suffix(tmp_path):
    src = tmp_path / "a.png"
    _make_png(src)
    (tmp_path / "a.bmp").write_bytes(b"existing")
    result = convert_file(src, "bmp", "image")
    assert result.success is True
    assert result.out_path == tmp_path / "a-1.bmp"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_converter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mediaconvert.converter'`

- [ ] **Step 3: Write the implementation**

Create `src/mediaconvert/converter.py`:

```python
"""Top-level per-file conversion: dispatch to a backend, resolve output
path, preserve mtime, and report success/failure without raising."""

from dataclasses import dataclass
from pathlib import Path

from mediaconvert.image_convert import convert_image
from mediaconvert.media_convert import convert_media
from mediaconvert.naming import copy_mtime, resolve_output_path


@dataclass
class ConversionResult:
    src: Path
    out_path: Path | None
    success: bool
    error: str | None


def convert_file(src: Path, fmt: str, category: str) -> ConversionResult:
    """Convert src to fmt. Never raises - failures are reported in the result."""
    out_path = resolve_output_path(src, fmt)
    try:
        if category == "image":
            convert_image(src, out_path, fmt)
        else:
            convert_media(src, out_path, fmt)
        copy_mtime(src, out_path)
        return ConversionResult(src=src, out_path=out_path, success=True, error=None)
    except RuntimeError as e:
        return ConversionResult(src=src, out_path=None, success=False, error=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/test_converter.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full test suite so far**

Run: `cd ~/Projects/mediaconvert && python3 -m pytest tests/ -v`
Expected: PASS (all tests from Tasks 1-5)

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/mediaconvert
git add src/mediaconvert/converter.py tests/test_converter.py
git commit -m "Add top-level converter dispatch"
```

---

## Task 6: PySide6 UI (ImageOptim-style drop-zone → list view)

**Files:**
- Create: `src/mediaconvert/ui.py`
- Create: `src/mediaconvert/__main__.py`

**Interfaces:**
- Consumes: `categorize`, `target_formats`, `MixedCategoryError` (Task 1); `convert_file`, `ConversionResult` (Task 5).
- Produces: `class MainWindow(QMainWindow)`. `main()` in `__main__.py` — creates `QApplication`, instantiates `MainWindow`, calls `.show()`, runs `app.exec()`.

No automated tests for this task (per spec: manual verification only for the UI, matching clipcut's convention). Steps are implementation + a manual smoke test.

The window has two states, swapped via a `QStackedWidget`: an **empty state** (dashed drop-zone box, ImageOptim-style) and a **list state** (toolbar + file list, shown once files are present). Both states share the same bottom bar, whose middle/right widgets change between the two states.

- [ ] **Step 1: Write the UI implementation**

Create `src/mediaconvert/ui.py`:

```python
"""mediaconvert main window: ImageOptim-style drag-and-drop batch format conversion."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mediaconvert.categorize import MixedCategoryError, categorize, target_formats
from mediaconvert.converter import convert_file


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("mediaconvert")
        self.resize(560, 420)
        self.setAcceptDrops(True)

        self._paths: list[Path] = []
        self._category: str | None = None

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.stack.addWidget(self._build_empty_page())
        self.stack.addWidget(self._build_list_page())

        root.addWidget(self._build_bottom_bar())

        self.setCentralWidget(central)
        self._show_empty_state("Drag and drop image, video, or audio files onto the area above")

    # -- page builders ----------------------------------------------------

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        drop_box = QFrame()
        drop_box.setObjectName("dropBox")
        drop_box.setStyleSheet(
            "#dropBox { border: 2px dashed palette(mid); border-radius: 8px; }"
        )
        box_layout = QVBoxLayout(drop_box)
        arrow = QLabel("⬇")  # down arrow
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setStyleSheet("font-size: 48px; color: palette(mid);")
        box_layout.addWidget(arrow)
        layout.addWidget(drop_box, stretch=1)
        return page

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 6)
        self.info_label = QLabel("")
        toolbar.addWidget(self.info_label)
        toolbar.addStretch(1)
        toolbar.addWidget(QLabel("Convert to:"))
        self.format_combo = QComboBox()
        toolbar.addWidget(self.format_combo)
        layout.addLayout(toolbar)

        self.file_list = QListWidget()
        layout.addWidget(self.file_list, stretch=1)

        self.reject_label = QLabel("")
        self.reject_label.setAlignment(Qt.AlignCenter)
        self.reject_label.setWordWrap(True)
        layout.addWidget(self.reject_label)

        return page

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 6, 8, 6)

        self.add_button = QPushButton("+")
        self.add_button.setFixedWidth(32)
        self.add_button.clicked.connect(self._open_files_dialog)
        layout.addWidget(self.add_button)

        self.bottom_status_label = QLabel("")
        layout.addWidget(self.bottom_status_label, stretch=1)

        self.convert_button = QPushButton("Convert")
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(self._convert_batch)
        layout.addWidget(self.convert_button)

        return bar

    # -- state transitions --------------------------------------------------

    def _show_empty_state(self, hint: str) -> None:
        self.stack.setCurrentIndex(0)
        self.bottom_status_label.setText(hint)
        self.convert_button.setEnabled(False)

    def _show_list_state(self, category: str) -> None:
        self.stack.setCurrentIndex(1)
        self.reject_label.setText("")
        self.file_list.show()
        self.info_label.setText(f"{len(self._paths)} file(s) added")
        self.bottom_status_label.setText("")
        self.convert_button.setEnabled(True)

    def _show_rejected_state(self, message: str) -> None:
        self.stack.setCurrentIndex(1)
        self.file_list.clear()
        self.file_list.hide()
        self.info_label.setText("")
        self.reject_label.setText(message)
        self.bottom_status_label.setText("")
        self.convert_button.setEnabled(False)

    # -- drag and drop / file dialog ----------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self._load_paths(paths)

    def _open_files_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Open files")
        if files:
            self._load_paths([Path(f) for f in files])

    # -- batch loading and conversion ---------------------------------------

    def _load_paths(self, paths: list[Path]) -> None:
        if not paths:
            return
        try:
            category = categorize(paths)
        except MixedCategoryError as e:
            self._paths = []
            self._category = None
            self._show_rejected_state(str(e))
            return

        self._paths = paths
        self._category = category

        self.file_list.clear()
        self.file_list.show()
        for p in paths:
            self.file_list.addItem(QListWidgetItem(f"{p.name}  —  Ready"))

        self.format_combo.clear()
        self.format_combo.addItems(target_formats(category))

        self._show_list_state(category)

    def _convert_batch(self) -> None:
        fmt = self.format_combo.currentText()
        if not fmt or not self._paths:
            return
        self.convert_button.setEnabled(False)

        success_count = 0
        for i, path in enumerate(self._paths):
            item = self.file_list.item(i)
            item.setText(f"{path.name}  —  Converting…")
            result = convert_file(path, fmt, self._category)
            if result.success:
                success_count += 1
                item.setText(f"{path.name}  —  Done")
            else:
                item.setText(f"{path.name}  —  Failed: {result.error}")

        self.bottom_status_label.setText(f"Converted {success_count}/{len(self._paths)} file(s)")
        self.convert_button.setEnabled(True)
```

Create `src/mediaconvert/__main__.py`:

```python
"""mediaconvert entry point."""

import sys

from PySide6.QtWidgets import QApplication

from mediaconvert.ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Manual smoke test**

Run: `cd ~/Projects/mediaconvert && PYTHONPATH=src python3 -m mediaconvert`

Verify:
- Window opens on the empty state: dashed drop-zone box with a down arrow, bottom bar shows the hint text on the left/middle and no enabled Convert button.
- Drag a few `.png` files in from a file manager -> view switches to the list state: toolbar shows "N file(s) added" on the left and "Convert to:" + an image-format dropdown on the right; each row shows "filename — Ready"; Convert button enables.
- Pick `webp`, click Convert -> each row updates to "Converting…" then "Done"; output `.webp` files appear next to the sources with preserved mtime; bottom bar shows "Converted N/N file(s)".
- Click `+` in the bottom bar with the list state showing -> file dialog opens, selecting more same-category files adds to the batch.
- Drag one image + one video together (fresh drop) -> list/toolbar are replaced by the centered rejection message ("Can't mix images, video, and audio in one batch"); Convert button stays disabled.
- Drag a `.mp4` -> dropdown includes video formats plus `gif`, `webp`, and audio formats; converting to `mp3` produces an audio-only file, row shows "Done".
- Close the window; no errors on stdout/stderr.

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/mediaconvert
git add src/mediaconvert/ui.py src/mediaconvert/__main__.py
git commit -m "Add ImageOptim-style PySide6 drag-and-drop UI"
```

---

## Task 7: Packaging (launcher script, desktop entry, PKGBUILD)

**Files:**
- Create: `mediaconvert` (repo root, executable launcher script)
- Create: `src/mediaconvert.desktop`
- Create: `PKGBUILD`
- Create: `.gitignore`

**Interfaces:**
- Consumes: `main()` from `src/mediaconvert/__main__.py` (Task 6).
- Produces: an installable Arch package `mediaconvert`.

- [ ] **Step 1: Write the launcher script**

Create `mediaconvert` (repo root):

```python
#!/usr/bin/env python3
"""Launcher for the installed mediaconvert package."""

import sys

from mediaconvert.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
```

Run: `chmod +x mediaconvert`

- [ ] **Step 2: Write the desktop entry**

Create `src/mediaconvert.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=mediaconvert
Comment=Drag-and-drop image/video/audio format conversion
Exec=/usr/bin/mediaconvert %f
Icon=image-x-generic
Terminal=false
Categories=AudioVideo;Graphics;
```

- [ ] **Step 3: Write the PKGBUILD**

Create `PKGBUILD`:

```bash
# Maintainer: James <claude@jamessparkes.com>
pkgname=mediaconvert
pkgver=1.0.0
pkgrel=1
pkgdesc="Drag-and-drop image/video/audio format conversion"
arch=('any')
license=('MIT')
depends=('pyside6' 'python' 'ffmpeg' 'imagemagick' 'libwebp')
source=('mediaconvert' 'mediaconvert.desktop' 'src/mediaconvert/__init__.py'
        'src/mediaconvert/__main__.py' 'src/mediaconvert/categorize.py'
        'src/mediaconvert/converter.py' 'src/mediaconvert/image_convert.py'
        'src/mediaconvert/media_convert.py' 'src/mediaconvert/naming.py'
        'src/mediaconvert/ui.py')
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
    site_packages="usr/lib/python3.$(python3 -c 'import sys; print(sys.version_info.minor)')/site-packages"
    install -Dm755 "$srcdir/mediaconvert" "$pkgdir/usr/bin/mediaconvert"
    install -Dm644 "$srcdir/mediaconvert.desktop" "$pkgdir/usr/share/applications/mediaconvert.desktop"
    install -Dm644 "$srcdir/src/mediaconvert/__init__.py" "$pkgdir/$site_packages/mediaconvert/__init__.py"
    install -Dm644 "$srcdir/src/mediaconvert/__main__.py" "$pkgdir/$site_packages/mediaconvert/__main__.py"
    install -Dm644 "$srcdir/src/mediaconvert/categorize.py" "$pkgdir/$site_packages/mediaconvert/categorize.py"
    install -Dm644 "$srcdir/src/mediaconvert/converter.py" "$pkgdir/$site_packages/mediaconvert/converter.py"
    install -Dm644 "$srcdir/src/mediaconvert/image_convert.py" "$pkgdir/$site_packages/mediaconvert/image_convert.py"
    install -Dm644 "$srcdir/src/mediaconvert/media_convert.py" "$pkgdir/$site_packages/mediaconvert/media_convert.py"
    install -Dm644 "$srcdir/src/mediaconvert/naming.py" "$pkgdir/$site_packages/mediaconvert/naming.py"
    install -Dm644 "$srcdir/src/mediaconvert/ui.py" "$pkgdir/$site_packages/mediaconvert/ui.py"
}
```

Note: `source=()` entries here are local relative paths (built with `source=('file::...')` omitted since these are plain filenames resolved relative to the PKGBUILD directory, matching a local, non-VCS Arch package layout).

- [ ] **Step 4: Write .gitignore**

Create `.gitignore`:

```
__pycache__/
*.pyc
pkg/
src/*.pkg.tar.zst
*.pkg.tar.zst
.pytest_cache/
```

- [ ] **Step 5: Build and install locally, verify**

Run: `cd ~/Projects/mediaconvert && makepkg -si --noconfirm`
Expected: package builds and installs without error.

Run: `mediaconvert` (from a normal terminal, not `PYTHONPATH=src`)
Expected: window opens identically to the Task 6 manual smoke test.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/mediaconvert
git add mediaconvert src/mediaconvert.desktop PKGBUILD .gitignore
git commit -m "Add packaging: launcher, desktop entry, PKGBUILD"
```

---

## Task 8: Remove the retired convert-image.sh service-menu artifacts

**Files:**
- Delete: `~/.local/bin/convert-image.sh`
- Delete: `~/Desktop/convert-image-logic.md` (its content is now superseded by this plan/spec; keep only if the user wants a paper trail)

This task is cleanup of the old approach now that mediaconvert replaces it. The KDE service-menu file (`~/.local/share/kio/servicemenus/convert-image.desktop`) was already removed in an earlier session.

- [ ] **Step 1: Confirm mediaconvert covers everything convert-image.sh did**

Check: image formats png/jpg/webp/bmp/tiff/gif/avif are all in `IMAGE_FORMATS` (Task 1) - yes. `.ico` largest-frame handling - yes (Task 3). WebP via libwebp - yes (Task 3).

- [ ] **Step 2: Remove the old script**

```bash
rm -f ~/.local/bin/convert-image.sh
```

- [ ] **Step 3: Ask the user whether to remove ~/Desktop/convert-image-logic.md**

This file was written as a reference during the design conversation; it's a snapshot, not a maintained doc. Leave removal of this specific file to a manual step outside the plan (don't auto-delete user Desktop files without a direct request in the session executing this task).

---

## Self-Review Notes

- **Spec coverage**: Category enforcement (Task 1/6), one-format-per-batch UI (Task 6), video's extra gif/webp/audio targets (Task 1), output naming/collision/mtime (Task 2/5), WebP-via-libwebp (Task 3), `.ico` largest-frame (Task 3), video/audio via ffmpeg including extraction (Task 4), packaging matching clipcut conventions (Task 7), retiring convert-image.sh (Task 8) - all covered.
- **No placeholders**: all steps contain runnable code and exact commands.
- **Type/name consistency checked**: `convert_image(src, out_path, fmt)` and `convert_media(src, out_path, fmt)` signatures match their use in `converter.convert_file`; `ConversionResult` fields (`src`, `out_path`, `success`, `error`) match UI usage in Task 6; `categorize()`/`target_formats()`/`MixedCategoryError` names match their use in Task 6's `ui.py`.
