"""Settings window (sidebar: File Settings / About) and persisted settings."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mediaconvert import __version__
from mediaconvert.image_convert import ImageOptions

SAME_AS_SOURCE = "same"
CONVERTED_SUBFOLDER = "converted_subfolder"
CUSTOM_FOLDER = "custom"

_ABOUT_HTML = f"""
<h2>Convert</h2>
<p>Version {__version__}</p>
<p>Drag-and-drop image, video, and audio format conversion.</p>
<p>Made by <a href="https://www.jamessparkes.com/">James Sparkes</a></p>
<p><b>Built with:</b></p>
<ul>
<li>PySide6 (Qt for Python)</li>
<li>ImageMagick</li>
<li>ffmpeg</li>
<li>libwebp (cwebp / gif2webp)</li>
</ul>
<p><b>Icon:</b><br>
<a href="https://www.flaticon.com/free-icons/convert" title="convert icons">
Convert icons created by Taufik Ramadhan - Flaticon</a></p>
"""


def _settings() -> QSettings:
    return QSettings("mediaconvert", "mediaconvert")


def get_output_location() -> str:
    return _settings().value("output_location", SAME_AS_SOURCE)


def get_custom_output_dir() -> str:
    return _settings().value("custom_output_dir", "")


def resolve_output_dir(src_dir: Path) -> Path | None:
    """Directory conversions should write to for a file living in src_dir,
    or None to mean "same as source" (no override)."""
    location = get_output_location()
    if location == CONVERTED_SUBFOLDER:
        return src_dir / "Converted"
    if location == CUSTOM_FOLDER:
        custom = get_custom_output_dir()
        return Path(custom) if custom else None
    return None


def get_png_optimize() -> bool:
    return _settings().value("png_optimize", False, type=bool)


def set_png_optimize(enabled: bool) -> None:
    _settings().setValue("png_optimize", enabled)


def get_png_mode() -> str:
    return _settings().value("png_mode", "lossless")


def set_png_mode(mode: str) -> None:
    _settings().setValue("png_mode", mode)


def get_oxipng_level() -> int:
    return int(_settings().value("oxipng_level", 4))


def set_oxipng_level(level: int) -> None:
    _settings().setValue("oxipng_level", level)


def get_pngquant_quality_min() -> int:
    return int(_settings().value("pngquant_quality_min", 65))


def set_pngquant_quality_min(value: int) -> None:
    _settings().setValue("pngquant_quality_min", value)


def get_jpeg_optimize() -> bool:
    return _settings().value("jpeg_optimize", False, type=bool)


def set_jpeg_optimize(enabled: bool) -> None:
    _settings().setValue("jpeg_optimize", enabled)


def get_jpeg_quality() -> int:
    return int(_settings().value("jpeg_quality", 85))


def set_jpeg_quality(value: int) -> None:
    _settings().setValue("jpeg_quality", value)


def get_image_options() -> ImageOptions:
    return ImageOptions(
        png_optimize=get_png_optimize(),
        png_mode=get_png_mode(),
        oxipng_level=get_oxipng_level(),
        pngquant_quality_min=get_pngquant_quality_min(),
        jpeg_optimize=get_jpeg_optimize(),
        jpeg_quality=get_jpeg_quality(),
    )


_PAGE_TITLES = ["File Settings", "About"]


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(680, 480)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, stretch=1)

        sidebar = QListWidget()
        sidebar.setFrameShape(QListWidget.NoFrame)
        sidebar.setFixedWidth(140)
        sidebar.setStyleSheet(
            "QListWidget { border: none; border-right: 1px solid rgba(127, 127, 127, 90); }"
        )
        sidebar.addItem(QListWidgetItem("File Settings"))
        sidebar.addItem(QListWidgetItem("About"))

        sidebar_container = QWidget()
        sidebar_container_layout = QVBoxLayout(sidebar_container)
        sidebar_container_layout.setContentsMargins(0, 1, 0, 0)
        sidebar_container_layout.setSpacing(0)
        sidebar_container_layout.addWidget(sidebar)
        body.addWidget(sidebar_container)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)

        self.page_title_label = QLabel("")
        self.page_title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        content_layout.addWidget(self.page_title_label)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_file_settings_page())
        self.pages.addWidget(self._build_about_page())
        content_layout.addWidget(self.pages, stretch=1)

        body.addWidget(content, stretch=1)

        sidebar.currentRowChanged.connect(self._change_page)
        sidebar.setCurrentRow(0)

        footer = QWidget()
        footer.setObjectName("settingsFooter")
        footer.setStyleSheet(
            "#settingsFooter { border-top: 1px solid rgba(127, 127, 127, 90); }"
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 8, 8, 8)
        footer_layout.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        footer_layout.addWidget(close_button)
        root.addWidget(footer)

    def _change_page(self, row: int) -> None:
        self.pages.setCurrentIndex(row)
        self.page_title_label.setText(_PAGE_TITLES[row])

    # -- pages --------------------------------------------------------------

    def _build_file_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        current = get_output_location()

        layout.addWidget(QLabel("Output location"))

        self.same_radio = QRadioButton("Same as source (next to the original file)")
        self.converted_radio = QRadioButton('"Converted" subfolder in the source directory')
        self.custom_radio = QRadioButton("Custom folder…")
        layout.addWidget(self.same_radio)
        layout.addWidget(self.converted_radio)

        custom_row = QHBoxLayout()
        custom_row.addWidget(self.custom_radio)
        self.custom_path_label = QLabel(get_custom_output_dir() or "(none selected)")
        custom_row.addWidget(self.custom_path_label, stretch=1)
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse)
        custom_row.addWidget(browse_button)
        layout.addLayout(custom_row)

        if current == CONVERTED_SUBFOLDER:
            self.converted_radio.setChecked(True)
        elif current == CUSTOM_FOLDER:
            self.custom_radio.setChecked(True)
        else:
            self.same_radio.setChecked(True)

        self.same_radio.toggled.connect(self._save)
        self.converted_radio.toggled.connect(self._save)
        self.custom_radio.toggled.connect(self._save)

        layout.addStretch(1)
        return page

    def _build_about_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        about_label = QLabel(_ABOUT_HTML)
        about_label.setWordWrap(True)
        about_label.setOpenExternalLinks(True)
        about_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(about_label)
        layout.addStretch(1)
        return page

    # -- actions --------------------------------------------------------------

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if directory:
            _settings().setValue("custom_output_dir", directory)
            self.custom_path_label.setText(directory)
            self.custom_radio.setChecked(True)
            self._save()

    def _save(self) -> None:
        if self.converted_radio.isChecked():
            _settings().setValue("output_location", CONVERTED_SUBFOLDER)
        elif self.custom_radio.isChecked():
            _settings().setValue("output_location", CUSTOM_FOLDER)
        else:
            _settings().setValue("output_location", SAME_AS_SOURCE)
