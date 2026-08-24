"""mediaconvert main window: ImageOptim-style drag-and-drop batch format conversion."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
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
    QStyle,
    QVBoxLayout,
    QWidget,
)

from mediaconvert.categorize import MixedCategoryError, categorize, target_formats
from mediaconvert.converter import convert_file


class MainWindow(QMainWindow):
    def __init__(self, initial_paths: list[Path] | None = None):
        super().__init__()
        self.setWindowTitle("mediaconvert")
        self.resize(560, 420)
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

        root.addWidget(self._build_bottom_bar())

        self.setCentralWidget(central)
        self._show_empty_state("Drag and drop image, video, or audio files onto the area above")

        if initial_paths:
            self._load_paths(initial_paths)

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

    def _show_list_state(self) -> None:
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
        event.acceptProposedAction()
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self._load_paths(paths)

    def _open_files_dialog(self) -> None:
        if self._converting:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Open files")
        if files:
            new_paths = [Path(f) for f in files]
            combined = self._paths + new_paths if self._paths else new_paths
            self._load_paths(combined)

    # -- icons ----------------------------------------------------------------

    def _icon_for_category(self, category: str) -> QIcon:
        style = self.style()
        icon_map = {
            "image": QStyle.SP_FileIcon,
            "video": QStyle.SP_MediaPlay,
            "audio": QStyle.SP_MediaVolume,
        }
        return style.standardIcon(icon_map.get(category, QStyle.SP_FileIcon))

    # -- batch loading and conversion ---------------------------------------

    def _load_paths(self, paths: list[Path]) -> None:
        if not paths or self._converting:
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
        icon = self._icon_for_category(category)
        for p in paths:
            item = QListWidgetItem(f"{p.name}  —  Ready")
            item.setIcon(icon)
            self.file_list.addItem(item)

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

        try:
            success_count = 0
            for i, path in enumerate(self._paths):
                item = self.file_list.item(i)
                item.setText(f"{path.name}  —  Converting…")
                QApplication.processEvents()
                result = convert_file(path, fmt, self._category)
                if result.success:
                    success_count += 1
                    item.setText(f"{path.name}  —  Done")
                else:
                    error_summary = (result.error or "").strip().splitlines()
                    short_error = error_summary[-1] if error_summary else "unknown error"
                    if len(short_error) > 120:
                        short_error = short_error[:117] + "..."
                    item.setText(f"{path.name}  —  Failed: {short_error}")
                    item.setToolTip(result.error or "")

            self.bottom_status_label.setText(f"Converted {success_count}/{len(self._paths)} file(s)")
        finally:
            self._converting = False
            self.convert_button.setEnabled(True)
            self.add_button.setEnabled(True)
