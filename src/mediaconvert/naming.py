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
