# mediaconvert — design spec

## Purpose

A small drag-and-drop desktop app for converting images, video, and audio
between formats, replacing the KDE service-menu approach in
`~/.local/bin/convert-image.sh` (which is being retired — its right-click
submenu is broken on the currently pinned Dolphin 26.04.3, and per-format
flat top-level menu entries were unwieldy). Modeled after the existing
`clipcut` app (same author, same stack, same packaging conventions) but for
format conversion instead of trim/crop.

## Stack

- **Language/UI**: Python + PySide6, matching `clipcut`
  (`~/Projects/clipcut`, depends on `pyside6` + `ffmpeg` + `gifsicle`,
  packaged as a single `clipcut` script + `clipcut.desktop` via PKGBUILD).
- **Packaging**: same pattern as clipcut — single executable script
  installed to `/usr/bin/mediaconvert`, `.desktop` file to
  `/usr/share/applications/`, built as an Arch package via PKGBUILD,
  versioned by bumping only the PKGBUILD patch number (per user's clipcut
  convention — never minor/major regardless of change size).
- **Backends** (all already installed, invoked as subprocesses — no new
  system deps required):
  - `magick` (ImageMagick, built with libheif — handles HEIC/AVIF/JPEG/PNG/
    BMP/TIFF/GIF/ICO natively) for general image conversion
  - `cwebp` / `gif2webp` (libwebp) for WebP *output* specifically — better
    size/quality than ImageMagick's own WebP encoder; `gif2webp` for
    animated GIF sources, `cwebp` for everything else
  - `ffmpeg` for all video and audio conversion, and for video→GIF/WebP
    (animated) and video→audio extraction

## UI flow

Visual model: ImageOptim (macOS) — a plain drop-zone window that switches
to a flat file-list view once files land, with a slim bottom bar. Adapted
here with an added toolbar above the list for the format picker, since
(unlike ImageOptim, which always does the same operation) this app needs
you to choose a target format.

1. **Initial screen**: single window, no toolbar. Centered dashed
   drop-zone box with a down-arrow icon (like ImageOptim's empty state).
   Bottom bar: `+` button on the left (opens a file picker as the non-drag
   fallback), a hint label ("Drag and drop image, video, or audio files
   onto the area above"), nothing on the right (no action button until
   files exist).
2. **After files are dropped**, the drop-zone area becomes a flat file
   list, one row per file: left icon (image/video/audio type icon, later
   replaced by a checkmark once that file converts), filename, and a
   right-aligned status text that updates in place (`Ready` →
   `Converting…` → `Done` / `Failed: <reason>`). No size/savings column —
   this app converts, it doesn't report size reduction like ImageOptim
   does.
3. **Toolbar above the list** (appears only once files are present): left
   side shows an info label (e.g. "5 files added"); right side shows
   "Convert to:" plus a format dropdown populated per the batch's
   category (see format-selection rules below).
4. **Category enforcement**: all dropped files in one batch must be the
   same category — image, video, or audio. Mixing categories (e.g. an
   image + a video in the same drop) is rejected with an inline message
   ("Can't mix images, video, and audio in one batch") shown in place of
   the file list, rather than attempting conversion. Dropping a new mixed
   batch replaces whatever was there; the app does not attempt to
   auto-split it.
5. **Format-selection rules** (populates the toolbar dropdown):
   - **Images dropped** → image output formats only
   - **Audio dropped** → audio output formats only
   - **Video dropped** → video output formats **+ gif + webp** (animated
     output via ffmpeg, not cwebp/gif2webp since the source is video, not
     a static image or animated GIF file) **+ all audio formats**
     (extraction — drops the video stream, keeps/transcodes audio only)
6. **Bottom bar** (list view) keeps the same shape as ImageOptim's: `+`
   button on the left (add more files to the current batch — subject to
   the same category enforcement), a summary status label in the middle
   ("Converted 4/5 files"), and a **Convert** button on the right, where
   ImageOptim has "Again".
7. Failures are shown inline per file (in that row's status text) — not a
   single blocking modal for the whole batch. Successful files still
   complete even if others in the batch fail.

## Output behavior (same as convert-image.sh)

- Output written next to the source file, same basename, new extension.
- Collision avoidance: if `name.ext` already exists, try `name-1.ext`,
  `name-2.ext`, etc.
- Output mtime set to match the source file's mtime (`touch -r`
  equivalent).

## Format lists

**Images**: avif, bmp, gif, heic, ico, jfif, jpeg/jpg, png, tiff, webp

- `.ico` **source**: multi-frame — pick the largest embedded frame (by
  pixel area, via `magick identify -format "%wx%h\n"`) rather than
  converting every frame, same logic as convert-image.sh.
- `.ico` as an **output** format is included (convert-image.sh only
  supported it as input).
- WebP output always routes through `cwebp`/`gif2webp`, not
  `magick ... output.webp` directly.

**Video**: avi, m2ts, m4v, mkv, mov, mp4, mpeg/mpg, mts, ogg, ogv, swf, ts,
vob, webm, wmv

**Audio**: aac, aifc, aiff, flac, m4a, m4b, mp3, opus, voc, wav

All three lists confirmed against installed `magick -list format` and
`ffmpeg -formats`/`-codecs` output — no missing codecs, no extra system
packages needed beyond what's already installed (ImageMagick w/ libheif,
ffmpeg, libwebp).

## Explicitly out of scope

- Right-click / KDE service-menu integration (launcher-only app, per
  user's decision — avoids the Dolphin submenu bug entirely rather than
  working around it).
- Per-file format pickers (one format per batch, matching
  convert-image.sh's existing one-format-per-invocation behavior).
- Trim/crop/quality/bitrate controls — that's clipcut's job, not this
  app's.
- Auto-splitting a mixed-category drop into sub-batches — rejected
  outright instead.

## Testing

- Manual: drag in sample files per category, confirm correct format list
  appears, confirm mixed-category rejection message, confirm output
  naming/collision/mtime behavior, confirm WebP output actually invokes
  `cwebp`/`gif2webp` (not ImageMagick's encoder) and `.ico` source picks
  the largest frame.
- No automated test suite planned initially (matches clipcut's structure,
  which relies on a manual regression script rather than a formal test
  suite).
