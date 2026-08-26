"""mediaconvert main window: ImageOptim-style drag-and-drop batch format conversion."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QDateTime, QEvent, QThread, QUrl, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QIcon,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mediaconvert.categorize import CATEGORY_ORDER, split_by_category, target_formats
from mediaconvert.control import ConversionControl
from mediaconvert.converter import convert_file
from mediaconvert.icons import svg_pixmap
from mediaconvert.settings_dialog import SettingsDialog, resolve_output_dir

_ARROW_DOWN_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>"""
_CIRCLE_ALERT_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>"""
_DEFAULT_HINT = "Click to add or drag and drop image, video, or audio files"

_ICON_NAME_BY_EXTENSION: dict[str, str] = {
    # image
    "avif": "image-avif",
    "bmp": "image-bmp",
    "gif": "image-gif",
    "heic": "image-heic",
    "ico": "image-x-icon",
    "jfif": "image-jpeg",
    "jpeg": "image-jpeg",
    "jpg": "image-jpeg",
    "png": "image-png",
    "tif": "image-tiff",
    "tiff": "image-tiff",
    "webp": "image-webp",
    # video
    "avi": "video-x-msvideo",
    "m2ts": "video-mp2t",
    "m4v": "video-mp4",
    "mkv": "video-x-matroska",
    "mov": "video-quicktime",
    "mp4": "video-mp4",
    "mpeg": "video-mpeg",
    "mpg": "video-mpeg",
    "mts": "video-mp2t",
    "ogg": "video-ogg",
    "ogv": "video-ogg",
    "swf": "application-x-shockwave-flash",
    "ts": "video-mp2t",
    "vob": "video-x-generic",
    "webm": "video-webm",
    "wmv": "video-x-ms-wmv",
    # audio
    "aac": "audio-aac",
    "aifc": "audio-x-aiff",
    "aiff": "audio-x-aiff",
    "flac": "audio-flac",
    "m4a": "audio-x-m4a",
    "m4b": "audio-x-m4a",
    "mp3": "audio-mp3",
    "opus": "audio-opus",
    "voc": "audio-x-generic",
    "wav": "audio-x-wav",
}


def _pluralize(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


@dataclass
class GroupSection:
    container: QWidget
    header_label: QLabel
    combo: QComboBox
    options_button: QPushButton
    clear_button: QPushButton
    convert_button: QPushButton
    table: QTableWidget


@dataclass
class _ConversionJob:
    category: str
    row: int
    path: Path
    fmt: str


class _ConversionWorker(QThread):
    """Runs conversions off the GUI thread; only emits signals, never
    touches widgets directly (Qt widgets are not thread-safe)."""

    job_starting = Signal(str, int, int, int, int)  # category, row, index_in_category, total_in_category, remaining_overall
    job_finished = Signal(str, int, bool, str)  # category, row, success, error
    job_reverted = Signal(str, int)  # category, row - stopped mid-flight, back to Ready
    finished_all = Signal(int, int, bool)  # success_count, attempted, stopped

    def __init__(self, jobs: list[_ConversionJob], category_totals: dict[str, int], control: ConversionControl):
        super().__init__()
        self._jobs = jobs
        self._category_totals = category_totals
        self._control = control

    def run(self) -> None:
        total = len(self._jobs)
        success_count = 0
        attempted = 0
        category_progress: dict[str, int] = {}
        try:
            for index, job in enumerate(self._jobs):
                if self._control.stop_requested.is_set():
                    break
                self._control.wait_while_paused()
                if self._control.stop_requested.is_set():
                    break

                category_progress[job.category] = category_progress.get(job.category, 0) + 1
                remaining = total - index
                self.job_starting.emit(
                    job.category, job.row, category_progress[job.category],
                    self._category_totals[job.category], remaining,
                )
                try:
                    out_dir = resolve_output_dir(job.path.parent)
                    result = convert_file(job.path, job.fmt, job.category, out_dir, control=self._control)
                    success, error = result.success, result.error or ""
                except Exception as e:
                    # convert_file already never raises, but this safety net
                    # guards against any other unexpected error in this
                    # per-job path, so one bad file can never again silently
                    # kill the whole background thread and hang the UI.
                    success, error = False, str(e)

                if not success and self._control.stop_requested.is_set():
                    # Killed by a Stop request mid-conversion, not a real
                    # failure - back to Ready rather than showing "Failed".
                    self.job_reverted.emit(job.category, job.row)
                else:
                    attempted += 1
                    if success:
                        success_count += 1
                    self.job_finished.emit(job.category, job.row, success, error)

                if self._control.stop_requested.is_set():
                    break
        finally:
            # Always emit, even if something above raised unexpectedly -
            # this is what lets the UI recover instead of staying locked
            # in "converting" state forever.
            stopped = self._control.stop_requested.is_set()
            self.finished_all.emit(success_count, attempted if stopped else total, stopped)


class MainWindow(QMainWindow):
    def __init__(self, initial_paths: list[Path] | None = None):
        super().__init__()
        self.setWindowTitle("Convert")
        self.resize(1080, 820)
        self.setAcceptDrops(True)

        self._groups: dict[str, list[Path]] = {}
        self._group_sections: dict[str, GroupSection] = {}
        self._table_category: dict[QTableWidget, str] = {}
        self._converting = False
        self._conversion_worker: _ConversionWorker | None = None
        self._conversion_control: ConversionControl | None = None
        self._error_log: list[str] = []

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.stack.addWidget(self._build_empty_page())
        self.stack.addWidget(self._build_list_page())

        self.bottom_bar = self._build_bottom_bar()
        root.addWidget(self.bottom_bar)

        self.setCentralWidget(central)
        self._show_empty_state(_DEFAULT_HINT)

        if initial_paths:
            self._add_paths(initial_paths)

    # -- page builders ----------------------------------------------------

    def _build_empty_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        drop_box = QFrame()
        drop_box.setObjectName("dropBox")
        drop_box.setStyleSheet(
            "#dropBox { border: 2px dashed palette(placeholder-text); border-radius: 8px; }"
        )
        drop_box.setCursor(Qt.PointingHandCursor)
        drop_box.installEventFilter(self)
        self._drop_box = drop_box
        box_layout = QVBoxLayout(drop_box)
        box_layout.setSpacing(8)
        box_layout.addStretch(1)
        self.empty_icon_label = QLabel()
        self.empty_icon_label.setPixmap(svg_pixmap(_ARROW_DOWN_ICON_SVG, "#8a8a8a", 56))
        self.empty_icon_label.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(self.empty_icon_label)
        self.empty_hint_label = QLabel("")
        self.empty_hint_label.setAlignment(Qt.AlignCenter)
        self.empty_hint_label.setWordWrap(True)
        self.empty_hint_label.setStyleSheet("color: palette(placeholder-text);")
        box_layout.addWidget(self.empty_hint_label)
        box_layout.addStretch(1)
        layout.addWidget(drop_box, stretch=1)
        return page

    def eventFilter(self, obj, event) -> bool:
        if obj is self._drop_box and event.type() == QEvent.MouseButtonRelease:
            self._open_files_dialog()
            return True
        if event.type() == QEvent.KeyPress and obj in self._table_category:
            if self._handle_table_key(self._table_category[obj], obj, event):
                return True
        return super().eventFilter(obj, event)

    def _handle_table_key(self, category: str, table: QTableWidget, event) -> bool:
        selected_rows = {index.row() for index in table.selectionModel().selectedRows()}
        if not selected_rows:
            return False
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if len(selected_rows) != 1:
                return False
            (row,) = selected_rows
            path = Path(table.item(row, 0).data(Qt.UserRole))
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return True
        if key == Qt.Key_Delete:
            if self._converting:
                return False
            self._remove_rows(category, selected_rows)
            return True
        return False

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for index, category in enumerate(CATEGORY_ORDER):
            section = self._build_group_section(category, is_first=index == 0)
            self._group_sections[category] = section
            section.container.hide()
            layout.addWidget(section.container, stretch=1)

        return page

    def _build_group_section(self, category: str, is_first: bool) -> GroupSection:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("groupHeader")
        border_rules = "border-bottom: 1px solid rgba(127, 127, 127, 90);"
        if not is_first:
            border_rules += " border-top: 1px solid rgba(127, 127, 127, 90);"
        header.setStyleSheet(f"#groupHeader {{ {border_rules} }}")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 8, 8, 8)

        header_icon_label = QLabel()
        header_layout.addWidget(header_icon_label)
        header_label = QLabel("")
        header_layout.addWidget(header_label)
        header_layout.addStretch(1)
        header_layout.addWidget(QLabel("Convert to:"))
        combo = QComboBox()
        combo.currentTextChanged.connect(lambda _text, cat=category: self._on_format_changed(cat))
        header_layout.addWidget(combo)
        options_button = QPushButton("Options")
        options_button.setEnabled(False)
        header_layout.addWidget(options_button)
        clear_button = QPushButton("Clear")
        clear_button.setVisible(False)
        clear_button.clicked.connect(lambda _checked=False, cat=category: self._clear_group(cat))
        header_layout.addWidget(clear_button)
        convert_button = QPushButton("Convert")
        convert_button.setVisible(False)
        convert_button.clicked.connect(lambda _checked=False, cat=category: self._convert_group(cat))
        header_layout.addWidget(convert_button)

        icon_size = options_button.sizeHint().height()
        header_icon_label.setPixmap(self._icon_for_category(category).pixmap(icon_size, icon_size))
        outer.addWidget(header)

        table = QTableWidget(0, 4)
        table.installEventFilter(self)
        self._table_category[table] = category
        table.setHorizontalHeaderLabels(["File Name", "Size", "Type", "Status"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, cat=category: self._show_context_menu(cat, pos)
        )
        table.cellDoubleClicked.connect(
            lambda row, column, cat=category: self._open_row_file(cat, row, column)
        )
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        header_view = table.horizontalHeader()
        header_view.setHighlightSections(False)
        header_view.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.Interactive)
        header_view.setSectionResizeMode(2, QHeaderView.Interactive)
        header_view.setSectionResizeMode(3, QHeaderView.Interactive)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(2, 120)
        table.setColumnWidth(3, 140)
        outer.addWidget(table, stretch=1)

        return GroupSection(
            container=container,
            header_label=header_label,
            combo=combo,
            options_button=options_button,
            clear_button=clear_button,
            convert_button=convert_button,
            table=table,
        )

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("bottomBar")
        bar.setStyleSheet("#bottomBar { border-top: 1px solid rgba(127, 127, 127, 90); }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 8, 8, 8)

        self.add_button = QPushButton("Add files")
        add_menu = QMenu(self)
        add_menu.addAction("Add Files…", self._open_files_dialog)
        add_menu.addAction("Add Folder…", self._open_folder_dialog)
        self.add_button.setMenu(add_menu)
        layout.addWidget(self.add_button)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_button)

        self.bottom_status_label = QLabel("")
        self.bottom_status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.bottom_status_label, stretch=1)

        self.details_button = QPushButton("Details")
        self.details_button.setVisible(False)
        self.details_button.clicked.connect(self._show_error_log)
        layout.addWidget(self.details_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setVisible(False)
        self.pause_button.clicked.connect(self._toggle_pause)
        layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self._stop_conversion)
        layout.addWidget(self.stop_button)

        self.clear_button = QPushButton("Clear all")
        self.clear_button.clicked.connect(self._clear_all)
        layout.addWidget(self.clear_button)

        self.convert_button = QPushButton("Convert All")
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(self._convert_batch)
        layout.addWidget(self.convert_button)

        return bar

    # -- state transitions --------------------------------------------------

    def _show_empty_state(self, hint: str, error: bool = False) -> None:
        self.stack.setCurrentIndex(0)
        icon_svg = _CIRCLE_ALERT_ICON_SVG if error else _ARROW_DOWN_ICON_SVG
        self.empty_icon_label.setPixmap(svg_pixmap(icon_svg, "#8a8a8a", 56))
        self.empty_hint_label.setText(hint)
        self.bottom_bar.hide()
        self.convert_button.setEnabled(False)

    def _show_list_state(self) -> None:
        self.stack.setCurrentIndex(1)
        self.bottom_bar.show()
        self.convert_button.setEnabled(True)

    # -- drag and drop / file dialog ----------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        event.acceptProposedAction()
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self._add_paths(paths)

    def _open_row_file(self, category: str, row: int, column: int) -> None:
        table = self._group_sections[category].table
        path = Path(table.item(row, 0).data(Qt.UserRole))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _show_context_menu(self, category: str, pos) -> None:
        table = self._group_sections[category].table
        row = table.rowAt(pos.y())
        if row < 0:
            return

        selection_model = table.selectionModel()
        selected_rows = {index.row() for index in selection_model.selectedRows()}
        if row not in selected_rows:
            table.selectRow(row)
            selected_rows = {row}

        menu = self._build_context_menu(category, table, selected_rows)
        menu.exec(table.viewport().mapToGlobal(pos))

    def _build_context_menu(self, category: str, table: QTableWidget, selected_rows: set[int]) -> QMenu:
        menu = QMenu(self)
        convert_label = "Convert" if len(selected_rows) == 1 else f"Convert {len(selected_rows)} Files"
        convert_action = menu.addAction(convert_label)
        convert_action.setEnabled(not self._converting)
        convert_action.triggered.connect(lambda: self._convert_selected(category, selected_rows))

        menu.addSeparator()
        remove_label = "Remove" if len(selected_rows) == 1 else f"Remove {len(selected_rows)} Files"
        remove_action = menu.addAction(remove_label)
        remove_action.setEnabled(not self._converting)
        remove_action.triggered.connect(lambda: self._remove_rows(category, selected_rows))

        if len(selected_rows) == 1:
            (only_row,) = selected_rows
            path = Path(table.item(only_row, 0).data(Qt.UserRole))
            menu.addSeparator()
            open_action = menu.addAction("Open File")
            open_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
            open_folder_action = menu.addAction("Open Containing Folder")
            open_folder_action.triggered.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
            )

        return menu

    def _remove_rows(self, category: str, rows: set[int]) -> None:
        section = self._group_sections[category]
        table = section.table
        for row in sorted(rows, reverse=True):
            table.removeRow(row)
        remaining = [
            Path(table.item(r, 0).data(Qt.UserRole)) for r in range(table.rowCount())
        ]
        if remaining:
            self._groups[category] = remaining
            self._update_group_header(category)
        else:
            del self._groups[category]
            section.container.hide()

        if not self._groups:
            self._show_empty_state(_DEFAULT_HINT)
        self._update_section_button_visibility()

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()

    def _open_files_dialog(self) -> None:
        if self._converting:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Open files")
        if files:
            self._add_paths([Path(f) for f in files])

    def _open_folder_dialog(self) -> None:
        if self._converting:
            return
        directory = QFileDialog.getExistingDirectory(self, "Select folder")
        if directory:
            self._add_paths([Path(directory)])

    def _clear_all(self) -> None:
        if self._converting:
            return
        for section in self._group_sections.values():
            section.table.setRowCount(0)
            section.container.hide()
        self._groups.clear()
        self._show_empty_state(_DEFAULT_HINT)

    def _clear_group(self, category: str) -> None:
        if self._converting or category not in self._groups:
            return
        table = self._group_sections[category].table
        self._remove_rows(category, set(range(table.rowCount())))

    def _update_section_button_visibility(self) -> None:
        show_section_buttons = len(self._groups) > 1
        for section in self._group_sections.values():
            section.clear_button.setVisible(show_section_buttons)
            section.convert_button.setVisible(show_section_buttons)

    # -- icons and row formatting ----------------------------------------------

    def _icon_for_category(self, category: str) -> QIcon:
        theme_name = {
            "image": "folder-pictures-symbolic",
            "video": "folder-videos-symbolic",
            "audio": "folder-music-symbolic",
        }.get(category, "folder-documents-symbolic")
        icon = QIcon.fromTheme(theme_name)
        if not icon.isNull():
            return icon
        style = self.style()
        fallback_map = {
            "image": QStyle.SP_FileIcon,
            "video": QStyle.SP_MediaPlay,
            "audio": QStyle.SP_MediaVolume,
        }
        return style.standardIcon(fallback_map.get(category, QStyle.SP_FileIcon))

    def _icon_for_path(self, path: Path, category: str) -> QIcon:
        theme_name = _ICON_NAME_BY_EXTENSION.get(path.suffix.lower().lstrip("."))
        if theme_name:
            icon = QIcon.fromTheme(theme_name)
            if not icon.isNull():
                return icon
        return self._icon_for_category(category)

    @staticmethod
    def _human_size(path: Path) -> str:
        try:
            size = path.stat().st_size
        except OSError:
            return ""
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} GB"

    @staticmethod
    def _type_for_path(path: Path) -> str:
        return path.suffix.lstrip(".").upper()

    # -- batch loading and conversion ---------------------------------------

    def _expand_folders(self, paths: list[Path]) -> list[Path] | None:
        """Replace any directories in paths with the files they contain.
        Returns None if the user cancelled the top-level-vs-recursive
        prompt (shown once, for the whole batch, only when at least one
        folder has subfolders of its own)."""
        folders = [p for p in paths if p.is_dir()]
        files = [p for p in paths if not p.is_dir()]

        def has_subfolders(folder: Path) -> bool:
            try:
                return any(child.is_dir() for child in folder.iterdir())
            except OSError:
                return False

        recursive = False
        if any(has_subfolders(folder) for folder in folders):
            choice = self._ask_recursive_expansion()
            if choice is None:
                return None
            recursive = choice

        expanded = list(files)
        for folder in folders:
            try:
                contents = folder.rglob("*") if recursive else folder.iterdir()
                expanded.extend(sorted(p for p in contents if p.is_file()))
            except OSError:
                continue
        return expanded

    def _ask_recursive_expansion(self) -> bool | None:
        box = QMessageBox(self)
        box.setWindowTitle("Add Folder")
        box.setText(
            "This folder contains subfolders. Add files from the top level "
            "only, or include files from subfolders too?"
        )
        top_level_button = box.addButton("Top Level Only", QMessageBox.AcceptRole)
        recursive_button = box.addButton("Include Subfolders", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked in (top_level_button, recursive_button):
            return clicked is recursive_button
        return None

    def _add_paths(self, paths: list[Path]) -> None:
        if not paths or self._converting:
            return

        if any(p.is_dir() for p in paths):
            expanded = self._expand_folders(paths)
            if expanded is None:
                return
            paths = expanded

        groups, ignored = split_by_category(paths)

        if not self._groups and not groups:
            self._show_empty_state("No supported files were found.", error=True)
            return

        added_count = 0
        for category, new_paths in groups.items():
            added_count += len(new_paths)
            self._add_to_group(category, new_paths)

        self._update_section_button_visibility()
        self._show_list_state()
        self._set_add_status(added_count, len(ignored))

    def _add_to_group(self, category: str, new_paths: list[Path]) -> None:
        section = self._group_sections[category]
        is_new = category not in self._groups
        self._groups.setdefault(category, [])
        self._groups[category].extend(new_paths)

        if is_new:
            section.container.show()
            section.combo.clear()
            section.combo.addItems(target_formats(category))

        section.table.setSortingEnabled(False)
        start_row = section.table.rowCount()
        section.table.setRowCount(start_row + len(new_paths))
        for offset, p in enumerate(new_paths):
            row = start_row + offset
            name_item = QTableWidgetItem(p.name)
            name_item.setIcon(self._icon_for_path(p, category))
            name_item.setData(Qt.UserRole, str(p))
            section.table.setItem(row, 0, name_item)
            section.table.setItem(row, 1, QTableWidgetItem(self._human_size(p)))
            section.table.setItem(row, 2, QTableWidgetItem(self._type_for_path(p)))
            section.table.setItem(row, 3, QTableWidgetItem("Ready"))
        section.table.setSortingEnabled(True)
        self._update_group_header(category)

    def _update_group_header(self, category: str) -> None:
        section = self._group_sections[category]
        count = len(self._groups.get(category, []))
        section.header_label.setText(_pluralize(count, f"{category} file"))

    def _set_add_status(self, added: int, ignored: int) -> None:
        text = f"{_pluralize(added, 'file')} added"
        if ignored:
            text += f", {_pluralize(ignored, 'other file')} ignored"
        self.bottom_status_label.setText(text)

    def _convert_batch(self) -> None:
        if not self._groups or self._converting:
            return

        jobs: list[_ConversionJob] = []
        category_totals: dict[str, int] = {}
        for category in CATEGORY_ORDER:
            if category not in self._groups:
                continue
            section = self._group_sections[category]
            fmt = section.combo.currentText()
            if not fmt:
                continue
            table = section.table
            pending_rows = [
                row for row in range(table.rowCount()) if table.item(row, 3).text() != "Done"
            ]
            if not pending_rows:
                continue
            category_totals[category] = len(pending_rows)
            for row in pending_rows:
                path = Path(table.item(row, 0).data(Qt.UserRole))
                jobs.append(_ConversionJob(category, row, path, fmt))

        if not jobs:
            return

        self._start_conversion(jobs, category_totals)

    def _convert_selected(self, category: str, rows: set[int]) -> None:
        if self._converting:
            return
        section = self._group_sections[category]
        fmt = section.combo.currentText()
        if not fmt:
            return
        jobs = [
            _ConversionJob(category, row, Path(section.table.item(row, 0).data(Qt.UserRole)), fmt)
            for row in sorted(rows)
        ]
        if not jobs:
            return
        self._start_conversion(jobs, {category: len(jobs)})

    def _convert_group(self, category: str) -> None:
        if self._converting or category not in self._groups:
            return
        section = self._group_sections[category]
        fmt = section.combo.currentText()
        if not fmt:
            return
        table = section.table
        pending_rows = [
            row for row in range(table.rowCount()) if table.item(row, 3).text() != "Done"
        ]
        if not pending_rows:
            return
        jobs = [
            _ConversionJob(category, row, Path(table.item(row, 0).data(Qt.UserRole)), fmt)
            for row in pending_rows
        ]
        self._start_conversion(jobs, {category: len(jobs)})

    def _start_conversion(self, jobs: list[_ConversionJob], category_totals: dict[str, int]) -> None:
        self._converting = True
        self._set_all_controls_enabled(False)
        self._set_bottom_bar_mode(processing=True)
        self.pause_button.setText("Pause")
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)

        self._conversion_control = ConversionControl()
        self._conversion_worker = _ConversionWorker(jobs, category_totals, self._conversion_control)
        self._conversion_worker.job_starting.connect(self._on_job_starting)
        self._conversion_worker.job_finished.connect(self._on_job_finished)
        self._conversion_worker.job_reverted.connect(self._on_job_reverted)
        self._conversion_worker.finished_all.connect(self._on_conversion_finished)
        self._conversion_worker.start()

    def _toggle_pause(self) -> None:
        if self._conversion_control is None:
            return
        if self._conversion_control.pause_requested.is_set():
            self._conversion_control.pause_requested.clear()
            self.pause_button.setText("Pause")
        else:
            self._conversion_control.pause_requested.set()
            self.pause_button.setText("Resume")

    def _stop_conversion(self) -> None:
        if self._conversion_control is None:
            return
        self.stop_button.setEnabled(False)
        self._conversion_control.request_stop()

    def _set_bottom_bar_mode(self, processing: bool) -> None:
        self.clear_button.setVisible(not processing)
        self.convert_button.setVisible(not processing)
        self.pause_button.setVisible(processing)
        self.stop_button.setVisible(processing)

    def _set_all_controls_enabled(self, enabled: bool) -> None:
        for section in self._group_sections.values():
            section.table.setSortingEnabled(enabled)
            section.combo.setEnabled(enabled)
            section.clear_button.setEnabled(enabled)
            section.convert_button.setEnabled(enabled)
        self.convert_button.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)

    def _on_format_changed(self, category: str) -> None:
        if self._converting:
            return
        section = self._group_sections.get(category)
        if section is None:
            return
        table = section.table
        for row in range(table.rowCount()):
            status_item = table.item(row, 3)
            if status_item is None:
                continue
            status_item.setText("Ready")
            status_item.setForeground(QBrush())
            status_item.setToolTip("")

    def _on_job_starting(
        self, category: str, row: int, index_in_category: int, total_in_category: int, remaining: int
    ) -> None:
        status_item = self._group_sections[category].table.item(row, 3)
        status_item.setForeground(QBrush())
        status_item.setText("Converting…")

        category_word = "file" if total_in_category == 1 else "files"
        remaining_word = "file" if remaining == 1 else "files"
        self.bottom_status_label.setText(
            f"Converting {index_in_category} / {total_in_category} {category} {category_word}, "
            f"{remaining} {remaining_word} remaining"
        )

    def _on_job_finished(self, category: str, row: int, success: bool, error: str) -> None:
        status_item = self._group_sections[category].table.item(row, 3)
        if success:
            status_item.setText("Done")
            status_item.setForeground(QBrush(QColor("#2ecc71")))
        else:
            error_summary = error.strip().splitlines()
            short_error = error_summary[-1] if error_summary else "unknown error"
            if len(short_error) > 120:
                short_error = short_error[:117] + "..."
            status_item.setText(f"Failed: {short_error}")
            status_item.setToolTip(error)
            status_item.setForeground(QBrush(QColor("#e74c3c")))
            name = self._group_sections[category].table.item(row, 0).text()
            self._log_error(category, name, error)

    def _on_job_reverted(self, category: str, row: int) -> None:
        status_item = self._group_sections[category].table.item(row, 3)
        status_item.setText("Ready")
        status_item.setForeground(QBrush())
        status_item.setToolTip("")

    def _log_error(self, category: str, name: str, error: str) -> None:
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self._error_log.append(f"[{timestamp}] [{category}] {name}\n{error.strip() or 'unknown error'}")
        self.details_button.setVisible(True)

    def _show_error_log(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Error Log")
        dialog.resize(640, 420)
        layout = QVBoxLayout(dialog)

        text_view = QPlainTextEdit()
        text_view.setReadOnly(True)
        text_view.setPlainText("\n\n".join(self._error_log))
        layout.addWidget(text_view)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        copy_button = QPushButton("Copy All")
        copy_button.clicked.connect(lambda: QGuiApplication.clipboard().setText(text_view.toPlainText()))
        button_row.addWidget(copy_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        dialog.exec()

    def _on_conversion_finished(self, success_count: int, attempted: int, stopped: bool) -> None:
        file_word = "file" if attempted == 1 else "files"
        if stopped:
            self.bottom_status_label.setText(f"Stopped — {success_count}/{attempted} {file_word} converted")
        else:
            self.bottom_status_label.setText(f"Successfully converted {success_count}/{attempted} {file_word}")
        self._converting = False
        self._set_all_controls_enabled(True)
        self._set_bottom_bar_mode(processing=False)
        self._conversion_worker = None
        self._conversion_control = None
