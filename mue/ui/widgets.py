"""Petits widgets maison : interrupteur, barre de progression fine, pastille de format."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import (QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt,
                          pyqtProperty)
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QWidget

from . import theme


def asset(name: str) -> Path:
    import sys
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parents[2]
    return base / "assets" / name


def app_icon() -> QIcon:
    ico = asset("mue.ico")
    png = asset("mue.png")
    icon = QIcon()
    if png.exists():
        icon.addFile(str(png))
    if ico.exists():
        icon.addFile(str(ico))
    return icon


def app_pixmap(size: int) -> QPixmap:
    pm = QPixmap(str(asset("mue.png")))
    if pm.isNull():
        return pm
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class Toggle(QAbstractButton):
    """Interrupteur on/off animé."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def get_knob(self) -> float:
        return self._pos

    def set_knob(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = pyqtProperty(float, get_knob, set_knob)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        off, on = QColor("#2C2C3A"), QColor(theme.VIOLET)
        t = self._pos
        track = QColor(int(off.red() + (on.red() - off.red()) * t),
                       int(off.green() + (on.green() - off.green()) * t),
                       int(off.blue() + (on.blue() - off.blue()) * t))
        if not self.isEnabled():
            track.setAlpha(110)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * t
        p.setBrush(QColor("#FFFFFF") if t > 0.5 else QColor("#B9B9C8"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class ThinProgress(QWidget):
    """Barre de progression fine en dégradé (ou couleur unie pour OK/erreur)."""

    def __init__(self, height: int = 4, parent: QWidget | None = None):
        super().__init__(parent)
        self._value = 0.0
        self._color: str | None = None
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def get_value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, v))
        self.update()

    value = pyqtProperty(float, get_value, set_value)

    def animate_to(self, v: float) -> None:
        if abs(v - self._value) < 0.001:
            return
        self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(v)
        self._anim.start()

    def set_color(self, color: str | None) -> None:
        self._color = color
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        rad = r.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#26262F"))
        p.drawRoundedRect(r, rad, rad)
        if self._value <= 0:
            return
        fill = QRectF(0, 0, max(r.height(), r.width() * self._value), r.height())
        path = QPainterPath()
        path.addRoundedRect(fill, rad, rad)
        if self._color:
            p.fillPath(path, QColor(self._color))
        else:
            p.fillPath(path, theme.accent_gradient(0, 0, r.width(), 0))


class Badge(QLabel):
    """Pastille « JPG → PNG » colorée selon la catégorie du fichier."""

    def __init__(self, text: str, color: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        c = QColor(color)
        self.setFont(theme.font(7.5, 63))
        self.setStyleSheet(
            f"color: {color}; background: rgba({c.red()},{c.green()},{c.blue()},30);"
            f"border: 1px solid rgba({c.red()},{c.green()},{c.blue()},70);"
            "border-radius: 6px; padding: 2px 7px;")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
