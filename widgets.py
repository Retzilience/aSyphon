# widgets.py
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QEasingCurve, QPropertyAnimation, Property, QSize
from PySide6.QtGui import QPainter, QColor, QFontMetrics, QPen
from PySide6.QtWidgets import QAbstractButton, QComboBox, QStyle, QStyleOptionComboBox, QLabel


class ToggleSwitch(QAbstractButton):
    """
    Pastel sliding switch.
    - checked: On (pastel green)
    - unchecked: Off (pastel red)
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._offset = 0.0  # 0..1
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        self._on_bg = QColor("#7fd6a6")   # pastel green
        self._off_bg = QColor("#e58b8b")  # pastel red
        self._knob = QColor("#f2f2f2")
        self._border = QColor("#2a2a30")

        self.toggled.connect(self._on_toggled)
        self._sync_offset()

        self.setFixedSize(46, 24)

    def sizeHint(self) -> QSize:
        return QSize(46, 24)

    def _sync_offset(self) -> None:
        self._offset = 1.0 if self.isChecked() else 0.0
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, v: float) -> None:
        self._offset = float(v)
        self.update()

    offset = Property(float, get_offset, set_offset)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        r = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        radius = r.height() / 2.0

        bg = self._on_bg if self.isChecked() else self._off_bg
        p.setPen(QPen(self._border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(r, radius, radius)

        margin = 3.0
        d = r.height() - 2 * margin
        x = r.x() + margin + self._offset * (r.width() - 2 * margin - d)
        knob_rect = QRectF(x, r.y() + margin, d, d)

        p.setPen(Qt.NoPen)
        p.setBrush(self._knob)
        p.drawEllipse(knob_rect)

        p.end()


class ElideComboBox(QComboBox):
    """
    Prevents horizontal overflow by eliding the displayed current text.
    The popup list remains full text.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(12)

    def paintEvent(self, event) -> None:
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)

        fm = QFontMetrics(opt.fontMetrics)
        elide_width = max(10, self.rect().width() - 38)
        opt.currentText = fm.elidedText(opt.currentText, Qt.ElideRight, elide_width)

        p = QPainter(self)
        self.style().drawComplexControl(QStyle.CC_ComboBox, opt, p, self)
        self.style().drawControl(QStyle.CE_ComboBoxLabel, opt, p, self)
        p.end()


class StatusPill(QLabel):
    """
    Compact fixed-width status indicator to avoid wide rows.
    Details go in tooltip.
    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedWidth(90)
        self.setText("Off")
        self.set_state("off")

    def set_state(self, state: str) -> None:
        # state: off | on | pending | error
        if state == "on":
            bg = "#233a2c"
            bd = "#2f6b45"
            fg = "#cfeedd"
        elif state == "pending":
            bg = "#3a3424"
            bd = "#7a6231"
            fg = "#f3e6c8"
        elif state == "error":
            bg = "#3a2424"
            bd = "#7a3131"
            fg = "#f3c8c8"
        else:
            bg = "#2a2a30"
            bd = "#3a3a42"
            fg = "#d6d6d6"

        self.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                border: 1px solid {bd};
                border-radius: 10px;
                padding: 4px 8px;
                color: {fg};
                font-weight: 600;
            }}
            """
        )
