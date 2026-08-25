# mediaconvert

A drag-and-drop desktop app for batch-converting image, video, and audio
files. Drop in a mixed pile of files (or a whole folder) and it sorts
them into their own group, lets you pick a target format per group, and
converts everything with one click.

## Features

- **Drag-and-drop or file/folder picking** — drop files or folders
  anywhere on the window, or use "Add Files…" / "Add Folder…". Dropping
  a folder with subfolders asks whether to add just the top-level files
  or include subfolders too.
- **Automatic grouping** — a mixed drop of images, videos, and audio
  splits into up to three sections (video, image, audio), each with its
  own file list and target-format dropdown. Unsupported files are
  silently skipped and reported in the status bar instead of blocking
  the whole batch.
- **Per-file-type icons** in the list, with a generic fallback for
  formats without a specific icon.
- **Convert All, or just what you need** — convert everything at once,
  right-click a file (or a multi-selection) to convert just that, or use
  a section's own Convert/Clear buttons when more than one section is
  present. Convert All skips files already converted; changing a
  section's target format resets its files back to "Ready" since that's
  effectively a new job.
- **Conversion runs in the background** — the file lists stay scrollable
  and interactive while converting, with a live "Converting X/Y
  {type} files, N remaining" status.
- **Keyboard shortcuts** — Enter opens the selected file, Delete removes
  selected file(s) from the list.
- **Settings** for where converted files are written (next to the
  source, into a "Converted" subfolder, or a custom folder).

Supported formats: most common image (PNG, JPEG, WebP, GIF, BMP, TIFF,
AVIF, HEIC, ICO, …), video (MP4, MKV, WebM, MOV, AVI, WMV, …), and audio
(MP3, WAV, FLAC, AAC, M4A, Opus, …) formats — see
`src/mediaconvert/categorize.py` for the full list.

## Requirements

- Python 3
- [PySide6](https://pypi.org/project/PySide6/)
- `ffmpeg` (video/audio conversion)
- ImageMagick (image conversion)
- `libwebp` (`cwebp`/`gif2webp`, for WebP output)

## Running it

### From this source checkout (development)

```bash
PYTHONPATH=src python -m mediaconvert
```

Or with the project's own virtualenv if you have one set up:

```bash
PYTHONPATH=src .venv/bin/python -m mediaconvert
```

You can also pass file paths on the command line to open with them
pre-loaded:

```bash
PYTHONPATH=src python -m mediaconvert ~/Pictures/photo.jpg ~/Videos/clip.mp4
```

### Installed as a package (Arch Linux)

Build and install with `makepkg`/`pacman`:

```bash
makepkg -f
sudo pacman -U mediaconvert-*.pkg.tar.zst
```

This installs a `mediaconvert` launcher, a desktop entry ("Convert"),
and an app icon, so it shows up in your application launcher and can be
set as the default handler for supported file types.

## Running the tests

```bash
pytest
```
