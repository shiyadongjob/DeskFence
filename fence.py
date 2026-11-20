# -*- coding: utf-8 -*-
"""收纳格子：图标项 + 标题栏 + 多彩边框 + Win32 四边四角 resize + 排序"""
import os
import subprocess
import uuid

from PySide6.QtCore import (QMimeData, QPoint, QEvent, QRect, Qt, QTimer, QUrl)
from PySide6.QtGui import (QBrush, QColor, QDrag, QLinearGradient, QPainter,
                           QPen)
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMenu, QPushButton, QScrollArea, QSizeGrip,
                               QVBoxLayout, QWidget)

import storage
import shellmenu
from common import (EDGE_HIT, FENCE_COLORS, FENCE_FRAMES, MAX_H, SORTS,
                    TITLE_H, VIEWS, cell_size, display_name, file_pixmap,
                    frame_info, is_light)

# 列表模式下使用系统小图标尺寸（资源管理器列表视图大小）
LIST_ICON = 18


def _norm_color(v):
    if v in FENCE_COLORS:
        return FENCE_COLORS[v]
    if isinstance(v, str) and v.startswith("#"):
        return v
    return FENCE_COLORS["深灰"]


# ---- 边框绘制工具 ----
def _auto_border_pen(fence, width):
    """自动取与底色对比的描边色"""
    if is_light(fence.color):
        return QPen(QColor(60, 60, 60, 160), width)
    return QPen(QColor(255, 255, 255, 180), width)


def _glow_pen(fence, width, alpha_center=180, alpha_edge=0):
    """发光边框：多层 pen 叠加"""
    base = QColor(fence.color)
    if is_light(fence.color):
        base = base.darker(140)
    else:
        base = base.lighter(130)
    return base


def draw_frame(p, fence, info):
    """按 info['type'] 绘制各种边框效果"""
    rect = fence.rect().adjusted(0, 0, -1, -1)
    radius = info.get("radius", 12)
    bw = info.get("border_w", 1)
    ftype = info.get("type", "simple")

    # 背景填充
    alpha = fence.manager.settings.get("fence_alpha", 170)
    bg = QColor(fence.color); bg.setAlpha(alpha)
    p.setBrush(QBrush(bg))

    # —— 无边框 ——
    if ftype == "simple" and bw == 0:
        p.setPen(Qt.NoPen)
        if radius == 0:
            p.drawRect(rect)
        else:
            p.drawRoundedRect(rect, radius, radius)
        return

    # —— 简约描边 / 大圆角 / 直角 / 加粗 ——
    if ftype == "simple":
        p.setPen(_auto_border_pen(fence, bw))
        if radius == 0:
            p.drawRect(rect)
        else:
            p.drawRoundedRect(rect, radius, radius)
        return

    # —— 发光：外发光 + 内描边 ——
    if ftype == "glow":
        glow = info.get("glow", 18)
        # 外发光层
        for i in range(glow, 0, -2):
            c = _glow_pen(fence, 2)
            c.setAlpha(40 - i * 2)
            p.setPen(QPen(c, 2))
            p.setBrush(Qt.NoBrush)
            rr = rect.adjusted(-i, -i, i, i)
            p.drawRoundedRect(rr, radius + i, radius + i)
        # 背景 + 内描边
        p.setBrush(QBrush(bg))
        p.setPen(_auto_border_pen(fence, bw))
        p.drawRoundedRect(rect, radius, radius)
        return

    # —— 霓虹：外发光 + 强描边 ——
    if ftype == "neon":
        glow = info.get("glow", 24)
        neon_c = QColor("#4fc3f7") if is_light(fence.color) else QColor("#22d3ee")
        for i in range(glow, 0, -2):
            c = QColor(neon_c); c.setAlpha(120 - i * 4)
            p.setPen(QPen(c, 3))
            p.setBrush(Qt.NoBrush)
            rr = rect.adjusted(-i, -i, i, i)
            p.drawRoundedRect(rr, radius + i, radius + i)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(neon_c, 2))
        p.drawRoundedRect(rect, radius, radius)
        return

    # —— 顶部彩条 ——
    if ftype == "topbar":
        p.setPen(_auto_border_pen(fence, bw))
        if radius == 0:
            p.drawRect(rect)
        else:
            p.drawRoundedRect(rect, radius, radius)
        # 顶部渐变彩条
        bar_h = info.get("bar_h", 4)
        grad = QLinearGradient(rect.topLeft(), QPoint(rect.right(), rect.top()))
        if is_light(fence.color):
            grad.setColorAt(0, QColor(66, 153, 225, 200))
            grad.setColorAt(0.5, QColor(128, 90, 213, 200))
            grad.setColorAt(1, QColor(237, 100, 166, 200))
        else:
            grad.setColorAt(0, QColor(34, 211, 238, 220))
            grad.setColorAt(0.5, QColor(168, 85, 247, 220))
            grad.setColorAt(1, QColor(244, 114, 182, 220))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        top_bar = QRect(rect.x() + bw, rect.y() + bw,
                        rect.width() - 2 * bw, bar_h)
        if radius > 0:
            # 裁剪圆角后再画彩条有点麻烦，简化处理
            p.drawRoundedRect(top_bar, radius - 1, radius - 1)
        else:
            p.drawRect(top_bar)
        return

    # —— 玻璃：渐变 + 高光 ——
    if ftype == "glass":
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, QColor(255, 255, 255, 40))
        grad.setColorAt(0.5, bg)
        grad.setColorAt(1, QColor(0, 0, 0, 40))
        p.setBrush(QBrush(grad))
        p.setPen(_auto_border_pen(fence, bw))
        if radius == 0:
            p.drawRect(rect)
        else:
            p.drawRoundedRect(rect, radius, radius)
        # 顶部高光条
        hi = QLinearGradient(rect.topLeft(),
                             QPoint(rect.right(), rect.y() + 20))
        hi.setColorAt(0, QColor(255, 255, 255, 120))
        hi.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(hi))
        p.drawRoundedRect(rect.adjusted(bw, bw, -bw, rect.height() - bw - 40),
                          max(radius - 2, 4), max(radius - 2, 4))
        return

    # —— 角落装饰：四角圆点 + 主描边 ——
    if ftype == "corners":
        p.setPen(_auto_border_pen(fence, bw))
        p.drawRoundedRect(rect, radius, radius)
        corner_c = QColor("#f59e0b") if is_light(fence.color) else QColor("#fbbf24")
        p.setPen(Qt.NoPen); p.setBrush(corner_c)
        dot_r = 4
        d = dot_r + 2
        for cx, cy in [(rect.x() + d, rect.y() + d),
                       (rect.right() - d, rect.y() + d),
                       (rect.x() + d, rect.bottom() - d),
                       (rect.right() - d, rect.bottom() - d)]:
            p.drawEllipse(QPoint(cx, cy), dot_r, dot_r)
        return

    # —— 虚线 ——
    if ftype == "dashed":
        p.setPen(QPen(_auto_border_pen(fence, bw).color(), bw, Qt.DashLine))
        if radius == 0:
            p.drawRect(rect)
        else:
            p.drawRoundedRect(rect, radius, radius)
        return

    # fallback
    p.setPen(_auto_border_pen(fence, bw))
    p.drawRoundedRect(rect, radius, radius)


# ==========================================================================
# IconItem / TitleBar / Fence
# ==========================================================================

class IconItem(QWidget):
    """格子里的单个图标项，支持同格子内拖动重排序"""

    def __init__(self, path, fence, parent=None):
        super().__init__(parent)
        self.path = os.path.normpath(path)
        self.fence = fence
        self._drag_start = None
        self._hover = False
        self._insert_hint = False
        self._dark_text = False
        icon_size = fence.icon_size
        self.setFixedSize(fence.cell_w, fence.cell_h)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(self.path)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 4)
        lay.setSpacing(2)

        self.icon_label = QLabel()
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(icon_size, icon_size)
        self.icon_label.setPixmap(file_pixmap(self.path, icon_size))

        self.text_label = QLabel(display_name(self.path))
        self.text_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.text_label.setWordWrap(True)
        self.text_label.setFixedHeight(fence.cell_h - icon_size - 16)

        lay.addWidget(self.icon_label, 0, Qt.AlignHCenter)
        lay.addWidget(self.text_label)

        self.set_dark_text(is_light(fence.color))

    def set_icon_px(self, px):
        """按像素尺寸重绘图标（列表模式用原生小图标）"""
        if self.icon_label.width() == px and self.icon_label.height() == px:
            return
        self.icon_label.setFixedSize(px, px)
        self.icon_label.setPixmap(file_pixmap(self.path, px))

    def set_dark_text(self, dark):
        self._dark_text = dark
        self.text_label.setStyleSheet(
            "color:%s; font-size:11px; background:transparent;"
            % ("#333" if dark else "#fff"))
        effect = QGraphicsDropShadowEffect(self.text_label)
        effect.setBlurRadius(6)
        effect.setOffset(0, 1)
        effect.setColor(QColor(255, 255, 255, 150) if dark
                        else QColor(0, 0, 0, 200))
        self.text_label.setGraphicsEffect(effect)

    def enterEvent(self, e):
        self._hover = True; self.update()

    def leaveEvent(self, e):
        self._hover = False; self.update()

    def set_insert_hint(self, on):
        self._insert_hint = on; self.update()

    def paintEvent(self, e):
        if self._hover or self._insert_hint:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            if self._dark_text:
                p.setPen(QPen(QColor(0, 0, 0, 80)))
                p.setBrush(QColor(0, 0, 0, 35))
            else:
                p.setPen(QPen(QColor(255, 255, 255, 90)))
                p.setBrush(QColor(255, 255, 255, 50))
            r = self.rect().adjusted(1, 1, -1, -1)
            p.drawRoundedRect(r, 6, 6)
            if self._insert_hint:
                p.setPen(QPen(QColor(120, 180, 255, 200), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 8, 8)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            try:
                os.startfile(self.path)
            except OSError:
                pass

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.fence.locked:
            self._drag_start = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self.fence.locked:
            return
        if self._drag_start is None or not (e.buttons() & Qt.LeftButton):
            return
        dist = (e.position().toPoint() - self._drag_start).manhattanLength()
        if dist < QApplication.startDragDistance():
            return
        self._drag_start = None
        self.fence._start_drag(self)

    def contextMenuEvent(self, e):
        # 与桌面一致的系统右键菜单（打开 / 复制 / 剪切 / 重命名 / 属性 …）
        hwnd = int(self.fence.winId())
        ok = shellmenu.show_shell_menu(self.path, hwnd, e.globalPos())
        if ok:
            # 菜单里的删除 / 剪切可能已改动文件，稍后清理失效项
            QTimer.singleShot(600, self.fence.drop_missing)


class TitleBar(QWidget):
    """格子标题栏：名字默认 QLabel（可抓来拖），双击才变编辑框"""
    BIG = 32

    def __init__(self, fence, name):
        super().__init__()
        self.fence = fence
        self._drag_off = None
        self.setFixedHeight(TITLE_H)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 6, 6)
        lay.setSpacing(2)

        # —— 默认显示 QLabel，双击切换为 QLineEdit ——
        self.name_label = QLabel(name)
        self.name_label.setCursor(Qt.SizeAllCursor)   # 提示可以拖
        self.name_label.setMaximumWidth(200)
        self.name_label.setMinimumWidth(40)
        self.name_label.installEventFilter(self)      # 抓双击事件

        self.name_edit = QLineEdit(name)
        self.name_edit.setMaximumWidth(200)
        self.name_edit.setMinimumWidth(40)
        self.name_edit.hide()
        self.name_edit.editingFinished.connect(self._finish_edit)
        self.name_edit.returnPressed.connect(self._finish_edit)

        self.collapse_btn = self._mk_btn("▾", fence.toggle_collapse)
        self.collapse_btn.setToolTip("折叠 / 展开（双击标题栏同效）")
        self.lock_btn = self._mk_btn("🔓", fence.toggle_lock)
        self.lock_btn.setToolTip("锁定 / 解锁（锁定后格子不可移动）")
        self.add_btn = self._mk_btn("＋", self._show_add_menu)
        self.add_btn.setToolTip("新建格子 / 便签")
        self.close_btn = self._mk_btn(
            "🗑", lambda: fence.manager.delete_fence(fence))
        self.close_btn.setToolTip("删除格子（文件自动放回桌面）")

        lay.addWidget(self.name_label, 1)
        lay.addWidget(self.name_edit, 1)
        lay.addWidget(self.collapse_btn)
        lay.addWidget(self.lock_btn)
        lay.addWidget(self.add_btn)
        lay.addWidget(self.close_btn)

    # —— 双击 QLabel → 切到 QLineEdit；失焦/回车 → 切回 ——
    def eventFilter(self, obj, event):
        if obj is self.name_label and event.type() == QEvent.MouseButtonDblClick:
            self._start_edit()
            return True
        return super().eventFilter(obj, event)

    def _start_edit(self):
        self.name_edit.setText(self.name_label.text())
        self.name_label.hide()
        self.name_edit.show()
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _finish_edit(self):
        new = self.name_edit.text().strip() or self.name_label.text()
        self.name_label.setText(new)
        self.name_edit.hide()
        self.name_label.show()
        self.fence.manager.schedule_save()

    # —— 供 Fence 取名字（替代 fence.titlebar.name_edit.text()）——
    def name_text(self):
        return self.name_label.text()

    def _mk_btn(self, text, slot):
        b = QPushButton(text)
        b.setFixedSize(self.BIG, self.BIG)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def apply_theme(self, dark_text):
        fg = "#333" if dark_text else "#fff"
        hover = "rgba(0,0,0,30)" if dark_text else "rgba(255,255,255,40)"
        self.name_label.setStyleSheet(
            "QLabel{color:%s;font-weight:bold;font-size:14px;"
            "padding:3px 6px;}" % fg)
        self.name_edit.setStyleSheet(
            "QLineEdit{color:%s;background:transparent;border:none;"
            "font-weight:bold;font-size:14px;padding:3px 6px;}"
            "QLineEdit:focus{background:%s;border-radius:4px;}" % (fg, hover))
        css = ("QPushButton{color:%s;background:transparent;border:none;"
               "font-size:15px;}"
               "QPushButton:hover{background:%s;border-radius:6px;}"
               % (fg, hover))
        for b in (self.collapse_btn, self.lock_btn, self.add_btn, self.close_btn):
            b.setStyleSheet(css)

    def update_lock(self, locked):
        self.lock_btn.setText("🔒" if locked else "🔓")

    def _show_add_menu(self):
        m = QMenu(self)
        a1 = m.addAction("新建格子")
        a2 = m.addAction("新建便签")
        chosen = m.exec(self.add_btn.mapToGlobal(
            self.add_btn.rect().bottomLeft()))
        if chosen is a1:
            self.fence.manager.create_fence()
        elif chosen is a2:
            self.fence.manager.create_note()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and not self.fence.locked:
            self._drag_off = (e.globalPosition().toPoint()
                              - self.fence.frameGeometry().topLeft())

    def mouseMoveEvent(self, e):
        if self._drag_off is not None and e.buttons() & Qt.LeftButton:
            self.fence.move(e.globalPosition().toPoint() - self._drag_off)

    def mouseReleaseEvent(self, e):
        if self._drag_off is not None:
            self._drag_off = None
            self.fence.manager.schedule_save()

    def mouseDoubleClickEvent(self, e):
        # 如果点的是 label，交给 eventFilter 处理重命名；否则折叠
        pos_l = self.mapFromGlobal(e.globalPosition().toPoint())
        if not self.name_label.geometry().contains(pos_l):
            if e.button() == Qt.LeftButton:
                self.fence.toggle_collapse()


class BottomToolBar(QWidget):
    """底部工具栏：排序下拉 + 视图切换"""
    H = 28

    def __init__(self, fence):
        super().__init__()
        self.fence = fence
        self.setFixedHeight(self.H)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.setSpacing(6)

        self.sort_btn = QPushButton()
        self.sort_btn.setCursor(Qt.PointingHandCursor)
        self.sort_btn.setToolTip("排序方式")
        self.sort_btn.clicked.connect(self._show_sort_menu)

        self.view_btn = QPushButton("▦")
        self.view_btn.setFixedSize(26, 22)
        self.view_btn.setCursor(Qt.PointingHandCursor)
        self.view_btn.setToolTip("切换 图标 / 列表 视图")
        self.view_btn.clicked.connect(fence.toggle_view)

        self.count_label = QLabel("")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        lay.addWidget(self.sort_btn)
        lay.addWidget(self.view_btn)
        lay.addStretch(1)
        lay.addWidget(self.count_label)

        self.update_sort_text()
        self.update_view_icon()

    def _show_sort_menu(self):
        m = QMenu(self)
        cur = self.fence.sort
        for label, val in SORTS.items():
            act = m.addAction(label)
            if val == cur:
                act.setText("✓ " + label)
            act.triggered.connect(
                lambda checked=False, v=val: self.fence.set_sort(v))
        m.exec(self.sort_btn.mapToGlobal(
            self.sort_btn.rect().bottomLeft()))

    def update_sort_text(self):
        cur = self.fence.sort
        for label, val in SORTS.items():
            if val == cur:
                self.sort_btn.setText("排序：" + label + " ▾")
                return
        self.sort_btn.setText("排序：手动 ▾")

    def update_view_icon(self):
        self.view_btn.setText("▤" if self.fence.view == "list" else "▦")

    def update_count(self, n):
        self.count_label.setText("%d 项" % n)

    def apply_theme(self, dark_text):
        fg = "#333" if dark_text else "#fff"
        hover = "rgba(0,0,0,25)" if dark_text else "rgba(255,255,255,35)"
        self.sort_btn.setStyleSheet(
            "QPushButton{color:%s;background:transparent;border:none;"
            "font-size:12px;padding:2px 6px;border-radius:4px;}"
            "QPushButton:hover{background:%s;}" % (fg, hover))
        self.view_btn.setStyleSheet(
            "QPushButton{color:%s;background:transparent;border:none;"
            "font-size:14px;border-radius:4px;}"
            "QPushButton:hover{background:%s;}" % (fg, hover))
        self.count_label.setStyleSheet(
            "QLabel{color:%s;font-size:11px;}" % fg)


class Fence(QWidget):
    """一个收纳格子，支持四边四角 resize、多种边框、锁定、排序、图标/列表视图"""

    def __init__(self, manager, name="新建格子", items=None, geo=None,
                 collapsed=False, color="深灰", frame="简约描边",
                 sort="手动", view="图标", locked=False, fence_id=None):
        super().__init__()
        self.manager = manager
        self.id = fence_id or uuid.uuid4().hex[:8]
        self.items = []
        self._collapsed = False
        self._saved_h = 300
        self.color = _norm_color(color)
        self.frame = frame if frame in FENCE_FRAMES else "简约描边"
        self.sort = sort if sort in SORTS.values() else (
            SORTS.get(sort, "manual") if isinstance(sort, str) else "manual")
        if self.sort not in SORTS.values():
            self.sort = "manual"
        # 视图模式
        self.view = view if view in VIEWS.values() else VIEWS.get(view, "icon")
        if self.view not in VIEWS.values():
            self.view = "icon"
        self.locked = locked
        self.icon_size = manager.settings.get("icon_size", 40)
        self.cell_w, self.cell_h = cell_size(self.icon_size)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.setMinimumSize(200, TITLE_H + 60)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.titlebar = TitleBar(self, name)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:transparent;width:8px;}"
            "QScrollBar::handle:vertical{background:rgba(128,128,128,120);"
            "border-radius:4px;min-height:24px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self.scroll.viewport().setStyleSheet("background:transparent;")

        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background:transparent;")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(8, 4, 8, 8)
        self.grid.setSpacing(0)
        self.scroll.setWidget(self.grid_host)

        root.addWidget(self.titlebar)
        root.addWidget(self.scroll, 1)

        # 底部工具栏（排序下拉 + 视图切换 + 项数 + 右下角 SizeGrip）
        self.bottom_toolbar = BottomToolBar(self)
        # 右下角 SizeGrip：叠在 bottom_toolbar 右下角
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(14, 14)
        self.grip.setStyleSheet("background:transparent;")
        # 用 bottom_toolbar 的布局：在 count_label 后面加 grip
        # BottomToolBar 里 lay 已经是 [sort_btn | view_btn | stretch | count_label]
        # 我们在 count_label 之后追加 grip
        btb_lay = self.bottom_toolbar.layout()
        btb_lay.addWidget(self.grip)

        root.addWidget(self.bottom_toolbar)

        if geo:
            self.setGeometry(*geo)
        else:
            self.resize(360, 300)
            off = 40 * (len(manager.fences) % 8)
            self.move(120 + off, 120 + off)

        for p in (items or []):
            if os.path.exists(p):
                self._add_item(p)
            else:
                # 跳过失效路径，启动时记一条
                import logging as _l
                _l.getLogger(__name__).warning("跳过失效路径: %s", p)
        self._apply_sort(initial=True)
        self.reflow()
        self.apply_theme()
        self.titlebar.update_lock(locked)
        self.grip.setVisible(not locked)
        self.bottom_toolbar.update_count(len(self.items))

        self._reflow_timer = QTimer(self, singleShot=True, interval=60,
                                    timeout=self.reflow)

        # 边缘 resize 状态
        self._resize_state = None   # None 或 ('resize', flags, start_pos, start_geo)
        # 给 Fence 自身 + TitleBar 装过滤器：
        # - Fence 自身：检测左右下边缘
        # - TitleBar：  检测上边缘（被 TitleBar 盖住，需要从 filter 里识别）
        # 拖动移动由 TitleBar 自己的 mousePressEvent 处理，不在这里拦
        self.installEventFilter(self)
        self.titlebar.installEventFilter(self)
        self.setMouseTracking(True)

        if collapsed:
            self.toggle_collapse()

    # ---- 自实现四边四角 resize（事件过滤器） ----
    def _edge_flags(self, pos_local):
        m = EDGE_HIT
        x, y = pos_local.x(), pos_local.y()
        w, h = self.width(), self.height()
        L = x <= m; R = x >= w - m
        T = y <= m; B = y >= h - m
        if L or R or T or B:
            return (L, T, R, B)
        return None

    def _cursor_for(self, flags):
        if flags is None: return Qt.ArrowCursor
        L, T, R, B = flags
        if (T and L) or (B and R): return Qt.SizeFDiagCursor
        if (T and R) or (B and L): return Qt.SizeBDiagCursor
        if L or R: return Qt.SizeHorCursor
        if T or B: return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def eventFilter(self, obj, event):
        if self.locked:
            return super().eventFilter(obj, event)

        # 只在 obj 是 Fence 自身 或 TitleBar 时考虑边缘 resize
        if obj is not self and obj is not self.titlebar:
            return super().eventFilter(obj, event)

        et = event.type()

        # 只在鼠标相关事件里取坐标（其他事件类型没有 globalPosition）
        if et not in (QEvent.HoverMove, QEvent.MouseMove,
                      QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            return super().eventFilter(obj, event)

        # QEvent 没有 globalPosition；必须先尝试转换
        try:
            pos_g = event.globalPosition().toPoint()
        except AttributeError:
            try:
                pos_g = event.globalPos()
            except AttributeError:
                return super().eventFilter(obj, event)

        pos_l = self.mapFromGlobal(pos_g)

        # —— 光标更新（鼠标移动/悬停时） ——
        if et in (QEvent.HoverMove, QEvent.MouseMove):
            if self._resize_state is None:
                flags = self._edge_flags(pos_l)
                self.setCursor(self._cursor_for(flags))

        # —— 边缘按下 → 开始 resize ——
        if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            flags = self._edge_flags(pos_l)
            if flags is not None:
                self._resize_state = ('resize', flags, pos_g, self.geometry())
                return True

        # —— 拖动中 → 持续 resize ——
        if et == QEvent.MouseMove and self._resize_state:
            _, flags, start_pos, start_geo = self._resize_state
            dx = pos_g.x() - start_pos.x()
            dy = pos_g.y() - start_pos.y()
            L, T, R, B = flags
            x, y, w, h = start_geo.x(), start_geo.y(), start_geo.width(), start_geo.height()
            min_w = self.minimumWidth(); min_h = self.minimumHeight()
            if L:
                nw = max(w - dx, min_w)
                x = start_geo.right() + 1 - nw; w = nw
            if R:
                w = max(w + dx, min_w)
            if T:
                nh = max(h - dy, min_h)
                y = start_geo.bottom() + 1 - nh; h = nh
            if B:
                h = max(h + dy, min_h)
            self.setGeometry(x, y, w, h)
            return True

        # —— 释放 → 结束 resize ——
        if et == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self._resize_state:
                self._resize_state = None
                self.unsetCursor()
                self.manager.schedule_save()
                return True

        return super().eventFilter(obj, event)

    # ---- 锁定 ----
    def toggle_lock(self):
        self.locked = not self.locked
        self.titlebar.update_lock(self.locked)
        self.grip.setVisible(not self.locked)
        self.titlebar.name_edit.setEnabled(not self.locked)
        self.manager.schedule_save()

    # ---- 外观 ----
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_frame(p, self, frame_info(self.frame))
        if self.locked:
            p.setPen(QPen(QColor(255, 180, 0, 180), 2))
            p.setBrush(QColor(255, 180, 0, 30))
            p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)
        p.end()

    def apply_theme(self):
        dark_text = is_light(self.color)
        self.titlebar.apply_theme(dark_text)
        self.bottom_toolbar.apply_theme(dark_text)
        for it in self.items:
            it.set_dark_text(dark_text)
        self.update()

    def rebuild(self):
        self.icon_size = self.manager.settings.get("icon_size", 40)
        self.cell_w, self.cell_h = cell_size(self.icon_size)
        paths = [it.path for it in self.items]
        for it in self.items:
            it.setParent(None); it.deleteLater()
        self.items = []
        for p in paths:
            self._add_item(p)
        self.reflow(); self.apply_theme()

    # ---- 视图切换 ----
    def toggle_view(self):
        self.view = "list" if self.view == "icon" else "icon"
        self.reflow()
        self.bottom_toolbar.update_view_icon()
        self.manager.schedule_save()

    # ---- 排序 ----
    def set_sort(self, sort_key):
        self.sort = sort_key
        self._apply_sort(); self.reflow()
        self.bottom_toolbar.update_sort_text()
        self.manager.schedule_save()

    def _apply_sort(self, initial=False):
        if self.sort == "name":
            self.items.sort(key=lambda it: display_name(it.path).lower())
        elif self.sort == "type":
            def key(it):
                p = it.path
                dir0 = 0 if os.path.isdir(p) else 1
                _, ext = os.path.splitext(p)
                return (dir0, ext.lower(), display_name(p).lower())
            self.items.sort(key=key)

    # ---- 拖入（从外部文件/其他格子） ----
    def _accept_drag(self, e):
        if not e.mimeData().hasUrls():
            return
        if isinstance(e.source(), IconItem):
            e.acceptProposedAction()
        else:
            # 外部文件一律按移动处理（拖进来就是收纳，原地就不再保留）
            e.setDropAction(Qt.MoveAction); e.accept()

    def dragEnterEvent(self, e):    self._accept_drag(e)
    def dragMoveEvent(self, e):
        self._accept_drag(e)
        src = e.source()
        if isinstance(src, IconItem) and src.fence is self:
            idx = self._item_index_at(e.position().toPoint())
            for i, it in enumerate(self.items):
                it.set_insert_hint(i == idx and it is src)

    def dragLeaveEvent(self, e):
        for it in self.items:
            it.set_insert_hint(False)

    def dropEvent(self, e):
        src = e.source()
        if isinstance(src, IconItem) and src.fence is self:
            for it in self.items: it.set_insert_hint(False)
            if self.sort == "manual":
                idx = self._item_index_at(e.position().toPoint())
                cur = self.items.index(src)
                if cur != idx:
                    self.items.pop(cur)
                    insert_at = idx if idx < cur else idx - 1
                    insert_at = max(0, min(insert_at, len(self.items)))
                    self.items.insert(insert_at, src)
                    self.reflow(); self.manager.schedule_save()
            e.acceptProposedAction(); return
        added = False
        for url in e.mimeData().urls():
            if not url.isLocalFile(): continue
            p = os.path.normpath(url.toLocalFile())
            new_p = storage.move_into(self.id, p)
            if new_p is None: new_p = p
            if any(it.path == new_p for it in self.items): continue
            self._add_item(new_p); added = True
        if added:
            self._apply_sort(); self.reflow(); self.manager.schedule_save()
        if isinstance(src, IconItem): e.acceptProposedAction()
        else: e.setDropAction(Qt.MoveAction); e.accept()

    def _start_drag(self, item):
        drag = QDrag(item)
        mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(item.path)])
        drag.setMimeData(mime)
        pix = item.icon_label.pixmap()
        if pix and not pix.isNull():
            drag.setPixmap(pix); drag.setHotSpot(QPoint(pix.width() // 2, pix.height() // 2))
        result = drag.exec(Qt.MoveAction | Qt.CopyAction)
        target = drag.target()
        if target is None:
            item.fence.remove_item(item)
        else:
            host = target
            while host is not None and not isinstance(host, Fence):
                host = host.parentWidget()
            if host is not None and host is not item.fence:
                item.fence.remove_item(item)

    def _item_index_at(self, pos_local):
        vp_pos = self.scroll.viewport().mapFromGlobal(self.mapToGlobal(pos_local))
        host_pos = self.grid_host.mapFrom(self.scroll.viewport(), vp_pos)
        for i, it in enumerate(self.items):
            r = QRect(it.pos(), it.size())
            if r.contains(host_pos): return i
        min_d = 1e9; best = len(self.items) - 1
        for i, it in enumerate(self.items):
            d = abs(it.y() + it.height() / 2 - host_pos.y())
            if d < min_d: min_d = d; best = i
        return best

    # ---- 项目管理 ----
    def _add_item(self, path):
        it = IconItem(path, self, self.grid_host)
        self.items.append(it)
        self.bottom_toolbar.update_count(len(self.items))

    def drop_missing(self):
        """系统右键菜单里删除 / 剪切之后，把已失效的条目从格子移除"""
        gone = [it for it in self.items if not os.path.exists(it.path)]
        if not gone:
            return
        for it in gone:
            self.items.remove(it)
            it.setParent(None); it.deleteLater()
        self.bottom_toolbar.update_count(len(self.items))
        self.reflow(); self.manager.schedule_save()

    def remove_item(self, item, release=False):
        if item in self.items:
            if release and storage.is_in_storage(item.path):
                storage.release(item.path)
            self.items.remove(item)
            item.setParent(None); item.deleteLater()
            self.bottom_toolbar.update_count(len(self.items))
            self.reflow(); self.manager.schedule_save()

    def release_all(self):
        storage.release_dir(self.id)
        for it in list(self.items):
            self.remove_item(it)

    def reflow(self):
        """按当前视图模式自动排列"""
        while self.grid.count(): self.grid.takeAt(0)

        if self.view == "list":
            # 列表模式：每行一个，左侧小图标 + 右侧文字（取系统小图标尺寸）
            self.grid.setHorizontalSpacing(0)
            row_w = max(120, self.scroll.viewport().width() - 20)
            for i, it in enumerate(self.items):
                it.set_icon_px(LIST_ICON)
                it.setFixedSize(row_w, LIST_ICON + 14)
                # 改内部布局：图标在左，文字拉伸在右
                lay = it.layout()
                while lay.count(): lay.takeAt(0)
                row = QHBoxLayout()
                row.setContentsMargins(6, 3, 6, 3)
                row.setSpacing(8)
                row.addWidget(it.icon_label)
                row.addWidget(it.text_label, 1)
                # text_label 改为单行省略
                it.text_label.setWordWrap(False)
                it.text_label.setFixedHeight(LIST_ICON + 4)
                it.text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                lay.addLayout(row)
                self.grid.addWidget(it, i, 0, Qt.AlignTop | Qt.AlignLeft)
            if self.items:
                self.grid.setRowStretch(len(self.items), 1)
        else:
            # 图标模式：网格
            self.grid.setHorizontalSpacing(0)
            cols = max(1, self.scroll.viewport().width() // self.cell_w)
            for i, it in enumerate(self.items):
                # 还原内部布局为上下
                lay = it.layout()
                while lay.count(): lay.takeAt(0)
                it.set_icon_px(self.icon_size)
                it.text_label.setWordWrap(True)
                it.text_label.setFixedHeight(self.cell_h - self.icon_size - 16)
                it.text_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
                col_row = QVBoxLayout()
                col_row.setContentsMargins(0, 0, 0, 0)
                col_row.setSpacing(2)
                col_row.addWidget(it.icon_label, 0, Qt.AlignHCenter)
                col_row.addWidget(it.text_label)
                lay.addLayout(col_row)
                it.setFixedSize(self.cell_w, self.cell_h)
                self.grid.addWidget(it, i // cols, i % cols,
                                    Qt.AlignTop | Qt.AlignLeft)
            rows = (len(self.items) + cols - 1) // cols
            self.grid.setRowStretch(rows, 1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_reflow_timer"): self._reflow_timer.start()
        if not self._collapsed: self.manager.schedule_save()

    # ---- 折叠 ----
    def toggle_collapse(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._saved_h = self.height()
            self.scroll.hide(); self.grip.hide()
            self.setMinimumHeight(0); self.setFixedHeight(TITLE_H + 4)
        else:
            self.setMinimumSize(200, TITLE_H + 60)
            self.setMaximumHeight(MAX_H)
            self.scroll.show()
            if not self.locked: self.grip.show()
            self.resize(self.width(), self._saved_h)
        self.titlebar.collapse_btn.setText("▸" if self._collapsed else "▾")
        self.manager.schedule_save()

    # ---- 右键菜单 ----
    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.addAction("新建格子").triggered.connect(
            lambda: self.manager.create_fence())
        m.addAction("新建便签").triggered.connect(
            lambda: self.manager.create_note())
        color_menu = m.addMenu("格子颜色")
        for name in FENCE_COLORS: color_menu.addAction(name)
        frame_menu = m.addMenu("边框样式")
        for name in FENCE_FRAMES: frame_menu.addAction(name)
        m.addSeparator()
        act_lock = m.addAction("锁定 / 解锁")
        act_del = m.addAction("删除此格子（文件放回桌面）")

        chosen = m.exec(e.globalPos())
        if chosen is act_lock:    self.toggle_lock()
        elif chosen is act_del:   self.manager.delete_fence(self)
        elif chosen is not None:
            if chosen.text() in FENCE_COLORS:
                self.color = FENCE_COLORS[chosen.text()]
                self.apply_theme(); self.manager.schedule_save()
            elif chosen.text() in FENCE_FRAMES:
                self.frame = chosen.text()
                self.update(); self.manager.schedule_save()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.titlebar.name_text(),
            "color": self.color,
            "frame": self.frame,
            "sort": self.sort,
            "view": self.view,
            "locked": self.locked,
            "x": self.x(), "y": self.y(),
            "w": self.width(),
            "h": self._saved_h if self._collapsed else self.height(),
            "collapsed": self._collapsed,
            "items": [it.path for it in self.items],
        }
