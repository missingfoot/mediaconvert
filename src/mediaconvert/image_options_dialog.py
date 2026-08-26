"""Dialog for PNG/JPEG optimization settings, opened from a category's Options button."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
)

from mediaconvert import settings_dialog


def _slider_row(layout: QVBoxLayout, minimum: int, maximum: int, value: int) -> tuple[QSlider, QLabel]:
    slider = QSlider(Qt.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    label = QLabel(str(value))
    label.setFixedWidth(28)
    row = QHBoxLayout()
    row.addWidget(slider, stretch=1)
    row.addWidget(label)
    layout.addLayout(row)
    return slider, label


class ImageOptionsDialog(QDialog):
    def __init__(self, fmt: str, parent=None):
        super().__init__(parent)
        self._is_png = fmt == "png"
        self.setWindowTitle("PNG Options" if self._is_png else "JPEG Options")

        layout = QVBoxLayout(self)
        if self._is_png:
            self._build_png_controls(layout)
        else:
            self._build_jpeg_controls(layout)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def _build_png_controls(self, layout: QVBoxLayout) -> None:
        layout.addWidget(QLabel("Compression mode"))
        lossless_radio = QRadioButton("Lossless (no quality loss)")
        lossy_radio = QRadioButton("Lossy (reduces color palette, smaller files)")
        layout.addWidget(lossless_radio)
        layout.addWidget(lossy_radio)
        if settings_dialog.get_png_mode() == "lossy":
            lossy_radio.setChecked(True)
        else:
            lossless_radio.setChecked(True)

        layout.addWidget(QLabel("Optimization level"))
        level_slider, level_label = _slider_row(layout, 0, 6, settings_dialog.get_oxipng_level())
        level_hint = QLabel("Larger, faster → smaller, slower")
        level_hint.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(level_hint)

        layout.addWidget(QLabel("Minimum quality (lossy mode only)"))
        quality_slider, quality_label = _slider_row(
            layout, 0, 100, settings_dialog.get_pngquant_quality_min()
        )
        quality_slider.setEnabled(lossy_radio.isChecked())

        def save_mode() -> None:
            settings_dialog.set_png_mode("lossy" if lossy_radio.isChecked() else "lossless")
            quality_slider.setEnabled(lossy_radio.isChecked())

        lossless_radio.toggled.connect(save_mode)
        lossy_radio.toggled.connect(save_mode)
        level_slider.valueChanged.connect(
            lambda v: (level_label.setText(str(v)), settings_dialog.set_oxipng_level(v))
        )
        quality_slider.valueChanged.connect(
            lambda v: (quality_label.setText(str(v)), settings_dialog.set_pngquant_quality_min(v))
        )

    def _build_jpeg_controls(self, layout: QVBoxLayout) -> None:
        layout.addWidget(QLabel("Quality"))
        quality_slider, quality_label = _slider_row(
            layout, 1, 100, settings_dialog.get_jpeg_quality()
        )
        quality_slider.valueChanged.connect(
            lambda v: (quality_label.setText(str(v)), settings_dialog.set_jpeg_quality(v))
        )
