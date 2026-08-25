# Grouped file-list UI

## Problem

mediaconvert currently treats every batch of dropped/added files as a single
list that must all belong to one media category (image, video, or audio). If
any file's extension doesn't match the rest, the whole drop is rejected with
an error screen ("Can't mix images, video, and audio in one batch") — even
when most of the files are perfectly convertible. This makes drag-and-drop
error-prone: a user dragging in a folder with a few stray files (e.g. a
`.txt` note next to their photos, or a video mixed in with images) gets
nothing.

## Goals

- Accept mixed drops. Split files into up to three independently-managed
  groups (video, image, audio), each with its own target format and table.
- Silently ignore genuinely unsupported files (unknown extensions), and
  surface the count rather than blocking the whole operation.
- Rework the toolbar layout: remove the top bar, move "Add files" to the
  bottom bar (left), keep "Settings" and "Convert" together on the right.
- Add a per-group "Options" button to the design now (disabled, unwired) so
  the layout doesn't need to change again when per-group options land later.

## Non-goals

- Implementing actual per-group conversion options (the Options button is a
  disabled placeholder only).
- Deduplicating files added twice across separate add operations (existing
  behavior already doesn't dedupe; not changing that).
- Any change to the actual conversion backends (`image_convert.py`,
  `media_convert.py`) or output-path resolution.

## Design

### `categorize.py`

Replace the all-or-nothing API with per-file classification:

- `category_of(path: Path) -> str | None` — returns `"image"`, `"video"`,
  `"audio"`, or `None` for an unrecognized extension. Replaces the
  raising `_category_of`.
- `split_by_category(paths: list[Path]) -> tuple[dict[str, list[Path]], list[Path]]`
  — buckets paths by category (only categories with at least one file appear
  as keys, each list preserving input order) and returns `(groups, ignored)`
  where `ignored` holds paths with unrecognized extensions.
- Remove `MixedCategoryError` and `categorize()` — no longer meaningful once
  mixed batches are the normal case.
- `target_formats()` is unchanged.
- `tests/test_categorize.py` is rewritten against the new API (mixed batches
  now split cleanly instead of raising; unknown extensions land in
  `ignored` instead of raising).

### `ui.py` data model

- `CATEGORY_ORDER = ["video", "image", "audio"]` — fixed display order.
- `self._groups: dict[str, list[Path]]` replaces `self._paths` /
  `self._category`. Only categories with files are present as keys.
- Per-group UI state lives in `self._group_widgets: dict[str, GroupSection]`
  (a small dataclass or plain dict holding the section's container widget,
  header count label, format combo, options button, and table). All three
  sections are constructed once at startup, added to the list page's layout
  in `CATEGORY_ORDER`, and shown/hidden as their group gains/loses files —
  this keeps section order fixed without rebuilding widgets on every add.
- Each group's `QTableWidget` keeps the existing columns (File Name, Size,
  Type, Status), same per-row icon/context-menu/double-click behavior as
  today, scoped to that group's own paths list.
- Group tables share the list page vertically with equal stretch factors, so
  with N groups visible each gets roughly `1/N` of the available height;
  each table still scrolls internally if its own rows overflow.

### Layout changes

- Top bar is removed.
- Each group section has its own header row: `"{n} {category} files"` label,
  a spacer, `"Convert to:"` + format `QComboBox`, and an `"Options"` button
  (`setEnabled(False)` — placeholder for future per-group options).
- Bottom bar becomes: `Add files` (left) — status label (center, stretch) —
  `Settings`, `Convert` (right, in that order).
- The status label is reused for two purposes at different times: after an
  add/drop, it shows `"{n} file(s) added"` or, when some were ignored,
  `"{n} file(s) added, {m} other file(s) ignored"`; after a conversion run it
  shows `"Converted {x}/{y} file(s)"` (as today).

### Add / drop flow

Both `_open_files_dialog` and `dropEvent` funnel through one
`_add_paths(paths: list[Path])`:

1. `groups, ignored = split_by_category(paths)`.
2. If there are no existing groups (`self._groups` empty) and `groups` is
   also empty (i.e. this is the first-ever add and nothing was recognized),
   show the existing big empty-state error screen, same as today's
   `MixedCategoryError` path, with a message like "No supported files were
   found." Nothing else changes.
3. Otherwise, for each category in `groups`: extend `self._groups[cat]`
   (creating it if new), show/populate that group's section (creating the
   format combo items via `target_formats(cat)` only when the section is
   newly shown, so an existing selection isn't reset), and append new rows
   to its table.
4. Update the bottom status label with the added/ignored counts for this
   operation.
5. Ensure the list state is shown (switch away from the empty-state page)
   whenever at least one group is non-empty.

### Row removal

- Context-menu "Remove" stays scoped to the table it was invoked on, and
  continues to rebuild that group's `self._groups[cat]` list from the
  table's remaining rows.
- After removal, if a group's list becomes empty: hide that section and
  delete the `self._groups` entry.
- If all groups become empty, fall back to the empty-state page (same
  hint text as the initial state).

### Convert flow

- `_convert_batch` iterates `CATEGORY_ORDER`, and for each present group runs
  the existing per-row conversion loop (using that group's own selected
  format from its combo and its own table's Status column).
- Aggregates success/total across all groups and shows
  `"Converted {x}/{y} file(s)"` in the bottom status label once all groups
  are done.
- `_converting` guard, disabling Add/Convert during the run, is unchanged in
  spirit but now applies globally across all group tables at once.

## Testing

- `tests/test_categorize.py`: rewritten for `category_of` and
  `split_by_category` (all-images, all-video, all-audio, mixed batch splits
  correctly, unknown extensions go to `ignored`, empty input).
- Manual verification in the running app (drag-drop mixed batches, add more
  files to an existing group, remove down to empty, convert multiple groups
  in one click) since `ui.py` has no existing automated UI test coverage.
