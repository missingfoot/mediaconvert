"""mediaconvert main window: ImageOptim-style drag-and-drop batch format conversion."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QUrl, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mediaconvert.categorize import CATEGORY_ORDER, split_by_category, target_formats
from mediaconvert.converter import convert_file
from mediaconvert.icons import svg_pixmap
from mediaconvert.settings_dialog import SettingsDialog, resolve_output_dir

_ARROW_DOWN_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>"""
_CIRCLE_ALERT_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>"""
_DEFAULT_HINT = "Click to add or drag and drop image, video, or audio files"


def _pluralize(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


@dataclass
class GroupSection:
    container: QWidget
    header_label: QLabel
    combo: QComboBox
    options_button: QPushButton
    table: QTableWidget


class MainWindow(QMainWindow):
    def __init__(self, initial_paths: list[Path] | None = None):
        super().__init__()
        self.setWindowTitle("Convert")
        self.resize(820, 600)
        self.setAcceptDrops(True)

        self._groups: dict[str, list[Path]] = {}
        self._group_sections: dict[str, GroupSection] = {}
        self._converting = False

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
        return super().eventFilter(obj, event)

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for category in CATEGORY_ORDER:
            section = self._build_group_section(category)
            self._group_sections[category] = section
            section.container.hide()
            layout.addWidget(section.container, stretch=1)

        return page

    def _build_group_section(self, category: str) -> GroupSection:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("groupHeader")
        header.setStyleSheet(
            "#groupHeader { border-bottom: 1px solid rgba(127, 127, 127, 90); }"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 8, 8, 8)

        header_label = QLabel("")
        header_layout.addWidget(header_label)
        header_layout.addStretch(1)
        header_layout.addWidget(QLabel("Convert to:"))
        combo = QComboBox()
        header_layout.addWidget(combo)
        options_button = QPushButton("Options")
        options_button.setEnabled(False)
        header_layout.addWidget(options_button)
        outer.addWidget(header)

        table = QTableWidget(0, 4)
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
            table=table,
        )

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("bottomBar")
        bar.setStyleSheet("#bottomBar { border-top: 1px solid rgba(127, 127, 127, 90); }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 8, 8, 8)

        self.add_button = QPushButton("Add files")
        self.add_button.clicked.connect(self._open_files_dialog)
        layout.addWidget(self.add_button)

        self.bottom_status_label = QLabel("")
        self.bottom_status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.bottom_status_label, stretch=1)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_button)

        self.convert_button = QPushButton("Convert")
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
        if self._converting:
            return
        table = self._group_sections[category].table
        path = Path(table.item(row, 0).data(Qt.UserRole))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _show_context_menu(self, category: str, pos) -> None:
        if self._converting:
            return
        table = self._group_sections[category].table
        row = table.rowAt(pos.y())
        if row < 0:
            return

        selection_model = table.selectionModel()
        selected_rows = {index.row() for index in selection_model.selectedRows()}
        if row not in selected_rows:
            table.selectRow(row)
            selected_rows = {row}

        menu = QMenu(self)
        remove_label = "Remove" if len(selected_rows) == 1 else f"Remove {len(selected_rows)} Files"
        remove_action = menu.addAction(remove_label)
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

        menu.exec(table.viewport().mapToGlobal(pos))

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

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()

    def _open_files_dialog(self) -> None:
        if self._converting:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Open files")
        if files:
            self._add_paths([Path(f) for f in files])

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

    def _add_paths(self, paths: list[Path]) -> None:
        if not paths or self._converting:
            return
        groups, ignored = split_by_category(paths)

        if not self._groups and not groups:
            self._show_empty_state("No supported files were found.", error=True)
            return

        added_count = 0
        for category, new_paths in groups.items():
            added_count += len(new_paths)
            self._add_to_group(category, new_paths)

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
        icon = self._icon_for_category(category)
        start_row = section.table.rowCount()
        section.table.setRowCount(start_row + len(new_paths))
        for offset, p in enumerate(new_paths):
            row = start_row + offset
            name_item = QTableWidgetItem(p.name)
            name_item.setIcon(icon)
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
        if not self._groups:
            return
        self._converting = True
        self.convert_button.setEnabled(False)
        self.add_button.setEnabled(False)

        try:
            total = 0
            success_count = 0
            for category in CATEGORY_ORDER:
                if category not in self._groups:
                    continue
                section = self._group_sections[category]
                fmt = section.combo.currentText()
                if not fmt:
                    continue
                table = section.table
                table.setSortingEnabled(False)
                for row in range(table.rowCount()):
                    total += 1
                    name_item = table.item(row, 0)
                    path = Path(name_item.data(Qt.UserRole))
                    status_item = table.item(row, 3)
                    status_item.setForeground(QBrush())
                    status_item.setText("Converting…")
                    QApplication.processEvents()
                    out_dir = resolve_output_dir(path.parent)
                    result = convert_file(path, fmt, category, out_dir)
                    if result.success:
                        success_count += 1
                        status_item.setText("Done")
                        status_item.setForeground(QBrush(QColor("#2ecc71")))
                    else:
                        error_summary = (result.error or "").strip().splitlines()
                        short_error = error_summary[-1] if error_summary else "unknown error"
                        if len(short_error) > 120:
                            short_error = short_error[:117] + "..."
                        status_item.setText(f"Failed: {short_error}")
                        status_item.setToolTip(result.error or "")
                        status_item.setForeground(QBrush(QColor("#e74c3c")))
                table.setSortingEnabled(True)

            self.bottom_status_label.setText(f"Converted {success_count}/{total} file(s)")
        finally:
            self._converting = False
            self.convert_button.setEnabled(True)
            self.add_button.setEnabled(True)
