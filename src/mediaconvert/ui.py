"""mediaconvert main window: ImageOptim-style drag-and-drop batch format conversion."""

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

from mediaconvert.categorize import MixedCategoryError, categorize, target_formats
from mediaconvert.converter import convert_file
from mediaconvert.icons import svg_pixmap
from mediaconvert.settings_dialog import SettingsDialog, resolve_output_dir

_ARROW_DOWN_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>"""
_CIRCLE_ALERT_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>"""
_DEFAULT_HINT = "Click to add or drag and drop image, video, or audio files"


class MainWindow(QMainWindow):
    def __init__(self, initial_paths: list[Path] | None = None):
        super().__init__()
        self.setWindowTitle("Convert")
        self.resize(820, 600)
        self.setAcceptDrops(True)

        self._paths: list[Path] = []
        self._category: str | None = None
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
            self._load_paths(initial_paths)

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

        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setStyleSheet("#topBar { border-bottom: 1px solid rgba(127, 127, 127, 90); }")
        toolbar = QHBoxLayout(top_bar)
        toolbar.setContentsMargins(8, 8, 8, 8)
        self.add_button = QPushButton("Add files")
        self.add_button.clicked.connect(self._open_files_dialog)
        toolbar.addWidget(self.add_button)
        self.info_label = QLabel("")
        toolbar.addWidget(self.info_label)
        toolbar.addStretch(1)
        toolbar.addWidget(QLabel("Convert to:"))
        self.format_combo = QComboBox()
        toolbar.addWidget(self.format_combo)
        layout.addWidget(top_bar)

        self.file_table = QTableWidget(0, 4)
        self.file_table.setHorizontalHeaderLabels(["File Name", "Size", "Type", "Status"])
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_table.customContextMenuRequested.connect(self._show_context_menu)
        self.file_table.cellDoubleClicked.connect(self._open_row_file)
        self.file_table.setShowGrid(False)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setSortingEnabled(True)
        header = self.file_table.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        self.file_table.setColumnWidth(1, 120)
        self.file_table.setColumnWidth(2, 120)
        self.file_table.setColumnWidth(3, 140)
        layout.addWidget(self.file_table, stretch=1)

        return page

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("bottomBar")
        bar.setStyleSheet("#bottomBar { border-top: 1px solid rgba(127, 127, 127, 90); }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 8, 8, 8)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_button)

        self.bottom_status_label = QLabel("")
        self.bottom_status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.bottom_status_label, stretch=1)

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
        self.file_table.show()
        self.info_label.setText(f"{len(self._paths)} file(s) added")
        self.bottom_status_label.setText("")
        self.convert_button.setEnabled(True)

    # -- drag and drop / file dialog ----------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        event.acceptProposedAction()
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self._load_paths(paths)

    def _open_row_file(self, row: int, column: int) -> None:
        if self._converting:
            return
        path = Path(self.file_table.item(row, 0).data(Qt.UserRole))
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _show_context_menu(self, pos) -> None:
        if self._converting:
            return
        row = self.file_table.rowAt(pos.y())
        if row < 0:
            return

        selection_model = self.file_table.selectionModel()
        selected_rows = {index.row() for index in selection_model.selectedRows()}
        if row not in selected_rows:
            self.file_table.selectRow(row)
            selected_rows = {row}

        menu = QMenu(self)
        remove_label = "Remove" if len(selected_rows) == 1 else f"Remove {len(selected_rows)} Files"
        remove_action = menu.addAction(remove_label)
        remove_action.triggered.connect(lambda: self._remove_rows(selected_rows))

        if len(selected_rows) == 1:
            (only_row,) = selected_rows
            path = Path(self.file_table.item(only_row, 0).data(Qt.UserRole))
            menu.addSeparator()
            open_action = menu.addAction("Open File")
            open_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
            open_folder_action = menu.addAction("Open Containing Folder")
            open_folder_action.triggered.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
            )

        menu.exec(self.file_table.viewport().mapToGlobal(pos))

    def _remove_rows(self, rows: set[int]) -> None:
        for row in sorted(rows, reverse=True):
            self.file_table.removeRow(row)
        self._paths = [
            Path(self.file_table.item(r, 0).data(Qt.UserRole)) for r in range(self.file_table.rowCount())
        ]
        if not self._paths:
            self._category = None
            self._show_empty_state(_DEFAULT_HINT)
        else:
            self.info_label.setText(f"{len(self._paths)} file(s) added")

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()

    def _open_files_dialog(self) -> None:
        if self._converting:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Open files")
        if files:
            new_paths = [Path(f) for f in files]
            combined = self._paths + new_paths if self._paths else new_paths
            self._load_paths(combined)

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

    def _load_paths(self, paths: list[Path]) -> None:
        if not paths or self._converting:
            return
        try:
            category = categorize(paths)
        except MixedCategoryError as e:
            self._paths = []
            self._category = None
            self._show_empty_state(str(e), error=True)
            return

        self._paths = paths
        self._category = category

        self.file_table.setSortingEnabled(False)
        self.file_table.setRowCount(0)
        self.file_table.show()
        icon = self._icon_for_category(category)
        self.file_table.setRowCount(len(paths))
        for row, p in enumerate(paths):
            name_item = QTableWidgetItem(p.name)
            name_item.setIcon(icon)
            name_item.setData(Qt.UserRole, str(p))
            self.file_table.setItem(row, 0, name_item)
            self.file_table.setItem(row, 1, QTableWidgetItem(self._human_size(p)))
            self.file_table.setItem(row, 2, QTableWidgetItem(self._type_for_path(p)))
            self.file_table.setItem(row, 3, QTableWidgetItem("Ready"))
        self.file_table.setSortingEnabled(True)

        self.format_combo.clear()
        self.format_combo.addItems(target_formats(category))

        self._show_list_state()

    def _convert_batch(self) -> None:
        fmt = self.format_combo.currentText()
        if not fmt or not self._paths:
            return
        self._converting = True
        self.convert_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.file_table.setSortingEnabled(False)

        try:
            success_count = 0
            for row in range(self.file_table.rowCount()):
                name_item = self.file_table.item(row, 0)
                path = Path(name_item.data(Qt.UserRole))
                status_item = self.file_table.item(row, 3)
                status_item.setForeground(QBrush())
                status_item.setText("Converting…")
                QApplication.processEvents()
                out_dir = resolve_output_dir(path.parent)
                result = convert_file(path, fmt, self._category, out_dir)
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

            self.bottom_status_label.setText(f"Converted {success_count}/{len(self._paths)} file(s)")
        finally:
            self._converting = False
            self.convert_button.setEnabled(True)
            self.add_button.setEnabled(True)
            self.file_table.setSortingEnabled(True)
