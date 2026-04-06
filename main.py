#!/usr/bin/env python3
import getpass
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Union
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QSettings, Signal, QByteArray, QSize, QDateTime, QStandardPaths, QTimer, QObject
from PySide6.QtGui import (
    QColor,
    QClipboard,
    QCursor,
    QFont,
    QGuiApplication,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QPolygonF,
    QRegion,
    QShortcut,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QWidget,
)
from PySide6.QtSvg import QSvgRenderer

@dataclass
class Stroke:
    path: QPainterPath
    color: QColor
    width: int
    opacity: float = 1.0


@dataclass
class TextItem:
    rect: QRectF
    text: str
    color: QColor
    font_size: int
    angle: float = 0.0


CanvasItem = Union[Stroke, TextItem]


class InlineTextEditor(QTextEdit):
    commit_requested = Signal()
    cancel_requested = Signal()
    live_text_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self._ignore_next_focus_out = False
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(
            """
            QTextEdit {
                background: rgba(30, 30, 30, 200);
                color: white;
                border: 1px dashed rgba(255, 255, 255, 180);
                border-radius: 4px;
                padding: 4px;
            }
            """
        )
        self.textChanged.connect(self._emit_live_update)

    def _emit_live_update(self) -> None:
        self.live_text_changed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
            event.accept()
            return

        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            event.accept()
            return

        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        if self._ignore_next_focus_out:
            self._ignore_next_focus_out = False
            event.accept()
            return

        self.commit_requested.emit()
        super().focusOutEvent(event)


class ColorButton(QPushButton):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color_value = QColor(color)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(color)
        self.setCheckable(True)
        self.update_style(active=False)

    def update_style(self, active: bool) -> None:
        border = "3px solid white" if active else "1px solid rgba(255, 255, 255, 60)"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {self.color_value.name()};
                border: {border};
                border-radius: 14px;
                padding: 0;
            }}
            QPushButton:hover {{
                border: 2px solid white;
            }}
            """
        )

SVG_ICON_PATHS: dict[str, str] = {
    "eye": """
    <path d="M3.5 12s3 -5 8.5 -5s8.5 5 8.5 5s-3 5 -8.5 5s-8.5 -5 -8.5 -5z" />
    <circle cx="12" cy="12" r="2.5" />
    """,
    "eye_off": """
    <path d="M3.5 12s3 -5 8.5 -5s8.5 5 8.5 5s-3 5 -8.5 5s-8.5 -5 -8.5 -5z" />
    <circle cx="12" cy="12" r="2.5" />
    <path d="M5 5l14 14" />
    """,
    "logo": """
    <path d="M12 3c-2.8 0 -5 2.2 -5 5c0 2.2 1.4 4 3.4 4.7l-1.2 5.3h1.8l.7 -3h1.6l.7 3h1.8l-1.2 -5.3c2 -0.7 3.4 -2.5 3.4 -4.7c0 -2.8 -2.2 -5 -5 -5z" />
    <path d="M10.6 8.4c0 -.8 .6 -1.4 1.4 -1.4s1.4 .6 1.4 1.4s-.6 1.4 -1.4 1.4s-1.4 -.6 -1.4 -1.4z" fill="white" stroke="none" />
    """,
    "pen": """
        <path d="M6 17l3.8 -.8l8.4 -8.4a2.2 2.2 0 0 0 -3.1 -3.1l-8.4 8.4l-.7 3.9z" />
        <path d="M13.5 5.5l5 5" />
    """,
    "highlighter": """
        <path d="M5.5 15.5l5 0l8 -8a2 2 0 0 0 -3 -3l-10 10l0 3z" />
        <path d="M12.5 5.5l6 6" />
        <path d="M5.5 19.5l8 0" />
    """,
    "text": """
        <path d="M6 6.5l12 0" />
        <path d="M12 6.5l0 11" />
        <path d="M9 17.5l6 0" />
    """,
    "line": """
        <path d="M6 18l12 -12" />
    """,
    "arrow": """
        <path d="M5 18l12 -12" />
        <path d="M12 6l5 0l0 5" />
    """,
    "rect": """
        <rect x="6" y="7" width="12" height="10" rx="1.5" />
    """,
    "circle": """
        <circle cx="12" cy="12" r="6" />
    """,
    "triangle": """
        <path d="M12 6l6 11l-12 0z" />
    """,
    "board": """
        <rect x="5" y="5" width="14" height="10" rx="1.2" />
        <path d="M10 19l2 -4l2 4" />
        <path d="M8.5 19l7 0" />
    """,
    "move": """
        <path d="M12 4l2.2 2.2h-1.4v3.6h3.6v-1.4l2.2 2.2l-2.2 2.2v-1.4h-3.6v3.6h1.4l-2.2 2.2l-2.2 -2.2h1.4v-3.6h-3.6v1.4l-2.2 -2.2l2.2 -2.2v1.4h3.6v-3.6h-1.4z" />
    """,
    "eraser": """
        <path d="M7 15l6 -8l5 5l-6 7l-5 -4z" />
        <path d="M11 19l7 0" />
    """,
    "mouse": """
        <path d="M8 4l8 7l-4 1l1.5 4.5l-2.2 .8l-1.5 -4.5l-2.8 2.2z" />
    """,
    "color": """
        <path d="M12 5c2.5 0 4.5 2 4.5 4.5c0 2.8 -2.4 4.5 -4.5 8c-2.1 -3.5 -4.5 -5.2 -4.5 -8c0 -2.5 2 -4.5 4.5 -4.5z" />
        <circle cx="12" cy="9.5" r="1.2" fill="white" stroke="none" />
    """,
    "off": """
        <path d="M7 7l10 10" />
        <path d="M17 7l-10 10" />
    """,
    "undo": """
        <path d="M9 8l-4 4l4 4" />
        <path d="M6 12h7a4 4 0 1 1 0 8h-2" />
    """,
    "redo": """
        <path d="M15 8l4 4l-4 4" />
        <path d="M18 12h-7a4 4 0 1 0 0 8h2" />
    """,
    "clear": """
        <path d="M6 8h12" />
        <path d="M9 8v-2h6v2" />
        <path d="M8 8l1 10h6l1 -10" />
        <path d="M10 11v4" />
        <path d="M14 11v4" />
    """,
    "screenshot": """
    <rect x="5" y="7" width="14" height="10" rx="2" />
    <circle cx="12" cy="12" r="3" />
    <path d="M9 7l1 -2h4l1 2" />
    """,
    "quit": """
        <path d="M9 7v-2h8v14h-8v-2" />
        <path d="M14 12h-9" />
        <path d="M8 9l-3 3l3 3" />
    """,
}

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

TOP_LOGO_PATH = str(ASSETS_DIR / "logo.png")
PEN_CURSOR_PATH = str(ASSETS_DIR / "pen.png")
HIGHLIGHTER_CURSOR_PATH = str(ASSETS_DIR / "highlighter.png")
TEXT_CURSOR_PATH = str(ASSETS_DIR / "text.png")
MOVE_CURSOR_PATH = str(ASSETS_DIR / "move.png")
ERASER_CURSOR_PATH = str(ASSETS_DIR / "eraser.png")
SCREENSHOT_CURSOR_PATH = str(ASSETS_DIR / "screenshot.png")

def make_svg_icon(
    icon_name: str,
    size: int = 22,
    stroke: str = "white",
    stroke_width: float = 1.8,
    fill: str = "none",
) -> QIcon:
    path_data = SVG_ICON_PATHS.get(icon_name, SVG_ICON_PATHS["pen"])
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24">
        <g stroke="{stroke}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round" fill="{fill}">
            {path_data}
        </g>
    </svg>
    """
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

def make_logo_icon_from_file(image_path: str, size: int = 24) -> QIcon:
    if not Path(image_path).exists():
        return make_svg_icon("logo", size=size, stroke="white", fill="none")

    pixmap = QPixmap(image_path)
    if pixmap.isNull():
        return make_svg_icon("logo", size=size, stroke="white", fill="none")

    scaled = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return QIcon(scaled)
    
class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.icon_name = icon_name
        self.base_tooltip = tooltip
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 42)
        self.setIconSize(QSize(22, 22))
        self.setText("")
        self.setCheckable(False)
        self._active = False
        self.apply_default_style()
        self.update_icon()

    def apply_default_style(self) -> None:
        border = "2px solid rgb(170, 170, 170)" if self._active else "1px solid rgb(95, 95, 95)"
        background = "rgb(90, 90, 90)" if self._active else "rgb(60, 60, 60)"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {background};
                border: {border};
                border-radius: 10px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background: rgb(85, 85, 85);
            }}
            """
        )

    def set_active(self, active: bool) -> None:
        self._active = active
        self.apply_default_style()

    def update_icon(
        self,
        *,
        stroke: str = "white",
        fill: str = "none",
        stroke_width: float = 1.8,
        size: int = 22,
    ) -> None:
        self.setIcon(make_svg_icon(
            self.icon_name,
            size=size,
            stroke=stroke,
            stroke_width=stroke_width,
            fill=fill,
        ))

class SizeDotsBar(QWidget):
    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sizes = [2, 4, 8, 14, 22]
        self._value = 4
        self.setFixedSize(150, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_sizes(self, sizes: list[int]) -> None:
        if not sizes:
            return
        self._sizes = sizes[:]
        nearest = min(self._sizes, key=lambda x: abs(x - self._value))
        self._value = nearest
        self.update()

    def setValue(self, value: int) -> None:
        nearest = min(self._sizes, key=lambda x: abs(x - value))
        if nearest == self._value:
            self.update()
            return
        self._value = nearest
        self.update()

    def value(self) -> int:
        return self._value

    def mousePressEvent(self, event: QMouseEvent) -> None:
        index = self.hit_index(event.position())
        if index is None:
            return
        self._value = self._sizes[index]
        self.update()
        self.valueChanged.emit(self._value)

    def hit_index(self, pos: QPointF) -> int | None:
        centers = self.dot_centers()
        for index, center in enumerate(centers):
            radius = self.dot_radius(index) + 6
            if math.hypot(pos.x() - center.x(), pos.y() - center.y()) <= radius:
                return index
        return None

    def dot_centers(self) -> list[QPointF]:
        count = len(self._sizes)
        if count == 1:
            return [QPointF(self.width() / 2, self.height() / 2)]

        left = 16.0
        right = self.width() - 16.0
        y = self.height() / 2
        step = (right - left) / (count - 1)
        return [QPointF(left + i * step, y) for i in range(count)]

    def dot_radius(self, index: int) -> float:
        radii = [3.0, 4.5, 6.0, 7.5, 9.0]
        if index < len(radii):
            return radii[index]
        return 6.0

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(70, 70, 70, 230))
        painter.drawRoundedRect(self.rect().adjusted(0, 4, 0, -4), 10, 10)

        centers = self.dot_centers()
        selected_index = min(range(len(self._sizes)), key=lambda i: abs(self._sizes[i] - self._value))

        for index, center in enumerate(centers):
            radius = self.dot_radius(index)
            if index == selected_index:
                painter.setBrush(QColor(255, 255, 255))
            else:
                painter.setBrush(QColor(20, 20, 20))
            painter.drawEllipse(center, radius, radius)

class ColorPalette(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.color_buttons: list[ColorButton] = []

        layout = QGridLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(6)
        self.setFixedWidth(140)

        colors = [
            "#00c853", "#00e676", "#64dd17", "#00ff00",
            "#00b0ff", "#0091ea", "#2979ff", "#00ffff",
            "#d500f9", "#aa00ff", "#ff1744", "#ff4081",
            "#ff9100", "#ffd600", "#ffff00", "#ff6d00",
            "#ffffff", "#d7ccc8", "#9e9e9e", "#000000",
        ]

        columns = 2
        for index, color in enumerate(colors):
            button = ColorButton(color)
            button.setFixedSize(26, 26)
            row = index // columns
            col = index % columns
            layout.addWidget(button, row, col)
            self.color_buttons.append(button)

        self.setStyleSheet(
            """
            QFrame {
                background: rgb(35, 35, 35);
                border: 1px solid rgb(85, 85, 85);
                border-radius: 10px;
            }
            """
        )

class SizePalette(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.size_slider = SizeDotsBar()
        self.size_value_label = QLabel("4")
        self.size_value_label.setFixedWidth(34)
        self.size_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_value_label.setStyleSheet(
            """
            QLabel {
                color: white;
                background: rgb(55, 55, 55);
                border: 1px solid rgb(95, 95, 95);
                border-radius: 8px;
                padding: 4px 6px;
                font-size: 13px;
                font-weight: 600;
            }
            """
        )

        layout.addWidget(self.size_slider)
        layout.addWidget(self.size_value_label)

        self.setStyleSheet(
            """
            QFrame {
                background: rgb(35, 35, 35);
                border: 1px solid rgb(85, 85, 85);
                border-radius: 10px;
            }
            """
        )

    def set_size_value(self, value: int) -> None:
        self.size_value_label.setText(str(value))

    def set_size_slider_range(self, minimum: int, maximum: int) -> None:
        if maximum <= 4:
            sizes = [minimum, minimum + 1, minimum + 2, max(minimum, maximum - 1), maximum]
        elif minimum == 8 and maximum == 96:
            sizes = [8, 14, 24, 48, 96]
        elif minimum == 6 and maximum == 64:
            sizes = [6, 12, 24, 40, 64]
        elif minimum == 8 and maximum == 72:
            sizes = [8, 16, 28, 48, 72]
        elif minimum == 1 and maximum == 48:
            sizes = [1, 4, 8, 14, 24]
        else:
            step = max(1, round((maximum - minimum) / 4))
            sizes = [
                minimum,
                minimum + step,
                minimum + step * 2,
                minimum + step * 3,
                maximum,
            ]

        cleaned: list[int] = []
        for size in sizes:
            clamped = max(minimum, min(size, maximum))
            if clamped not in cleaned:
                cleaned.append(clamped)

        while len(cleaned) < 5:
            cleaned.append(cleaned[-1])

        self.size_slider.set_sizes(cleaned[:5])

    def set_size_slider_value(self, value: int) -> None:
        self.size_slider.setValue(value)
        self.set_size_value(self.size_slider.value())

    def value(self) -> int:
        return self.size_slider.value()

class ScreenshotActionsPalette(QFrame):
    copy_clicked = Signal()
    save_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.copy_button = QPushButton("Copy")
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")

        for button in (self.copy_button, self.save_button, self.cancel_button):
            button.setMinimumHeight(34)
            layout.addWidget(button)

        self.copy_button.clicked.connect(self.copy_clicked.emit)
        self.save_button.clicked.connect(self.save_clicked.emit)
        self.cancel_button.clicked.connect(self.cancel_clicked.emit)

        self.setStyleSheet(
            """
            QFrame {
                background: rgb(35, 35, 35);
                border: 1px solid rgb(85, 85, 85);
                border-radius: 10px;
            }
            QPushButton {
                color: white;
                background: rgb(55, 55, 55);
                border: 1px solid rgb(95, 95, 95);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgb(75, 75, 75);
            }
            """
        )

class BoardPalette(QFrame):
    board_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.setFixedWidth(64)

        self.white_button = IconButton("board", "Whiteboard")
        self.black_button = IconButton("board", "Blackboard")
        self.off_button = IconButton("off", "Off")

        self.white_button.setStyleSheet(
            """
            QPushButton {
                background: white;
                border: 1px solid rgb(160, 160, 160);
                border-radius: 10px;
                padding: 4px;
            }
            QPushButton:hover {
                background: rgb(230, 230, 230);
            }
            """
        )
        self.white_button.update_icon(stroke="black")

        self.black_button.setStyleSheet(
            """
            QPushButton {
                background: rgb(20, 20, 20);
                border: 1px solid rgb(95, 95, 95);
                border-radius: 10px;
                padding: 4px;
            }
            QPushButton:hover {
                background: rgb(45, 45, 45);
            }
            """
        )
        self.black_button.update_icon(stroke="white")
        self.off_button.update_icon(stroke="white")

        for button in (self.white_button, self.black_button, self.off_button):
            button.setMinimumHeight(40)
            layout.addWidget(button)

        self.white_button.clicked.connect(lambda: self._select("white"))
        self.black_button.clicked.connect(lambda: self._select("black"))
        self.off_button.clicked.connect(lambda: self._select("off"))

        self.setStyleSheet(
            """
            QFrame {
                background: rgb(35, 35, 35);
                border: 1px solid rgb(85, 85, 85);
                border-radius: 10px;
            }
            """
        )

    def _select(self, mode: str) -> None:
        self.board_selected.emit(mode)
        self.hide()

class ShapePalette(QFrame):
    shape_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.setFixedWidth(64)

        self.line_button = IconButton("line", "Line")
        self.arrow_button = IconButton("arrow", "Arrow")
        self.rect_button = IconButton("rect", "Rect")
        self.circle_button = IconButton("circle", "Circle")
        self.triangle_button = IconButton("triangle", "Triangle")

        for button in (
            self.line_button,
            self.arrow_button,
            self.rect_button,
            self.circle_button,
            self.triangle_button,
        ):
            button.setMinimumHeight(34)
            layout.addWidget(button)

        self.line_button.clicked.connect(lambda: self._select("line"))
        self.arrow_button.clicked.connect(lambda: self._select("arrow"))
        self.rect_button.clicked.connect(lambda: self._select("rect"))
        self.circle_button.clicked.connect(lambda: self._select("circle"))
        self.triangle_button.clicked.connect(lambda: self._select("triangle"))

        self.setStyleSheet(
            """
            QFrame {
                background: rgb(35, 35, 35);
                border: 1px solid rgb(85, 85, 85);
                border-radius: 10px;
            }
            QPushButton {
                color: white;
                background: rgb(55, 55, 55);
                border: 1px solid rgb(95, 95, 95);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgb(75, 75, 75);
            }
            """
        )

    def _select(self, mode: str) -> None:
        self.shape_selected.emit(mode)
        self.hide()

class ToolPalette(QFrame):
    tool_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.setFixedWidth(64)

        self.pen_button = IconButton("pen", "Pen")
        self.highlighter_button = IconButton("highlighter", "Highlighter")
        self.text_button = IconButton("text", "Text")

        for button in (
            self.pen_button,
            self.highlighter_button,
            self.text_button,
        ):
            button.setMinimumHeight(34)
            layout.addWidget(button)

        self.pen_button.clicked.connect(lambda: self._select("pen"))
        self.highlighter_button.clicked.connect(lambda: self._select("highlighter"))
        self.text_button.clicked.connect(lambda: self._select("text"))

        self.setStyleSheet(
            """
            QFrame {
                background: rgb(35, 35, 35);
                border: 1px solid rgb(85, 85, 85);
                border-radius: 10px;
            }
            QPushButton {
                color: white;
                background: rgb(55, 55, 55);
                border: 1px solid rgb(95, 95, 95);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgb(75, 75, 75);
            }
            """
        )

    def _select(self, mode: str) -> None:
        self.tool_selected.emit(mode)
        self.hide()

class ToolbarWindow(QFrame):
    def __init__(self) -> None:
        super().__init__(None)

        self._drag_offset: QPoint | None = None
        self._drag_start_global: QPoint | None = None
        self._drag_started = False
        self.on_moved = None
        self.color_buttons: list[ColorButton] = []
        self.is_collapsed = False
        self._collapsible_widgets: list[QWidget] = []
        self.overlay = None

        self.setWindowTitle("clarivo Toolbar")
        toolbar_flags = (
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        if sys.platform.startswith("linux"):
            toolbar_flags |= Qt.WindowType.X11BypassWindowManagerHint

        self.setWindowFlags(toolbar_flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.title_label = QLabel("clarivo")
        self.logo_button = QPushButton()
        self.logo_button.setToolTip("clarivo")
        self.logo_button.setCursor(Qt.CursorShape.OpenHandCursor)
        self.logo_button.setFixedSize(42, 42)
        self.logo_button.setIconSize(QSize(24, 24))
        self.logo_button.setStyleSheet(
            """
            QPushButton {
                background: rgb(0, 0, 0);
                border: 2px solid white;
                border-radius: 21px;
                padding: 4px;
            }
            QPushButton:hover {
                background: rgb(20, 20, 20);
            }
            """
        )
        self.logo_button.setIcon(make_logo_icon_from_file(TOP_LOGO_PATH, 24))
        self.eye_button = IconButton("eye", "Hide Toolbar")
        self.eye_button.setFixedSize(42, 42)
        self.pen_button = IconButton("pen", "Pen")
        self.highlighter_button = IconButton("highlighter", "Highlighter")
        self.line_button = IconButton("line", "Line")
        self.arrow_button = IconButton("arrow", "Arrow")
        self.rect_button = IconButton("rect", "Rect")
        self.circle_button = IconButton("circle", "Circle")
        self.triangle_button = IconButton("triangle", "Triangle")
        self.tools_button = IconButton("pen", "Tools")
        self.shapes_button = IconButton("circle", "Shapes")
        self.text_button = IconButton("text", "Text")
        self.board_button = IconButton("board", "Board")
        self.move_button = IconButton("move", "Move")
        self.eraser_button = IconButton("eraser", "Eraser")
        self.mouse_button = IconButton("mouse", "Mouse")

        self.size_button = IconButton("circle", "Size")
        self.size_palette = SizePalette()
        self.size_slider = self.size_palette.size_slider
        self.size_value_label = self.size_palette.size_value_label

        self.undo_button = IconButton("undo", "Undo")
        self.redo_button = IconButton("redo", "Redo")
        self.clear_button = IconButton("clear", "Clear")
        self.screenshot_button = IconButton("screenshot", "Screenshot")
        self.quit_button = IconButton("quit", "Quit")

        self.color_button = IconButton("color", "Color")
        self.color_palette = ColorPalette()
        self.color_buttons = self.color_palette.color_buttons

        self.board_palette = BoardPalette()
        self.shape_palette = ShapePalette()
        self.tool_palette = ToolPalette()

        for button in (
            self.pen_button,
            self.highlighter_button,
            self.line_button,
            self.arrow_button,
            self.rect_button,
            self.circle_button,
            self.triangle_button,
            self.tools_button,
            self.shapes_button,
            self.text_button,
            self.board_button,
            self.move_button,
            self.eraser_button,
            self.mouse_button,
            self.color_button,
            self.undo_button,
            self.redo_button,
            self.clear_button,
            self.screenshot_button,
            self.quit_button,
        ):
            button.setMinimumHeight(36)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)



        layout.addWidget(self.logo_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self.eye_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self.mouse_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.tools_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.shapes_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.eraser_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.move_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self.size_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.color_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.undo_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.redo_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.clear_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.board_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.screenshot_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.quit_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self._collapsible_widgets = [
        self.tools_button,
        self.shapes_button,
        self.board_button,
        self.move_button,
        self.eraser_button,
        self.mouse_button,
        self.size_button,
        self.color_button,
        self.undo_button,
        self.redo_button,
        self.clear_button,
        self.screenshot_button,
        self.quit_button,
    ]

        self.setStyleSheet(
            """
            QFrame {
                background: rgb(30, 30, 30);
                border: 1px solid rgb(75, 75, 75);
                border-radius: 10px;
            }
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: 600;
                padding: 0 4px;
                border: none;
                background: transparent;
            }
            QPushButton {
                color: white;
                background: rgb(60, 60, 60);
                border: 1px solid rgb(95, 95, 95);
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgb(85, 85, 85);
            }
            """
        )

        self.adjustSize()

        self.installEventFilter(self)
        self.logo_button.installEventFilter(self)

        for widget in (
            self.tools_button,
            self.shapes_button,
            self.board_button,
            self.move_button,
            self.eraser_button,
            self.mouse_button,
            self.size_button,
            self.color_button,
            self.undo_button,
            self.redo_button,
            self.clear_button,
            self.screenshot_button,
            self.quit_button,
        ):
            widget.installEventFilter(self)

        self.board_button.clicked.connect(self.toggle_board_palette)
        self.tools_button.clicked.connect(self.toggle_tool_palette)
        self.shapes_button.clicked.connect(self.toggle_shape_palette)
        self.size_button.clicked.connect(self.toggle_size_palette)
        self.color_button.clicked.connect(self.toggle_color_palette)
        self.eye_button.clicked.connect(self.toggle_collapsed)

    def set_active_color(self, color: QColor) -> None:
        for button in self.color_buttons:
            is_active = button.color_value == color
            button.setChecked(is_active)
            button.update_style(active=is_active)

        self.set_color_button_preview(color)

    def set_size_value(self, value: int) -> None:
        self.size_value_label.setText(str(value))

    def set_size_slider_range(self, minimum: int, maximum: int) -> None:
        if maximum <= 4:
            sizes = [minimum, max(minimum, minimum + 1), max(minimum, minimum + 2), max(minimum, maximum - 1), maximum]
        elif maximum <= 12:
            sizes = [minimum, 2, 4, 6, maximum]
        elif maximum <= 24:
            sizes = [minimum, 4, 8, 12, maximum]
        else:
            sizes = [minimum, 4, 8, 14, maximum]

        cleaned: list[int] = []
        for size in sizes:
            clamped = max(minimum, min(size, maximum))
            if clamped not in cleaned:
                cleaned.append(clamped)

        while len(cleaned) < 5:
            cleaned.append(cleaned[-1])

        self.size_slider.set_sizes(cleaned[:5])

    def set_size_slider_value(self, value: int) -> None:
        self.size_slider.setValue(value)
        self.set_size_value(self.size_slider.value())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.color_palette.hide()
        self.board_palette.hide()
        self.shape_palette.hide()
        self.tool_palette.hide()
        self.size_palette.hide()

        if event.button() == Qt.MouseButton.LeftButton:
            target = self.childAt(event.position().toPoint())

            if target is self.logo_button:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.logo_button.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

            if isinstance(target, QPushButton) or isinstance(target, QSlider):
                self._drag_offset = None
                super().mousePressEvent(event)
                return

            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            if callable(self.on_moved):
                self.on_moved()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        self.logo_button.setCursor(Qt.CursorShape.OpenHandCursor)
        if callable(self.on_moved):
            self.on_moved()
        super().mouseReleaseEvent(event)

    def eventFilter(self, watched: QObject, event) -> bool:
        if watched in {
            self,
            self.logo_button,
            self.tools_button,
            self.shapes_button,
            self.board_button,
            self.move_button,
            self.eraser_button,
            self.mouse_button,
            self.size_button,
            self.color_button,
            self.undo_button,
            self.redo_button,
            self.clear_button,
            self.screenshot_button,
            self.quit_button,
        }:
            if event.type() == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.color_palette.hide()
                self.board_palette.hide()
                self.shape_palette.hide()
                self.tool_palette.hide()
                self.size_palette.hide()

                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self._drag_start_global = event.globalPosition().toPoint()
                self._drag_started = watched is self.logo_button
                if watched is self.logo_button:
                    self.logo_button.setCursor(Qt.CursorShape.ClosedHandCursor)
                return watched is self.logo_button

            if event.type() == event.Type.MouseMove and self._drag_offset is not None and (event.buttons() & Qt.MouseButton.LeftButton):
                current_global = event.globalPosition().toPoint()
                if not self._drag_started and self._drag_start_global is not None:
                    distance = (current_global - self._drag_start_global).manhattanLength()
                    if distance >= 8:
                        self._drag_started = True

                if self._drag_started:
                    self.move(current_global - self._drag_offset)
                    if callable(self.on_moved):
                        self.on_moved()
                    return True

            if event.type() == event.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                dragged = self._drag_started
                self._drag_offset = None
                self._drag_start_global = None
                self._drag_started = False
                self.logo_button.setCursor(Qt.CursorShape.OpenHandCursor)
                if callable(self.on_moved):
                    self.on_moved()
                return dragged

        return super().eventFilter(watched, event)

    def toggle_board_palette(self) -> None:
        self.color_palette.hide()
        self.shape_palette.hide()
        self.tool_palette.hide()
        self.size_palette.hide()

        if self.board_palette.isVisible():
            self.board_palette.hide()
            return

        self.position_board_palette()
        self.board_palette.show()
        self.board_palette.raise_()
        self.board_palette.activateWindow()

    def position_side_palette(self, button: QPushButton, palette: QWidget) -> None:
        button_pos = button.mapToGlobal(button.rect().center())
        palette.adjustSize()

        x = button_pos.x() + (button.width() // 2) + 10
        y = button_pos.y() - (palette.height() // 2)

        palette.move(x, y)

    def position_board_palette(self) -> None:
        self.position_side_palette(self.board_button, self.board_palette)

    def set_board_button_mode(self, mode: str) -> None:
        self.board_button.icon_name = "board"

        if mode == "white":
            self.board_button.setToolTip("Whiteboard")
            self.board_button.setStyleSheet(
                """
                QPushButton {
                    background: white;
                    border: 2px solid rgb(160, 160, 160);
                    border-radius: 10px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: rgb(230, 230, 230);
                }
                """
            )
            self.board_button.update_icon(stroke="black")
        elif mode == "black":
            self.board_button.setToolTip("Blackboard")
            self.board_button.setStyleSheet(
                """
                QPushButton {
                    background: rgb(20, 20, 20);
                    border: 2px solid rgb(120, 120, 120);
                    border-radius: 10px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: rgb(45, 45, 45);
                }
                """
            )
            self.board_button.update_icon(stroke="white")
        else:
            self.board_button.setToolTip("Board")
            self.board_button.apply_default_style()
            self.board_button.update_icon(stroke="white")


    def toggle_tool_palette(self) -> None:
        self.color_palette.hide()
        self.board_palette.hide()
        self.shape_palette.hide()
        self.size_palette.hide()

        if self.tool_palette.isVisible():
            self.tool_palette.hide()
            return

        self.position_tool_palette()
        self.tool_palette.show()
        self.tool_palette.raise_()
        self.tool_palette.activateWindow()

    def position_tool_palette(self) -> None:
        self.position_side_palette(self.tools_button, self.tool_palette)

    def set_tools_button_mode(self, mode: str) -> None:
        if mode == "pen":
            self.tools_button.icon_name = "pen"
            self.tools_button.setToolTip("Pen")
        elif mode == "highlighter":
            self.tools_button.icon_name = "highlighter"
            self.tools_button.setToolTip("Highlighter")
        elif mode == "text":
            self.tools_button.icon_name = "text"
            self.tools_button.setToolTip("Text")
        else:
            self.tools_button.icon_name = "pen"
            self.tools_button.setToolTip("Tools")

        self.tools_button.update_icon(stroke="white")

    def toggle_shape_palette(self) -> None:
        self.color_palette.hide()
        self.board_palette.hide()
        self.tool_palette.hide()
        self.size_palette.hide()

        if self.shape_palette.isVisible():
            self.shape_palette.hide()
            return

        self.position_shape_palette()
        self.shape_palette.show()
        self.shape_palette.raise_()
        self.shape_palette.activateWindow()

    def position_shape_palette(self) -> None:
        self.position_side_palette(self.shapes_button, self.shape_palette)

    def set_shapes_button_mode(self, mode: str) -> None:
        if mode == "line":
            self.shapes_button.icon_name = "line"
            self.shapes_button.setToolTip("Line")
        elif mode == "arrow":
            self.shapes_button.icon_name = "arrow"
            self.shapes_button.setToolTip("Arrow")
        elif mode == "rect":
            self.shapes_button.icon_name = "rect"
            self.shapes_button.setToolTip("Rect")
        elif mode == "circle":
            self.shapes_button.icon_name = "circle"
            self.shapes_button.setToolTip("Circle")
        elif mode == "triangle":
            self.shapes_button.icon_name = "triangle"
            self.shapes_button.setToolTip("Triangle")
        else:
            self.shapes_button.icon_name = "rect"
            self.shapes_button.setToolTip("Shapes")

        self.shapes_button.update_icon(stroke="white")

    def toggle_color_palette(self) -> None:
        self.board_palette.hide()
        self.shape_palette.hide()
        self.tool_palette.hide()
        self.size_palette.hide()

        if self.color_palette.isVisible():
            self.color_palette.hide()
            return

        self.position_color_palette()
        self.color_palette.show()
        self.color_palette.raise_()
        self.color_palette.activateWindow()

    def position_color_palette(self) -> None:
        self.position_side_palette(self.color_button, self.color_palette)

    def set_color_button_preview(self, color: QColor) -> None:
        self.color_button.setToolTip("Color")
        self.color_button.setStyleSheet(
            f"""
            QPushButton {{
                background: {color.name()};
                border: 2px solid white;
                border-radius: 8px;
                min-width: 38px;
                min-height: 36px;
                padding: 0;
            }}
            QPushButton:hover {{
                background: {color.name()};
                border: 2px solid white;
            }}
            """
        )

    def toggle_size_palette(self) -> None:
        if self.size_palette.isVisible():
            self.size_palette.hide()
            return

        self.position_size_palette()
        self.size_palette.show()
        self.size_palette.raise_()
        self.size_palette.activateWindow()

    def position_size_palette(self) -> None:
        button_pos = self.size_button.mapToGlobal(self.size_button.rect().center())
        self.size_palette.adjustSize()
        self.size_palette.move(button_pos.x() + 28, button_pos.y() - self.size_palette.height() // 2)

    def set_size_button_active(self, active: bool) -> None:
        self.size_button.set_active(active)


    def toggle_collapsed(self) -> None:
        self.is_collapsed = not self.is_collapsed

        self.color_palette.hide()
        self.board_palette.hide()
        self.shape_palette.hide()
        self.tool_palette.hide()
        self.size_palette.hide()

        for widget in self._collapsible_widgets:
            widget.setVisible(not self.is_collapsed)

        self.eye_button.setToolTip("Show Toolbar" if self.is_collapsed else "Hide Toolbar")
        self.eye_button.icon_name = "eye_off" if self.is_collapsed else "eye"

        if self.is_collapsed:
            self.eye_button.setStyleSheet(
                """
                QPushButton {
                    background: rgb(190, 55, 55);
                    border: 2px solid rgb(255, 255, 255);
                    border-radius: 10px;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: rgb(255, 23, 68);
                }
                """
            )
            self.eye_button.update_icon(stroke="white")
        else:
            self.eye_button.apply_default_style()
            self.eye_button.update_icon(stroke="white")

        if hasattr(self, "overlay"):
            self.overlay.set_visuals_hidden(self.is_collapsed)

        self.adjustSize()

        if callable(self.on_moved):
            self.on_moved()

class OverlayWindow(QWidget):
    state_changed = Signal()

    def __init__(self, toolbar: ToolbarWindow) -> None:
        super().__init__(None)

        self.toolbar = toolbar
        self.mode = "mouse"
        self.board_mode = "off"
        self.visuals_hidden = False

        self.pen_color = QColor("#ff0000")
        self.pen_width = 4
        self.pen_opacity = 1.0
        self.pen_min_width = 1
        self.pen_max_width = 48

        self.highlighter_color = QColor("#ffff00")
        self.highlighter_width = 18
        self.highlighter_opacity = 0.35
        self.highlighter_min_width = 6
        self.highlighter_max_width = 64

        self.text_color = QColor("#ffffff")
        self.text_font_size = 24
        self.text_min_size = 8
        self.text_max_size = 96

        self.eraser_width = 24
        self.eraser_min_width = 8
        self.eraser_max_width = 72

        self.items: list[CanvasItem] = []
        self.undo_stack: list[list[CanvasItem]] = []
        self.redo_stack: list[list[CanvasItem]] = []

        self.current_path: QPainterPath | None = None
        self.shape_start: QPointF | None = None
        self.shape_current: QPointF | None = None
        self.screenshot_start: QPointF | None = None
        self.screenshot_end: QPointF | None = None
        self.screenshot_selection_ready = False

        self.selected_item_index: int | None = None
        self.dragging_item = False
        self.drag_last_pos = QPointF()
        self.pending_item_move_history = False

        self.resizing_item = False
        self.resize_item_initial_path: QPainterPath | None = None
        self.resize_item_initial_rect: QRectF | None = None
        self.resize_item_anchor = QPointF()

        self.selected_text_index: int | None = None
        self.dragging_text = False
        self.resizing_text = False
        self.rotating_text = False
        self.drag_offset = QPointF()
        self.pending_history = False
        self.rotation_start_offset = 0.0

        self.text_editor = InlineTextEditor(self)
        self.text_editor.hide()
        self.text_editor.commit_requested.connect(self.commit_text_edit)
        self.text_editor.cancel_requested.connect(self.cancel_text_edit)
        self.text_editor.live_text_changed.connect(self.live_update_text_edit)
        self.editing_text_index: int | None = None

        self.setWindowTitle("clarivo Overlay")
        overlay_flags = (
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        if sys.platform.startswith("linux"):
            overlay_flags |= Qt.WindowType.X11BypassWindowManagerHint

        self.setWindowFlags(overlay_flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(
            Qt.WidgetAttribute.WA_NoSystemBackground,
            not sys.platform.startswith("win"),
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        screen = QGuiApplication.primaryScreen()
        geometry = screen.geometry() if screen is not None else QRect(0, 0, 1280, 720)
        self.setGeometry(geometry)

        self.pen_cursor = self.build_custom_cursor(
            PEN_CURSOR_PATH,
            hot_x=3,
            hot_y=0,
            size=45,
        )

        self.highlighter_cursor = self.build_custom_cursor(
            HIGHLIGHTER_CURSOR_PATH,
            hot_x=3,
            hot_y=0,
            size=52,
        )

        self.text_cursor = self.build_custom_cursor(
            TEXT_CURSOR_PATH,
            hot_x=11,
            hot_y=26,
            size=52,
        )

        self.move_cursor = self.build_custom_cursor(
            MOVE_CURSOR_PATH,
            hot_x=3,
            hot_y=7,
            size=50,
        )

        self.eraser_cursor = self.build_custom_cursor(
            ERASER_CURSOR_PATH,
            hot_x=3,
            hot_y=0,
            size=50,
        )

        self.screenshot_cursor = self.build_custom_cursor(
            SCREENSHOT_CURSOR_PATH,
            hot_x=6,
            hot_y=6,
            size=42,
        )

    def emit_state_changed(self) -> None:
        self.state_changed.emit()

    def build_custom_cursor(
        self,
        image_path: str,
        hot_x: int = 0,
        hot_y: int = 0,
        size: int = 45,
    ) -> QCursor:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return QCursor(Qt.CursorShape.CrossCursor)

        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QCursor(scaled, hot_x, hot_y)

    def clone_item(self, item: CanvasItem) -> CanvasItem:
        if isinstance(item, Stroke):
            return Stroke(QPainterPath(item.path), QColor(item.color), int(item.width), float(item.opacity))
        return TextItem(QRectF(item.rect), str(item.text), QColor(item.color), int(item.font_size), float(item.angle))

    def snapshot_items(self) -> list[CanvasItem]:
        return [self.clone_item(item) for item in self.items]

    def push_history(self) -> None:
        self.undo_stack.append(self.snapshot_items())
        self.redo_stack.clear()

    def restore_snapshot(self, snapshot: list[CanvasItem]) -> None:
        self.items = [self.clone_item(item) for item in snapshot]
        self.current_path = None
        self.shape_start = None
        self.shape_current = None
        self.selected_item_index = None
        self.selected_text_index = None
        self.hide_text_editor()
        self.dragging_text = False
        self.resizing_text = False
        self.rotating_text = False
        self.dragging_item = False
        self.resizing_item = False
        self.resize_item_initial_path = None
        self.resize_item_initial_rect = None
        self.pending_history = False
        self.pending_item_move_history = False
        self.update()
        self.emit_state_changed()

    def toolbar_rect_in_overlay(self) -> QRect:
        top_left = self.mapFromGlobal(self.toolbar.frameGeometry().topLeft())
        return QRect(top_left, self.toolbar.size())
    
    def apply_input_transparency(self) -> None:
        transparent = self.mode == "mouse"

        if sys.platform.startswith("win"):
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, transparent)
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, transparent)
        else:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, transparent)

        self.show()
        self.raise_()

    def sync_input_region(self) -> None:
        self.apply_input_transparency()

        if self.mode == "mouse":
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
            self.clearMask()
            self.show()
            self.raise_()
            return

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)

        full_region = QRegion(self.rect())
        toolbar_region = QRegion(self.toolbar_rect_in_overlay())
        self.setMask(full_region.subtracted(toolbar_region))

        self.show()
        self.raise_()


    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.current_path = None
        self.shape_start = None
        self.shape_current = None
        self.screenshot_start = None
        self.screenshot_end = None
        self.screenshot_selection_ready = False
        self.dragging_text = False
        self.resizing_text = False
        self.rotating_text = False
        self.dragging_item = False
        self.resizing_item = False
        self.resize_item_initial_path = None
        self.resize_item_initial_rect = None
        self.pending_history = False
        self.pending_item_move_history = False

        if mode != "text":
            self.selected_text_index = None
            self.hide_text_editor()

        if mode != "move":
            self.selected_item_index = None

        if mode in {"mouse"}:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode == "pen":
            self.setCursor(self.pen_cursor)
        elif mode == "highlighter":
            self.setCursor(self.highlighter_cursor)
        elif mode == "text":
            self.setCursor(self.text_cursor)
        elif mode == "move":
            self.setCursor(self.move_cursor)
        elif mode == "eraser":
            self.setCursor(self.eraser_cursor)
        elif mode == "screenshot":
            self.setCursor(self.screenshot_cursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

        self.sync_input_region()

        if mode != "mouse":
            self.activateWindow()
            self.setFocus()

        self.update()
        self.emit_state_changed()

    def set_pen_mode(self) -> None:
        self.set_mode("pen")

    def set_highlighter_mode(self) -> None:
        self.set_mode("highlighter")

    def set_eraser_mode(self) -> None:
        self.set_mode("eraser")

    def set_line_mode(self) -> None:
        self.set_mode("line")

    def set_arrow_mode(self) -> None:
        self.set_mode("arrow")

    def set_rect_mode(self) -> None:
        self.set_mode("rect")

    def set_circle_mode(self) -> None:
        self.set_mode("circle")

    def set_triangle_mode(self) -> None:
        self.set_mode("triangle")

    def set_text_mode(self) -> None:
        self.set_mode("text")

    def set_move_mode(self) -> None:
        self.set_mode("move")

    def set_mouse_mode(self) -> None:
        self.set_mode("mouse")

    def cycle_board_mode(self) -> None:
        if self.board_mode == "off":
            self.board_mode = "white"
        elif self.board_mode == "white":
            self.board_mode = "black"
        else:
            self.board_mode = "off"
        self.update()
        self.emit_state_changed()

    def set_board_mode(self, mode: str) -> None:
        if mode not in {"off", "white", "black"}:
            mode = "off"
        self.board_mode = mode
        self.update()
        self.emit_state_changed()

    def current_board_color(self) -> QColor | None:
        if self.board_mode == "white":
            return QColor("#ffffff")
        if self.board_mode == "black":
            return QColor("#111111")
        return None
    
    def set_screenshot_mode(self) -> None:
        self.set_mode("screenshot")

    def set_visuals_hidden(self, hidden: bool) -> None:
        self.visuals_hidden = hidden
        self.update()
        self.emit_state_changed()

    def shutdown_overlay(self) -> None:
        self.mode = "mouse"
        self.current_path = None
        self.shape_start = None
        self.shape_current = None
        self.screenshot_start = None
        self.screenshot_end = None
        self.dragging_text = False
        self.resizing_text = False
        self.rotating_text = False
        self.dragging_item = False
        self.resizing_item = False
        self.pending_history = False
        self.pending_item_move_history = False
        self.selected_item_index = None
        self.selected_text_index = None

        self.hide_text_editor()
        self.clearMask()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
        self.hide()
        self.close()

    def get_selected_item(self) -> CanvasItem | None:
        if self.selected_item_index is None:
            return None
        if self.selected_item_index < 0 or self.selected_item_index >= len(self.items):
            self.selected_item_index = None
            return None
        return self.items[self.selected_item_index]

    def clear_selection(self) -> None:
        self.selected_item_index = None
        if self.mode != "text":
            self.selected_text_index = None
        self.dragging_item = False
        self.pending_item_move_history = False
        self.update()
        self.emit_state_changed()

    def set_current_tool_color(self, color: QColor) -> None:
        if self.mode == "highlighter":
            self.highlighter_color = QColor(color)
        elif self.mode == "text":
            self.text_color = QColor(color)
            selected = self.get_selected_text_item()
            if selected is not None:
                self.push_history()
                selected.color = QColor(color)
                self.update_text_editor_style()
        else:
            self.pen_color = QColor(color)

        self.update()
        self.emit_state_changed()

    def current_tool_color(self) -> QColor:
        if self.mode == "highlighter":
            return QColor(self.highlighter_color)
        if self.mode == "text":
            selected = self.get_selected_text_item()
            if selected is not None:
                return QColor(selected.color)
            return QColor(self.text_color)
        return QColor(self.pen_color)

    def current_tool_width(self) -> int:
        if self.mode == "highlighter":
            return self.highlighter_width
        if self.mode == "eraser":
            return self.eraser_width
        if self.mode == "text":
            selected = self.get_selected_text_item()
            if selected is not None:
                return selected.font_size
            return self.text_font_size
        return self.pen_width

    def current_tool_width_range(self) -> tuple[int, int]:
        if self.mode == "highlighter":
            return self.highlighter_min_width, self.highlighter_max_width
        if self.mode == "eraser":
            return self.eraser_min_width, self.eraser_max_width
        if self.mode == "text":
            return self.text_min_size, self.text_max_size
        return self.pen_min_width, self.pen_max_width

    def set_current_tool_width(self, value: int) -> None:
        min_width, max_width = self.current_tool_width_range()
        clamped_value = max(min_width, min(value, max_width))

        if self.mode == "highlighter":
            self.highlighter_width = clamped_value
        elif self.mode == "eraser":
            self.eraser_width = clamped_value
        elif self.mode == "text":
            self.text_font_size = clamped_value
            selected = self.get_selected_text_item()
            if selected is not None:
                selected.font_size = clamped_value
                self.update_text_editor_geometry()
                self.update_text_editor_style()
        else:
            self.pen_width = clamped_value

        self.update()
        self.emit_state_changed()

    def clear_canvas(self) -> None:
        if not self.items:
            return
        self.push_history()
        self.items.clear()
        self.current_path = None
        self.shape_start = None
        self.shape_current = None
        self.selected_item_index = None
        self.selected_text_index = None
        self.hide_text_editor()
        self.update()
        self.emit_state_changed()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        self.redo_stack.append(self.snapshot_items())
        self.restore_snapshot(self.undo_stack.pop())

    def redo(self) -> None:
        if not self.redo_stack:
            return
        self.undo_stack.append(self.snapshot_items())
        self.restore_snapshot(self.redo_stack.pop())

    def current_stroke_style(self) -> tuple[QColor, int, float]:
        if self.mode == "highlighter":
            return QColor(self.highlighter_color), self.highlighter_width, self.highlighter_opacity
        return QColor(self.pen_color), self.pen_width, self.pen_opacity

    def stroke_hit_path(self, stroke: Stroke, extra_width: int = 0) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        stroker.setWidth(max(1.0, float(stroke.width + extra_width)))
        return stroker.createStroke(stroke.path)

    def rotate_point(self, point: QPointF, center: QPointF, angle_deg: float) -> QPointF:
        radians = math.radians(angle_deg)
        dx = point.x() - center.x()
        dy = point.y() - center.y()
        cos_a = math.cos(radians)
        sin_a = math.sin(radians)
        return QPointF(
            center.x() + dx * cos_a - dy * sin_a,
            center.y() + dx * sin_a + dy * cos_a,
        )

    def text_local_point(self, item: TextItem, scene_point: QPointF) -> QPointF:
        return self.rotate_point(scene_point, item.rect.center(), -item.angle)

    def text_contains_point(self, item: TextItem, pos: QPointF) -> bool:
        return item.rect.contains(self.text_local_point(item, pos))

    def item_contains_point(self, item: CanvasItem, pos: QPointF) -> bool:
        if isinstance(item, TextItem):
            return self.text_contains_point(item, pos)
        hit_path = self.stroke_hit_path(item, max(10, item.width + 6))
        return hit_path.contains(pos)

    def find_item_at(self, pos: QPointF) -> int | None:
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if self.item_contains_point(item, pos):
                return index
        return None

    def move_item_by(self, item: CanvasItem, delta: QPointF) -> None:
        if isinstance(item, TextItem):
            item.rect.translate(delta)
            return
        transform = QTransform()
        transform.translate(delta.x(), delta.y())
        item.path = transform.map(item.path)

    def selected_stroke_bounds(self, stroke: Stroke) -> QRectF:
        return self.stroke_hit_path(stroke, 6).boundingRect()

    def draw_selected_stroke_bounds(self, painter: QPainter, stroke: Stroke) -> None:
        rect = self.selected_stroke_bounds(stroke)
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        handle = self.stroke_resize_handle_rect(stroke)
        painter.setPen(QPen(QColor(20, 20, 20), 1))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRect(handle)

    def stroke_resize_handle_rect(self, stroke: Stroke) -> QRectF:
        rect = self.selected_stroke_bounds(stroke)
        size = 12.0
        return QRectF(rect.right() - size, rect.bottom() - size, size, size)

    def find_stroke_resize_handle_at(self, pos: QPointF) -> int | None:
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if isinstance(item, Stroke):
                if self.stroke_resize_handle_rect(item).contains(pos):
                    return index
        return None

    def scale_stroke_from_rect(self, stroke: Stroke, target_pos: QPointF) -> None:
        if self.resize_item_initial_path is None or self.resize_item_initial_rect is None:
            return

        initial_rect = QRectF(self.resize_item_initial_rect)
        anchor = QPointF(self.resize_item_anchor)

        min_size = 20.0
        new_width = max(min_size, target_pos.x() - anchor.x())
        new_height = max(min_size, target_pos.y() - anchor.y())

        if initial_rect.width() <= 0.1 or initial_rect.height() <= 0.1:
            return

        scale_x = new_width / initial_rect.width()
        scale_y = new_height / initial_rect.height()

        transform = QTransform()
        transform.translate(anchor.x(), anchor.y())
        transform.scale(scale_x, scale_y)
        transform.translate(-anchor.x(), -anchor.y())

        stroke.path = transform.map(QPainterPath(self.resize_item_initial_path))

    def text_resize_handle_center(self, item: TextItem) -> QPointF:
        return self.rotate_point(item.rect.bottomRight(), item.rect.center(), item.angle)

    def text_rotate_handle_center(self, item: TextItem) -> QPointF:
        local = QPointF(item.rect.center().x(), item.rect.top() - 22.0)
        return self.rotate_point(local, item.rect.center(), item.angle)

    def text_move_handle_center(self, item: TextItem) -> QPointF:
        return self.rotate_point(item.rect.center(), item.rect.center(), item.angle)

    def find_text_item_at(self, pos: QPointF) -> int | None:
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if isinstance(item, TextItem) and self.text_contains_point(item, pos):
                return index
        return None

    def find_text_resize_handle_at(self, pos: QPointF) -> int | None:
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if isinstance(item, TextItem):
                center = self.text_resize_handle_center(item)
                if math.hypot(pos.x() - center.x(), pos.y() - center.y()) <= 10.0:
                    return index
        return None

    def find_text_rotate_handle_at(self, pos: QPointF) -> int | None:
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if isinstance(item, TextItem):
                center = self.text_rotate_handle_center(item)
                if math.hypot(pos.x() - center.x(), pos.y() - center.y()) <= 10.0:
                    return index
        return None

    def find_text_move_handle_at(self, pos: QPointF) -> int | None:
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if isinstance(item, TextItem):
                center = self.text_move_handle_center(item)
                if math.hypot(pos.x() - center.x(), pos.y() - center.y()) <= 10.0:
                    return index
        return None

    def get_selected_text_item(self) -> TextItem | None:
        if self.selected_text_index is None:
            return None
        if self.selected_text_index < 0 or self.selected_text_index >= len(self.items):
            self.selected_text_index = None
            return None
        item = self.items[self.selected_text_index]
        if not isinstance(item, TextItem):
            self.selected_text_index = None
            return None
        return item

    def erase_at(self, pos: QPointF) -> None:
        for index in range(len(self.items) - 1, -1, -1):
            item = self.items[index]
            if isinstance(item, TextItem):
                if self.text_contains_point(item, pos):
                    self.push_history()
                    self.items.pop(index)
                    if self.selected_item_index == index:
                        self.selected_item_index = None
                    self.selected_text_index = None
                    self.hide_text_editor()
                    self.update()
                    self.emit_state_changed()
                    return
            else:
                hit_path = self.stroke_hit_path(item, self.eraser_width)
                if hit_path.contains(pos):
                    self.push_history()
                    self.items.pop(index)
                    if self.selected_item_index == index:
                        self.selected_item_index = None
                    self.update()
                    self.emit_state_changed()
                    return

    def normalized_rect(self, start: QPointF, end: QPointF) -> QRectF:
        return QRectF(start, end).normalized()

    def build_line_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end)
        return path

    def build_rect_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.normalized_rect(start, end))
        return path

    def build_circle_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(self.normalized_rect(start, end))
        return path

    def build_triangle_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        rect = self.normalized_rect(start, end)
        top = QPointF(rect.center().x(), rect.top())
        left = QPointF(rect.left(), rect.bottom())
        right = QPointF(rect.right(), rect.bottom())

        polygon = QPolygonF([top, right, left, top])
        path = QPainterPath()
        path.addPolygon(polygon)
        path.closeSubpath()
        return path

    def build_arrow_path(self, start: QPointF, end: QPointF, width: int) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end)

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length < 1.0:
            return path

        ux = dx / length
        uy = dy / length

        head_length = max(14.0, width * 4.0)
        head_width = max(10.0, width * 2.5)

        base_x = end.x() - ux * head_length
        base_y = end.y() - uy * head_length

        perp_x = -uy
        perp_y = ux

        left = QPointF(base_x + perp_x * head_width / 2.0, base_y + perp_y * head_width / 2.0)
        right = QPointF(base_x - perp_x * head_width / 2.0, base_y - perp_y * head_width / 2.0)

        path.moveTo(end)
        path.lineTo(left)
        path.moveTo(end)
        path.lineTo(right)
        return path

    def build_shape_path(self, mode: str, start: QPointF, end: QPointF) -> QPainterPath:
        if mode == "line":
            return self.build_line_path(start, end)
        if mode == "arrow":
            return self.build_arrow_path(start, end, self.pen_width)
        if mode == "rect":
            return self.build_rect_path(start, end)
        if mode == "circle":
            return self.build_circle_path(start, end)
        if mode == "triangle":
            return self.build_triangle_path(start, end)
        return QPainterPath()

    def preview_path(self) -> QPainterPath | None:
        if self.mode in {"pen", "highlighter"}:
            return self.current_path
        if self.mode in {"line", "arrow", "rect", "circle", "triangle"}:
            if self.shape_start is None or self.shape_current is None:
                return None
            return self.build_shape_path(self.mode, self.shape_start, self.shape_current)
        return None
    
    def render_items_to_pixmap(self, rect: QRect) -> QPixmap:
        pixmap = QPixmap(rect.size())
        board_color = self.current_board_color()

        if board_color is not None:
            pixmap.fill(board_color)
        else:
            pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(-rect.topLeft())

        for index, item in enumerate(self.items):
            if isinstance(item, Stroke):
                self.draw_stroke(painter, item)
            else:
                self.draw_text_item(painter, item, selected=False)

        painter.end()
        return pixmap

    def create_text_item(self, pos: QPointF) -> None:
        self.push_history()
        rect = QRectF(pos.x(), pos.y(), 220.0, 90.0)
        item = TextItem(rect=rect, text="Text", color=QColor(self.text_color), font_size=self.text_font_size, angle=0.0)
        self.items.append(item)
        self.selected_item_index = len(self.items) - 1
        self.selected_text_index = len(self.items) - 1
        self.start_text_edit(self.selected_text_index)
        self.emit_state_changed()

    def start_text_edit(self, index: int) -> None:
        if index < 0 or index >= len(self.items):
            return

        item = self.items[index]
        if not isinstance(item, TextItem):
            return

        self.selected_item_index = index
        self.selected_text_index = index
        self.editing_text_index = index

        self.text_editor.blockSignals(True)
        self.text_editor.setPlainText(item.text)
        self.text_editor.blockSignals(False)

        self.update_text_editor_style()
        self.update_text_editor_geometry()

        self.text_editor._ignore_next_focus_out = True
        self.text_editor.show()
        self.text_editor.raise_()

        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

        def _focus_editor() -> None:
            if self.editing_text_index != index:
                return
            self.text_editor.raise_()
            self.text_editor.activateWindow()
            self.text_editor.setFocus(Qt.FocusReason.OtherFocusReason)
            cursor = self.text_editor.textCursor()
            cursor.select(cursor.SelectionType.Document)
            self.text_editor.setTextCursor(cursor)

        QTimer.singleShot(0, _focus_editor)
        self.emit_state_changed()

    def update_text_editor_style(self) -> None:
        item = self.get_selected_text_item()
        color = self.text_color if item is None else item.color
        font_size = self.text_font_size if item is None else item.font_size
        font = QFont()
        font.setPointSize(font_size)
        self.text_editor.setFont(font)
        self.text_editor.setTextColor(QColor(color))
        self.text_editor.setStyleSheet(
            f"""
            QTextEdit {{
                background: rgba(30, 30, 30, 200);
                color: {QColor(color).name()};
                border: 1px dashed rgba(255, 255, 255, 180);
                border-radius: 4px;
                padding: 4px;
            }}
            """
        )

    def update_text_editor_geometry(self) -> None:
        item = self.get_selected_text_item()
        if item is None or self.editing_text_index is None:
            return
        self.text_editor.setGeometry(item.rect.toRect().adjusted(6, 6, -18, -18))

    def live_update_text_edit(self) -> None:
        if self.editing_text_index is None:
            return
        if self.editing_text_index < 0 or self.editing_text_index >= len(self.items):
            return

        item = self.items[self.editing_text_index]
        if not isinstance(item, TextItem):
            return

        item.text = self.text_editor.toPlainText() or "Text"
        self.update()
        self.emit_state_changed()

    def commit_text_edit(self) -> None:
        if self.editing_text_index is None:
            return
        if self.editing_text_index < 0 or self.editing_text_index >= len(self.items):
            self.hide_text_editor()
            return

        item = self.items[self.editing_text_index]
        if not isinstance(item, TextItem):
            self.hide_text_editor()
            return

        item.text = self.text_editor.toPlainText() or "Text"
        self.hide_text_editor()
        self.update()
        self.emit_state_changed()

    def cancel_text_edit(self) -> None:
        self.hide_text_editor()
        self.update()

    def hide_text_editor(self) -> None:
        self.text_editor.hide()
        self.editing_text_index = None

    def delete_selected_text(self) -> None:
        if self.selected_text_index is None:
            return
        if self.selected_text_index < 0 or self.selected_text_index >= len(self.items):
            self.selected_text_index = None
            return
        if not isinstance(self.items[self.selected_text_index], TextItem):
            self.selected_text_index = None
            return

        self.push_history()
        self.items.pop(self.selected_text_index)
        self.selected_item_index = None
        self.selected_text_index = None
        self.hide_text_editor()
        self.update()
        self.emit_state_changed()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self.mode != "text":
            super().mouseDoubleClickEvent(event)
            return

        hit_index = self.find_text_item_at(event.position())
        if hit_index is not None:
            self.start_text_edit(hit_index)
            event.accept()
            return

        super().mouseDoubleClickEvent(event)
        
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.mode == "screenshot":
            if event.button() != Qt.MouseButton.LeftButton:
                event.ignore()
                return

            self.screenshot_start = event.position()
            self.screenshot_end = event.position()
            self.screenshot_selection_ready = False
            self.update()
            return
        if self.mode == "move":
            if event.button() != Qt.MouseButton.LeftButton:
                event.ignore()
                return

            resize_index = self.find_stroke_resize_handle_at(event.position())
            if resize_index is not None:
                self.selected_item_index = resize_index
                self.selected_text_index = None
                item = self.get_selected_item()
                if isinstance(item, Stroke):
                    self.resizing_item = True
                    self.dragging_item = False
                    self.dragging_text = False
                    self.pending_item_move_history = False
                    self.resize_item_initial_path = QPainterPath(item.path)
                    self.resize_item_initial_rect = self.selected_stroke_bounds(item)
                    self.resize_item_anchor = QPointF(
                        self.resize_item_initial_rect.left(),
                        self.resize_item_initial_rect.top(),
                    )
                    self.update()
                    self.emit_state_changed()
                return

            hit_index = self.find_item_at(event.position())
            if hit_index is None:
                self.clear_selection()
                return

            self.selected_item_index = hit_index
            item = self.get_selected_item()
            if item is None:
                self.clear_selection()
                return

            self.pending_item_move_history = False
            self.pending_history = False
            self.resizing_item = False
            self.resizing_text = False
            self.rotating_text = False

            if isinstance(item, TextItem):
                self.selected_text_index = hit_index
                self.dragging_text = True
                self.dragging_item = False
                local_point = self.text_local_point(item, event.position())
                self.drag_offset = local_point - item.rect.topLeft()
            else:
                self.selected_text_index = None
                self.dragging_item = True
                self.dragging_text = False
                self.drag_last_pos = event.position()

            self.update()
            self.emit_state_changed()
            return

        if self.mode == "eraser":
            if event.button() != Qt.MouseButton.LeftButton:
                event.ignore()
                return
            self.erase_at(event.position())
            return
        
        if self.mode == "screenshot":
            if event.button() != Qt.MouseButton.LeftButton:
                return

            if self.screenshot_start is None:
                return

            self.screenshot_end = event.position()
            self.screenshot_selection_ready = True
            self.update()
            self.emit_state_changed()
            return
        
        if self.mode == "screenshot":
            if event.button() != Qt.MouseButton.LeftButton:
                event.ignore()
                return

            self.screenshot_start = event.position()
            self.screenshot_end = event.position()
            self.screenshot_selection_ready = False
            self.update()
            return

        if self.mode in {"pen", "highlighter"}:
            if event.button() != Qt.MouseButton.LeftButton:
                event.ignore()
                return
            path = QPainterPath()
            path.moveTo(event.position())
            self.current_path = path
            self.update()
            return

        if self.mode in {"line", "arrow", "rect", "circle", "triangle"}:
            if event.button() != Qt.MouseButton.LeftButton:
                event.ignore()
                return
            self.shape_start = event.position()
            self.shape_current = event.position()
            self.update()
            return

        if self.mode == "text":
            if event.button() != Qt.MouseButton.LeftButton:
                event.ignore()
                return

            if self.text_editor.isVisible() and not self.text_editor.geometry().contains(event.position().toPoint()):
                self.commit_text_edit()

            rotate_index = self.find_text_rotate_handle_at(event.position())
            if rotate_index is not None:
                self.selected_item_index = rotate_index
                self.selected_text_index = rotate_index
                item = self.get_selected_text_item()
                if item is not None:
                    self.rotating_text = True
                    self.dragging_text = False
                    self.resizing_text = False
                    center = item.rect.center()
                    self.rotation_start_offset = math.degrees(
                        math.atan2(event.position().y() - center.y(), event.position().x() - center.x())
                    ) - item.angle
                    self.pending_history = False
                    self.update()
                    self.emit_state_changed()
                return

            move_index = self.find_text_move_handle_at(event.position())
            if move_index is not None:
                self.selected_item_index = move_index
                self.selected_text_index = move_index
                selected = self.get_selected_text_item()
                if selected is not None:
                    self.dragging_text = True
                    self.resizing_text = False
                    self.rotating_text = False
                    local_point = self.text_local_point(selected, event.position())
                    self.drag_offset = local_point - selected.rect.topLeft()
                    self.pending_history = False
                    self.update()
                    self.emit_state_changed()
                return

            resize_index = self.find_text_resize_handle_at(event.position())
            if resize_index is not None:
                self.selected_item_index = resize_index
                self.selected_text_index = resize_index
                self.resizing_text = True
                self.dragging_text = False
                self.rotating_text = False
                self.pending_history = False
                self.update()
                self.emit_state_changed()
                return

            text_index = self.find_text_item_at(event.position())
            if text_index is not None:
                self.selected_item_index = text_index
                self.selected_text_index = text_index
                selected = self.get_selected_text_item()
                if selected is not None:
                    self.dragging_text = True
                    self.resizing_text = False
                    self.rotating_text = False
                    local_point = self.text_local_point(selected, event.position())
                    self.drag_offset = local_point - selected.rect.topLeft()
                    self.pending_history = False
                    self.update()
                    self.emit_state_changed()
                return

            self.selected_item_index = None
            self.selected_text_index = None
            self.dragging_text = False
            self.resizing_text = False
            self.rotating_text = False
            self.create_text_item(event.position())
            self.update()
            return

        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.mode == "screenshot":
            if self.screenshot_start is None:
                return
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return

            self.screenshot_end = event.position()
            self.update()
            return

        if self.mode == "move":
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return

            item = self.get_selected_item()
            if item is None:
                self.dragging_item = False
                self.dragging_text = False
                self.resizing_item = False
                return

            if isinstance(item, TextItem):
                if not self.dragging_text:
                    return

                if not self.pending_history:
                    self.push_history()
                    self.pending_history = True

                local_point = self.text_local_point(item, event.position())
                item.rect.moveTopLeft(local_point - self.drag_offset)
                self.update()
                self.emit_state_changed()
                return

            if self.resizing_item:
                if not self.pending_item_move_history:
                    self.push_history()
                    self.pending_item_move_history = True

                if isinstance(item, Stroke):
                    self.scale_stroke_from_rect(item, event.position())
                    self.update()
                    self.emit_state_changed()
                return

            if not self.dragging_item:
                return

            if not self.pending_item_move_history:
                self.push_history()
                self.pending_item_move_history = True

            delta = event.position() - self.drag_last_pos
            self.move_item_by(item, delta)
            self.drag_last_pos = event.position()

            self.update()
            self.emit_state_changed()
            return

        if self.mode == "eraser":
            if event.buttons() & Qt.MouseButton.LeftButton:
                self.erase_at(event.position())
            return

        if self.mode in {"pen", "highlighter"}:
            if self.current_path is None:
                return
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return
            self.current_path.lineTo(event.position())
            self.update()
            return

        if self.mode in {"line", "arrow", "rect", "circle", "triangle"}:
            if self.shape_start is None:
                return
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return
            self.shape_current = event.position()
            self.update()
            return

        if self.mode == "text":
            selected = self.get_selected_text_item()
            if selected is None:
                return
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return

            if self.dragging_text:
                if not self.pending_history:
                    self.push_history()
                    self.pending_history = True
                local_point = self.text_local_point(selected, event.position())
                selected.rect.moveTopLeft(local_point - self.drag_offset)
                self.update_text_editor_geometry()
                self.update()
                self.emit_state_changed()
                return

            if self.resizing_text:
                if not self.pending_history:
                    self.push_history()
                    self.pending_history = True
                local_point = self.text_local_point(selected, event.position())
                selected.rect.setWidth(max(60.0, local_point.x() - selected.rect.left()))
                selected.rect.setHeight(max(40.0, local_point.y() - selected.rect.top()))
                self.update_text_editor_geometry()
                self.update()
                self.emit_state_changed()
                return

            if self.rotating_text:
                if not self.pending_history:
                    self.push_history()
                    self.pending_history = True
                center = selected.rect.center()
                current_angle = math.degrees(
                    math.atan2(event.position().y() - center.y(), event.position().x() - center.x())
                )
                selected.angle = current_angle - self.rotation_start_offset
                self.update()
                self.emit_state_changed()
                return

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.mode == "screenshot":
            if event.button() != Qt.MouseButton.LeftButton:
                return

            if self.screenshot_start is None:
                return

            self.screenshot_end = event.position()
            self.screenshot_selection_ready = True
            self.update()
            self.emit_state_changed()
            return

        if self.mode == "move":
            self.dragging_item = False
            self.dragging_text = False
            self.resizing_item = False
            self.resizing_text = False
            self.rotating_text = False
            self.pending_item_move_history = False
            self.pending_history = False
            self.resize_item_initial_path = None
            self.resize_item_initial_rect = None
            self.update()
            return

        if self.mode == "eraser":
            return
        

        if self.mode in {"pen", "highlighter"}:
            if event.button() != Qt.MouseButton.LeftButton or self.current_path is None:
                return

            color, width, opacity = self.current_stroke_style()
            self.push_history()
            self.items.append(
                Stroke(
                    path=self.current_path,
                    color=color,
                    width=width,
                    opacity=opacity,
                )
            )
            self.current_path = None
            self.update()
            self.emit_state_changed()
            return

        if self.mode in {"line", "arrow", "rect", "circle", "triangle"}:
            if event.button() != Qt.MouseButton.LeftButton:
                return
            if self.shape_start is None or self.shape_current is None:
                return

            self.shape_current = event.position()
            shape_path = self.build_shape_path(self.mode, self.shape_start, self.shape_current)
            if not shape_path.isEmpty():
                self.push_history()
                self.items.append(
                    Stroke(
                        path=shape_path,
                        color=QColor(self.pen_color),
                        width=self.pen_width,
                        opacity=self.pen_opacity,
                    )
                )

            self.shape_start = None
            self.shape_current = None
            self.update()
            self.emit_state_changed()
            return

        if self.mode == "text":
            self.dragging_text = False
            self.resizing_text = False
            self.rotating_text = False
            self.pending_history = False
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            event.accept()
            return

        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo()
            event.accept()
            return

        if event.key() == Qt.Key.Key_Delete and self.mode == "text":
            self.delete_selected_text()
            event.accept()
            return

        if event.key() == Qt.Key.Key_Escape:
            self.set_mouse_mode()
            event.accept()
            return

        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.sync_input_region()
        self.update_text_editor_geometry()

    def draw_stroke(self, painter: QPainter, stroke: Stroke) -> None:
        color = QColor(stroke.color)
        color.setAlphaF(stroke.opacity)
        painter.setPen(
            QPen(
                color,
                stroke.width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawPath(stroke.path)

    def draw_text_item(self, painter: QPainter, item: TextItem, selected: bool) -> None:
        center = item.rect.center()

        painter.save()
        painter.translate(center)
        painter.rotate(item.angle)
        painter.translate(-center)

        font = QFont()
        font.setPointSize(item.font_size)
        painter.setFont(font)
        painter.setPen(QPen(item.color))
        painter.drawText(
            item.rect.adjusted(4, 4, -4, -4),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            item.text,
        )
        painter.restore()

        if selected:
            top_left = self.rotate_point(item.rect.topLeft(), center, item.angle)
            top_right = self.rotate_point(item.rect.topRight(), center, item.angle)
            bottom_right = self.rotate_point(item.rect.bottomRight(), center, item.angle)
            bottom_left = self.rotate_point(item.rect.bottomLeft(), center, item.angle)

            painter.setPen(QPen(QColor(255, 255, 255, 220), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(QPolygonF([top_left, top_right, bottom_right, bottom_left]))

            resize_center = self.text_resize_handle_center(item)
            rotate_center = self.text_rotate_handle_center(item)
            move_center = self.text_move_handle_center(item)

            painter.setPen(QPen(QColor(20, 20, 20), 1))
            painter.setBrush(QColor(255, 255, 255, 235))
            painter.drawEllipse(resize_center, 7, 7)
            painter.drawEllipse(rotate_center, 7, 7)

            painter.setBrush(QColor(0, 170, 255, 235))
            painter.drawEllipse(move_center, 7, 7)

            painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
            painter.drawLine(
                self.rotate_point(QPointF(item.rect.center().x(), item.rect.top()), center, item.angle),
                rotate_center,
            )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if sys.platform.startswith("win"):
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            if self.mode != "mouse" and self.board_mode == "off":
                painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

        if self.visuals_hidden:
            return

        board_color = self.current_board_color()
        if board_color is not None:
            painter.fillRect(self.rect(), board_color)

        if self.mode == "screenshot" and self.screenshot_start is not None and self.screenshot_end is not None:
            rect = QRectF(self.screenshot_start, self.screenshot_end).normalized()

            painter.fillRect(self.rect(), QColor(0, 0, 0, 90))

            if board_color is not None:
                painter.fillRect(rect, board_color)
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                painter.fillRect(rect, Qt.GlobalColor.transparent)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            painter.setPen(QPen(QColor(255, 255, 255, 220), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

        for index, item in enumerate(self.items):
            is_selected = self.selected_item_index == index

            if isinstance(item, Stroke):
                self.draw_stroke(painter, item)
                if is_selected and self.mode == "move":
                    self.draw_selected_stroke_bounds(painter, item)
            else:
                selected = is_selected and self.mode in {"text", "move"}
                self.draw_text_item(painter, item, selected)

        preview = self.preview_path()
        if preview is not None and not preview.isEmpty():
            if self.mode == "highlighter":
                color = QColor(self.highlighter_color)
                width = self.highlighter_width
                opacity = self.highlighter_opacity
            else:
                color = QColor(self.pen_color)
                width = self.pen_width
                opacity = self.pen_opacity

            self.draw_stroke(
                painter,
                Stroke(
                    path=preview,
                    color=color,
                    width=width,
                    opacity=opacity,
                ),
            )

class ScreenPenApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.settings = QSettings(getpass.getuser(), "clarivo")

        self.toolbar = ToolbarWindow()
        self.overlay = OverlayWindow(self.toolbar)
        self.toolbar.overlay = self.overlay

        self.toolbar.on_moved = self.on_toolbar_moved

        self.overlay.state_changed.connect(self.sync_toolbar_state)
        self.overlay.state_changed.connect(self.maybe_finish_screenshot)
        self.toolbar.board_palette.board_selected.connect(self.set_board_mode)
        self.toolbar.shape_palette.shape_selected.connect(self.set_shape_mode)
        self.toolbar.tool_palette.tool_selected.connect(self.set_tool_mode)
        self.app.aboutToQuit.connect(self.cleanup_before_quit)

        self.toolbar.pen_button.clicked.connect(self.activate_pen_mode)
        self.toolbar.highlighter_button.clicked.connect(self.activate_highlighter_mode)
        self.toolbar.line_button.clicked.connect(self.activate_line_mode)
        self.toolbar.arrow_button.clicked.connect(self.activate_arrow_mode)
        self.toolbar.rect_button.clicked.connect(self.activate_rect_mode)
        self.toolbar.circle_button.clicked.connect(self.activate_circle_mode)
        self.toolbar.triangle_button.clicked.connect(self.activate_triangle_mode)
        self.toolbar.text_button.clicked.connect(self.activate_text_mode)
        self.toolbar.move_button.clicked.connect(self.activate_move_mode)
        self.toolbar.eraser_button.clicked.connect(self.activate_eraser_mode)
        self.toolbar.mouse_button.clicked.connect(self.activate_mouse_mode)
        self.toolbar.size_slider.valueChanged.connect(self.apply_slider_size)
        self.toolbar.undo_button.clicked.connect(self.overlay.undo)
        self.toolbar.redo_button.clicked.connect(self.overlay.redo)
        self.toolbar.clear_button.clicked.connect(self.overlay.clear_canvas)
        self.toolbar.screenshot_button.clicked.connect(self.activate_screenshot_mode)
        self.toolbar.quit_button.clicked.connect(self.quit_app)

        for color_button in self.toolbar.color_buttons:
            color_button.clicked.connect(
                lambda checked=False, c=color_button.color_value: self.apply_selected_color(c)
            )

        self.toolbar_undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self.toolbar)
        self.toolbar_undo_shortcut.activated.connect(self.overlay.undo)

        self.toolbar_redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self.toolbar)
        self.toolbar_redo_shortcut.activated.connect(self.overlay.redo)

        self.overlay_undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self.overlay)
        self.overlay_undo_shortcut.activated.connect(self.overlay.undo)

        self.overlay_redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self.overlay)
        self.overlay_redo_shortcut.activated.connect(self.overlay.redo)

        self.pending_screenshot_pixmap: QPixmap | None = None
        self.pending_screenshot_rect: QRect | None = None
        self.screenshot_actions = ScreenshotActionsPalette()
        self.screenshot_actions.copy_clicked.connect(self.copy_selected_screenshot)
        self.screenshot_actions.save_clicked.connect(self.save_pending_screenshot)
        self.screenshot_actions.cancel_clicked.connect(self.cancel_screenshot_capture)

        self.load_settings()

    def sync_regions(self) -> None:
        self.overlay.sync_input_region()
        self.overlay.update()
        self.toolbar.show()
        self.toolbar.raise_()

    def sync_active_color(self) -> None:
        self.toolbar.set_active_color(self.overlay.current_tool_color())

    def sync_size_controls(self) -> None:
        minimum, maximum = self.overlay.current_tool_width_range()
        current = self.overlay.current_tool_width()
        self.toolbar.size_palette.set_size_slider_range(minimum, maximum)
        self.toolbar.size_palette.set_size_slider_value(current)

    def sync_toolbar_state(self) -> None:
        self.sync_active_color()
        self.sync_size_controls()
        self.toolbar.set_board_button_mode(self.overlay.board_mode)
        self.toolbar.set_shapes_button_mode(self.overlay.mode)
        self.toolbar.set_tools_button_mode(self.overlay.mode)

        self.toolbar.tools_button.set_active(self.overlay.mode in {"pen", "highlighter", "text"})
        self.toolbar.shapes_button.set_active(self.overlay.mode in {"line", "arrow", "rect", "circle", "triangle"})
        self.toolbar.board_button.set_active(self.overlay.board_mode != "off")
        self.toolbar.move_button.set_active(self.overlay.mode == "move")
        self.toolbar.screenshot_button.set_active(self.overlay.mode == "screenshot")
        self.toolbar.eraser_button.set_active(self.overlay.mode == "eraser")
        self.toolbar.mouse_button.set_active(self.overlay.mode == "mouse")
        self.toolbar.size_button.set_active(self.overlay.mode in {"pen", "highlighter", "text", "line", "arrow", "rect", "circle", "triangle", "eraser"})

    def apply_selected_color(self, color: QColor) -> None:
        self.overlay.set_current_tool_color(color)
        self.sync_toolbar_state()
        self.save_settings()

    def apply_slider_size(self, value: int) -> None:
        self.overlay.set_current_tool_width(value)
        self.toolbar.size_palette.set_size_value(self.overlay.current_tool_width())
        self.save_settings()

    def set_shape_mode(self, mode: str) -> None:
        self.activate_mode_and_sync(mode)

    def set_tool_mode(self, mode: str) -> None:
        self.activate_mode_and_sync(mode)

    def activate_mode_and_sync(self, mode: str) -> None:
        if mode == "pen":
            self.overlay.set_pen_mode()
        elif mode == "highlighter":
            self.overlay.set_highlighter_mode()
        elif mode == "line":
            self.overlay.set_line_mode()
        elif mode == "arrow":
            self.overlay.set_arrow_mode()
        elif mode == "rect":
            self.overlay.set_rect_mode()
        elif mode == "circle":
            self.overlay.set_circle_mode()
        elif mode == "triangle":
            self.overlay.set_triangle_mode()
        elif mode == "text":
            self.overlay.set_text_mode()
        elif mode == "move":
            self.overlay.set_move_mode()
        elif mode == "screenshot":
            self.overlay.set_screenshot_mode()
        elif mode == "eraser":
            self.overlay.set_eraser_mode()
        else:
            self.overlay.set_mouse_mode()

        self.toolbar.show()
        self.toolbar.raise_()
        if mode == "mouse":
            self.toolbar.activateWindow()
        self.sync_regions()
        self.sync_toolbar_state()
        self.save_settings()

    def activate_pen_mode(self) -> None:
        self.activate_mode_and_sync("pen")

    def activate_highlighter_mode(self) -> None:
        self.activate_mode_and_sync("highlighter")

    def activate_line_mode(self) -> None:
        self.activate_mode_and_sync("line")

    def activate_arrow_mode(self) -> None:
        self.activate_mode_and_sync("arrow")

    def activate_rect_mode(self) -> None:
        self.activate_mode_and_sync("rect")

    def activate_circle_mode(self) -> None:
        self.activate_mode_and_sync("circle")

    def activate_triangle_mode(self) -> None:
        self.activate_mode_and_sync("triangle")

    def activate_text_mode(self) -> None:
        self.activate_mode_and_sync("text")

    def activate_move_mode(self) -> None:
        self.activate_mode_and_sync("move")

    def activate_eraser_mode(self) -> None:
        self.activate_mode_and_sync("eraser")

    def activate_mouse_mode(self) -> None:
        self.activate_mode_and_sync("mouse")

    def on_toolbar_moved(self) -> None:
        self.toolbar.color_palette.hide()
        self.toolbar.board_palette.hide()
        self.toolbar.shape_palette.hide()
        self.toolbar.tool_palette.hide()
        self.toolbar.size_palette.hide()
        self.screenshot_actions.hide()
        self.sync_regions()
        self.save_settings()

    def save_settings(self) -> None:
        self.settings.setValue("pen_color", self.overlay.pen_color.name())
        self.settings.setValue("pen_width", self.overlay.pen_width)
        self.settings.setValue("highlighter_color", self.overlay.highlighter_color.name())
        self.settings.setValue("highlighter_width", self.overlay.highlighter_width)
        self.settings.setValue("text_color", self.overlay.text_color.name())
        self.settings.setValue("text_font_size", self.overlay.text_font_size)
        self.settings.setValue("board_mode", self.overlay.board_mode)
        self.settings.setValue("eraser_width", self.overlay.eraser_width)
        self.settings.setValue("last_mode", self.overlay.mode)
        self.settings.setValue("toolbar_x", self.toolbar.x())
        self.settings.setValue("toolbar_y", self.toolbar.y())
        self.settings.sync()

    def load_settings(self) -> None:
        self.overlay.pen_color = QColor(str(self.settings.value("pen_color", self.overlay.pen_color.name())))
        self.overlay.highlighter_color = QColor(str(self.settings.value("highlighter_color", self.overlay.highlighter_color.name())))
        self.overlay.text_color = QColor(str(self.settings.value("text_color", self.overlay.text_color.name())))
        self.overlay.pen_width = int(self.settings.value("pen_width", self.overlay.pen_width))
        self.overlay.highlighter_width = int(self.settings.value("highlighter_width", self.overlay.highlighter_width))
        self.overlay.text_font_size = int(self.settings.value("text_font_size", self.overlay.text_font_size))
        self.overlay.board_mode = str(self.settings.value("board_mode", "off"))
        self.overlay.eraser_width = int(self.settings.value("eraser_width", self.overlay.eraser_width))

        toolbar_x = int(self.settings.value("toolbar_x", 40))
        toolbar_y = int(self.settings.value("toolbar_y", 40))
        self.toolbar.move(toolbar_x, toolbar_y)

        last_mode = str(self.settings.value("last_mode", "mouse"))
        if last_mode in {"pen", "highlighter", "line", "arrow", "rect", "circle", "triangle", "text", "move", "eraser"}:
            self.activate_mode_and_sync(last_mode)
        else:
            self.activate_mouse_mode()
        self.toolbar.set_board_button_mode(self.overlay.board_mode)

    def quit_app(self) -> None:
        self.save_settings()

        try:
            self.overlay.shutdown_overlay()
        except Exception:
            pass

        try:
            self.toolbar.hide()
            self.toolbar.close()
        except Exception:
            pass

        self.app.processEvents()
        self.app.quit()

    def show(self) -> None:
        self.overlay.showFullScreen()
        self.sync_regions()
        self.sync_toolbar_state()

    def __del__(self) -> None:
        try:
            self.save_settings()
        except Exception:
            pass

    def cleanup_before_quit(self) -> None:
        try:
            self.overlay.shutdown_overlay()
        except Exception:
            pass

        try:
            self.toolbar.hide()
        except Exception:
            pass

    def set_board_mode(self, mode: str) -> None:
        if self.overlay.board_mode == mode:
            self.overlay.set_board_mode("off")
        else:
            self.overlay.set_board_mode(mode)

        self.toolbar.set_board_button_mode(self.overlay.board_mode)
        self.save_settings()

    def activate_screenshot_mode(self) -> None:
        self.screenshot_actions.hide()
        self.pending_screenshot_pixmap = None
        self.pending_screenshot_rect = None
        self.overlay.screenshot_start = None
        self.overlay.screenshot_end = None
        self.overlay.screenshot_selection_ready = False
        self.overlay.set_screenshot_mode()
        self.toolbar.show()
        self.toolbar.raise_()
        self.overlay.showFullScreen()
        self.overlay.raise_()
        self.overlay.activateWindow()
        self.overlay.setFocus()
        self.sync_regions()

    def save_selected_screenshot(self) -> None:
        self.prepare_selected_screenshot()
        self.save_pending_screenshot()

    def prepare_selected_screenshot(self) -> None:
        if self.overlay.screenshot_start is None or self.overlay.screenshot_end is None:
            self.pending_screenshot_pixmap = None
            self.pending_screenshot_rect = None
            return

        rect = QRectF(self.overlay.screenshot_start, self.overlay.screenshot_end).normalized().toRect()
        if rect.width() < 2 or rect.height() < 2:
            self.pending_screenshot_pixmap = None
            self.pending_screenshot_rect = None
            return

        self.pending_screenshot_rect = rect

        board_color = self.overlay.current_board_color()

        old_start = self.overlay.screenshot_start
        old_end = self.overlay.screenshot_end

        self.overlay.screenshot_start = None
        self.overlay.screenshot_end = None
        self.overlay.update()
        self.app.processEvents()

        if board_color is None:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                self.pending_screenshot_pixmap = None
                self.pending_screenshot_rect = None
                self.overlay.screenshot_start = old_start
                self.overlay.screenshot_end = old_end
                self.overlay.update()
                return
            base_pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        else:
            base_pixmap = QPixmap(rect.size())
            base_pixmap.fill(board_color)

        overlay_pixmap = self.overlay.render_items_to_pixmap(rect)

        painter = QPainter(base_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawPixmap(0, 0, overlay_pixmap)
        painter.end()

        self.pending_screenshot_pixmap = base_pixmap

        self.overlay.screenshot_start = old_start
        self.overlay.screenshot_end = old_end
        self.overlay.update()

    def show_screenshot_actions(self) -> None:
        if self.pending_screenshot_rect is None:
            return

        rect = self.pending_screenshot_rect
        self.screenshot_actions.adjustSize()

        action_w = self.screenshot_actions.width()
        action_h = self.screenshot_actions.height()

        screen_rect = self.overlay.rect()

        margin = 8
        gap = 8

        below_x = rect.center().x() - (action_w // 2)
        below_y = rect.bottom() + gap

        above_x = below_x
        above_y = rect.top() - action_h - gap

        right_x = rect.right() + gap
        right_y = rect.center().y() - (action_h // 2)

        left_x = rect.left() - action_w - gap
        left_y = right_y

        def fits(x: int, y: int) -> bool:
            return (
                x >= margin
                and y >= margin
                and x + action_w <= screen_rect.width() - margin
                and y + action_h <= screen_rect.height() - margin
            )

        if fits(below_x, below_y):
            x, y = below_x, below_y
        elif fits(above_x, above_y):
            x, y = above_x, above_y
        elif fits(right_x, right_y):
            x, y = right_x, right_y
        elif fits(left_x, left_y):
            x, y = left_x, left_y
        else:
            x = max(margin, min(below_x, screen_rect.width() - action_w - margin))
            y = max(margin, min(below_y, screen_rect.height() - action_h - margin))

        global_pos = self.overlay.mapToGlobal(QPoint(x, y))
        self.screenshot_actions.move(global_pos)
        self.screenshot_actions.show()
        self.screenshot_actions.raise_()
        self.screenshot_actions.activateWindow()

    def clear_screenshot_state(self) -> None:
        self.pending_screenshot_pixmap = None
        self.pending_screenshot_rect = None
        self.overlay.screenshot_start = None
        self.overlay.screenshot_end = None
        self.overlay.screenshot_selection_ready = False
        self.overlay.update()
        self.screenshot_actions.hide()

    def copy_selected_screenshot(self) -> None:
        if self.pending_screenshot_pixmap is None:
            return

        clipboard = QApplication.clipboard()
        clipboard.setPixmap(self.pending_screenshot_pixmap, QClipboard.Mode.Clipboard)

        self.clear_screenshot_state()
        self.toolbar.show()
        self.toolbar.raise_()
        self.activate_mouse_mode()

    def save_pending_screenshot(self) -> None:
        if self.pending_screenshot_pixmap is None:
            return

        pictures_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
        if not pictures_dir:
            pictures_dir = str(Path.home() / "Pictures")

        target_dir = Path(pictures_dir) / "clarivo"
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp = QDateTime.currentDateTime().toString("yyyyMMdd-hhmmss")
        file_path = target_dir / f"clarivo-{timestamp}.png"
        self.pending_screenshot_pixmap.save(str(file_path), "PNG")

        self.clear_screenshot_state()
        self.toolbar.show()
        self.toolbar.raise_()
        self.activate_mouse_mode()

    def cancel_screenshot_capture(self) -> None:
        self.clear_screenshot_state()
        self.toolbar.show()
        self.toolbar.raise_()
        self.activate_mouse_mode()

    def maybe_finish_screenshot(self) -> None:
        if self.overlay.mode != "screenshot":
            return
        if not self.overlay.screenshot_selection_ready:
            return
        if self.overlay.screenshot_start is None or self.overlay.screenshot_end is None:
            return

        self.overlay.screenshot_selection_ready = False
        self.prepare_selected_screenshot()
        self.show_screenshot_actions()

def main() -> int:
    app = QApplication(sys.argv)
    screen_pen = ScreenPenApp(app)
    screen_pen.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())