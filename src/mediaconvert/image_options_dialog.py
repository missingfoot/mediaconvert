"""Dialog for PNG/JPEG optimization settings, opened from a category's Options button."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from mediaconvert import settings_dialog


def _hint(layout: QVBoxLayout, text: str, indent: int = 0) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("color: palette(placeholder-text);")
    if indent:
        label.setContentsMargins(indent, 0, 0, 0)
    layout.addWidget(label)
    return label


def _heading(layout: QVBoxLayout, text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-weight: 600;")
    layout.addWidget(label)
    return label


def _divider(layout: QVBoxLayout) -> None:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    layout.addWidget(line)


def _radio_text_indent(radio: QRadioButton) -> int:
    """Left offset needed to line up with a QRadioButton's text, past its indicator."""
    style = radio.style()
    return (
        style.pixelMetric(QStyle.PM_ExclusiveIndicatorWidth, None, radio)
        + style.pixelMetric(QStyle.PM_RadioButtonLabelSpacing, None, radio)
    )


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
    """Settings only take effect when Apply is clicked - Cancel discards
    whatever was changed in the dialog."""

    def __init__(self, fmt: str, parent=None):
        super().__init__(parent)
        self._is_png = fmt == "png"
        self.setWindowTitle("PNG Options" if self._is_png else "JPEG Options")

        layout = QVBoxLayout(self)
        if self._is_png:
            self._build_png_controls(layout)
        else:
            self._build_jpeg_controls(layout)

        buttons = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._apply)
        apply_button.setDefault(True)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(apply_button)
        layout.addLayout(buttons)

    def _apply(self) -> None:
        if self._is_png:
            settings_dialog.set_png_optimize(self._optimize_checkbox.isChecked())
            settings_dialog.set_png_mode("lossy" if self._lossy_radio.isChecked() else "lossless")
            settings_dialog.set_oxipng_level(self._level_slider.value())
            settings_dialog.set_pngquant_quality_min(self._quality_slider.value())
        else:
            settings_dialog.set_jpeg_optimize(self._optimize_checkbox.isChecked())
            settings_dialog.set_jpeg_quality(self._quality_slider.value())
        self.accept()

    def _build_png_controls(self, layout: QVBoxLayout) -> None:
        optimize_checkbox = QCheckBox("Optimize")
        optimize_checkbox.setChecked(settings_dialog.get_png_optimize())
        layout.addWidget(optimize_checkbox)
        _hint(layout, "Off uses a plain ImageMagick conversion instead")
        self._optimize_checkbox = optimize_checkbox

        _divider(layout)

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(controls)

        _heading(controls_layout, "Compression mode")
        lossless_radio = QRadioButton("Lossless")
        controls_layout.addWidget(lossless_radio)
        indent = _radio_text_indent(lossless_radio)
        _hint(controls_layout, "No quality loss", indent)
        lossy_radio = QRadioButton("Lossy")
        controls_layout.addWidget(lossy_radio)
        _hint(controls_layout, "Reduces color palette, smaller files", indent)
        if settings_dialog.get_png_mode() == "lossy":
            lossy_radio.setChecked(True)
        else:
            lossless_radio.setChecked(True)
        self._lossy_radio = lossy_radio

        _divider(controls_layout)

        controls_layout.addWidget(QLabel("Optimization level"))
        _hint(controls_layout, "Larger, faster → smaller, slower")
        level_slider, level_label = _slider_row(controls_layout, 0, 6, settings_dialog.get_oxipng_level())
        self._level_slider = level_slider

        controls_layout.addWidget(QLabel("Minimum quality"))
        _hint(controls_layout, "Lower is smaller but riskier, with more visible color loss")
        quality_slider, quality_label = _slider_row(
            controls_layout, 0, 100, settings_dialog.get_pngquant_quality_min()
        )
        _hint(controls_layout, "65 is a good default for most photos")
        self._quality_slider = quality_slider

        def sync_enabled() -> None:
            controls.setEnabled(optimize_checkbox.isChecked())
            quality_slider.setEnabled(optimize_checkbox.isChecked() and lossy_radio.isChecked())

        optimize_checkbox.toggled.connect(sync_enabled)
        lossless_radio.toggled.connect(sync_enabled)
        lossy_radio.toggled.connect(sync_enabled)
        sync_enabled()

        level_slider.valueChanged.connect(lambda v: level_label.setText(str(v)))
        quality_slider.valueChanged.connect(lambda v: quality_label.setText(str(v)))

    def _build_jpeg_controls(self, layout: QVBoxLayout) -> None:
        optimize_checkbox = QCheckBox("Optimize")
        optimize_checkbox.setChecked(settings_dialog.get_jpeg_optimize())
        layout.addWidget(optimize_checkbox)
        _hint(layout, "Off uses a plain ImageMagick conversion instead")
        self._optimize_checkbox = optimize_checkbox

        _divider(layout)

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(controls)

        controls_layout.addWidget(QLabel("Quality"))
        quality_slider, quality_label = _slider_row(
            controls_layout, 1, 100, settings_dialog.get_jpeg_quality()
        )
        quality_slider.valueChanged.connect(lambda v: quality_label.setText(str(v)))
        self._quality_slider = quality_slider

        controls.setEnabled(optimize_checkbox.isChecked())
        optimize_checkbox.toggled.connect(controls.setEnabled)
