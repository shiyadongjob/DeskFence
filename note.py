# -*- coding: utf-8 -*-
"""便签：彩色半透明窗口，富文本自动保存"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QColorDialog, QHBoxLayout, QMenu, QPushButton,
                               QSizeGrip, QTextEdit, QVBoxLayout, QWidget)

from common import NOTE_COLORS, is_light


def _norm_color(v):
    """兼容旧配置里的颜色名，统一转成 #rrggbb"""
    if v in NOTE_COLORS:
        return NOTE_COLORS[v]
    if isinstance(v, str) and v.startswith("#"):
        return v
    return NOTE_COLORS["黄"]


class NoteDragBar(QWidget):
    """便签顶栏：拖动窗口 + 关闭按钮"""

    def __init__(self, note):
        super().__init__()
        self.note = note
        self._off = None
        self.setFixedHeight(28)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 4, 0)
        lay.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton{color:#555;background:transparent;border:none;font-size:13px;}"
            "QPushButton:hover{background:rgba(0,0,0,40);border-radius:4px;}")
        close_btn.clicked.connect(lambda: note.manager.delete_note(note))
        lay.addWidget(close_btn)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._off = (e.globalPosition().toPoint()
                         - self.note.frameGeometry().topLeft())

    def mouseMoveEvent(self, e):
        if self._off is not None and e.buttons() & Qt.LeftButton:
            self.note.move(e.globalPosition().toPoint() - self._off)

    def mouseReleaseEvent(self, e):
        if self._off is not None:
            self._off = None
            self.note.manager.schedule_save()


class Note(QWidget):
    """便签（彩色半透明窗口，内容自动保存）"""

    def __init__(self, manager, html="", geo=None, color="黄"):
        super().__init__()
        self.manager = manager
        self.color = _norm_color(color)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(170, 110)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.bar = NoteDragBar(self)

        self.edit = QTextEdit()
        if html:
            self.edit.setHtml(html)
        self.edit.setPlaceholderText("写点什么…")
        self.edit.textChanged.connect(manager.schedule_save)
        self._apply_text_style()

        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        self.grip.setStyleSheet("background:transparent;")
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 2, 2)
        bottom.addStretch()
        bottom.addWidget(self.grip)

        root.addWidget(self.bar)
        root.addWidget(self.edit, 1)
        root.addLayout(bottom)

        if geo:
            self.setGeometry(*geo)
        else:
            self.resize(240, 200)
            off = 40 * (len(manager.notes) % 8)
            self.move(520 + off, 160 + off)

    def _apply_text_style(self):
        """浅色便签深色字，深色便签浅色字"""
        fg = "#3a3a3a" if is_light(self.color) else "#f0f0f0"
        self.edit.setStyleSheet(
            "QTextEdit{background:transparent;border:none;color:%s;"
            "font-size:12px;padding:2px 6px;}"
            "QScrollBar:vertical{background:transparent;width:8px;}"
            "QScrollBar::handle:vertical{background:rgba(128,128,128,120);"
            "border-radius:4px;min-height:24px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}" % fg)

    def set_color(self, hex_color):
        self.color = hex_color
        self._apply_text_style()
        self.update()
        self.manager.schedule_save()

    def paintEvent(self, e):
        c = QColor(self.color)
        c.setAlpha(235)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(128, 128, 128, 90)))
        p.setBrush(c)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.manager.schedule_save()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        act_fence = m.addAction("新建格子")
        act_note = m.addAction("新建便签")
        color_menu = m.addMenu("颜色")
        color_acts = {name: color_menu.addAction(name) for name in NOTE_COLORS}
        act_custom = color_menu.addAction("自定义…")
        m.addSeparator()
        act_del = m.addAction("删除此便签")
        chosen = m.exec(e.globalPos())
        if chosen is act_fence:
            self.manager.create_fence()
        elif chosen is act_note:
            self.manager.create_note()
        elif chosen is act_del:
            self.manager.delete_note(self)
        elif chosen is act_custom:
            c = QColorDialog.getColor(QColor(self.color), self, "便签颜色")
            if c.isValid():
                self.set_color(c.name())
        else:
            for name, act in color_acts.items():
                if chosen is act:
                    self.set_color(NOTE_COLORS[name])
                    break

    def to_dict(self):
        return {
            "x": self.x(), "y": self.y(),
            "w": self.width(), "h": self.height(),
            "color": self.color,
            "html": self.edit.toHtml(),
        }
