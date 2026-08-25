"""Output path resolution and mtime preservation for mediaconvert."""

import os
from pathlib import Path


def resolve_output_path(src: Path, fmt: str, out_dir: Path | None = None) -> Path:
    """Same basename as src with a new extension, in out_dir (or src's own
    directory if out_dir is None); -1, -2, ... on collision.

    Always returns a path distinct from src, even when fmt matches src's
    extension (self-conversion still produces a numbered sibling, never
    overwrites the source). Creates out_dir if it doesn't exist yet.
    """
    directory = out_dir if out_dir is not None else src.parent
    if out_dir is not None:
        directory.mkdir(parents=True, exist_ok=True)
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
