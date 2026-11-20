# -*- coding: utf-8 -*-
"""托盘 + 格子/便签管理 + 配置持久化"""
import json
import os

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QStyle, QSystemTrayIcon

from common import (CONFIG_PATH, DEFAULT_SETTINGS, ICON_PATH, STORAGE_DIR,
                    attach_to_desktop, detach_from_desktop)
from fence import Fence
from note import Note
from settings import SettingsWindow

APP_ICON_PATH = ICON_PATH


class Manager(QObject):
    """管理所有格子和便签 + 托盘 + 设置 + 持久化"""

    # 信号：全部可见状态变化（给设置中心的勾选框用）
    all_visible_changed = Signal(bool)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.fences = []
        self.notes = []
        self.settings = dict(DEFAULT_SETTINGS)
        self._settings_win = None
        self._save_timer = QTimer(self, singleShot=True, interval=500,
                                  timeout=self.save)
        # 桌面层级守护：Explorer 重启会重建桌面层，每 3 秒检查并重新挂载。
        # 正常情况下 GetParent 已正确，函数内零操作、不闪烁。
        self._z_timer = QTimer(self, interval=3000,
                               timeout=self._ensure_desktop_attach)
        self.all_visible = True
        self._build_tray()
        self._z_timer.start()
        self.load()
        # 冷启动时 Qt 对刚 setParent 到桌面层的窗口不会立即建立完整的
        # hover/鼠标进入事件状态。事件循环起来后重放一次 hide→show，
        # 等价于用户手动"隐藏全部→显示全部"，恢复图标经过/选中高亮。
        QTimer.singleShot(200, self._polish_hover)
        app.aboutToQuit.connect(self.save)
        app.aboutToQuit.connect(self._on_quit)

    def _polish_hover(self):
        """启动后重建一次窗口事件分发，恢复图标 hover/选中状态。"""
        visibles = [w for w in self.fences + self.notes if w.isVisible()]
        if not visibles:
            return
        for w in visibles:
            w.hide()
            w.show()
        # show 之后重新挂载并抬升，保持桌面层级正确
        attach_to_desktop(visibles, force_raise=True)

    def _on_quit(self):
        """退出前停止守护并解除桌面挂载，否则 Qt 事件循环无法结束。"""
        try:
            self._z_timer.stop()
            detach_from_desktop(self.fences + self.notes)
        except Exception:
            pass

    # ---- 托盘 ----
    def _build_tray(self):
        # 优先用自定义图标，没找到就 fallback 到系统桌面图标
        if os.path.exists(APP_ICON_PATH):
            icon = QIcon(APP_ICON_PATH)
        else:
            icon = self.app.style().standardIcon(QStyle.SP_DesktopIcon)
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip("桌面收纳")
        self._tray_menu = QMenu()
        self._tray_menu.addAction("新建格子").triggered.connect(
            lambda: self.create_fence())
        self._tray_menu.addAction("新建便签").triggered.connect(
            lambda: self.create_note())
        self._tray_menu.addAction("设置中心").triggered.connect(self.show_settings)
        self._tray_menu.addSeparator()
        self.act_toggle = self._tray_menu.addAction("隐藏全部")
        self.act_toggle.triggered.connect(self._toggle_from_tray)
        self.all_visible_changed.connect(self._update_toggle_text)
        self._tray_menu.addSeparator()
        self._tray_menu.addAction("退出").triggered.connect(self.app.quit)
        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(self._on_tray)
        self.tray.show()

    def _on_tray(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.set_all_visible(not self.all_visible)

    def _toggle_from_tray(self):
        self.set_all_visible(not self.all_visible)

    def _update_toggle_text(self, visible):
        self.act_toggle.setText("隐藏全部" if visible else "显示全部")

    def _ensure_desktop_attach(self):
        """确保所有窗口都挂在桌面层下（Explorer 重启后自动重新挂载）。"""
        try:
            attach_to_desktop(self.fences + self.notes)
        except Exception:
            pass

    def _attach_new(self, w):
        """新窗口/恢复显示的窗口挂到桌面层并抬到最上方，避免被旧格子挡住。"""
        try:
            attach_to_desktop(w, force_raise=True)
            # 原生句柄可能晚一帧才就绪，补一次
            QTimer.singleShot(0, lambda: attach_to_desktop(w, force_raise=True))
        except Exception:
            pass

    def set_all_visible(self, visible):
        """统一入口：设置全部可见状态，通知所有监听者"""
        self.all_visible = visible
        for w in self.fences + self.notes:
            w.setVisible(visible)
        self.all_visible_changed.emit(visible)
        self.schedule_save()
        for w in self.fences + self.notes:
            if w.isVisible():
                self._attach_new(w)

    # ---- 设置中心 ----
    def show_settings(self):
        if self._settings_win is None:
            self._settings_win = SettingsWindow(self)
            self._settings_win.setAttribute(Qt.WA_DeleteOnClose)
            self._settings_win.destroyed.connect(self._on_settings_closed)
        self._settings_win.show()
        self._settings_win.raise_()
        self._settings_win.activateWindow()

    def _on_settings_closed(self):
        self._settings_win = None

    def set_setting(self, key, value):
        self.settings[key] = value
        self.schedule_save()
        for f in self.fences:
            if key == "icon_size":
                f.rebuild()
            else:
                f.apply_theme()

    # ---- 格子/便签 ----
    def create_fence(self, **kw):
        f = Fence(self, **kw)
        self.fences.append(f)
        # 与全局可见状态保持一致：隐藏全部时新建的格子也不该突然冒出来
        f.setVisible(self.all_visible)
        self._attach_new(f)
        self.schedule_save()
        return f

    def delete_fence(self, f):
        if f in self.fences:
            f.release_all()  # 收纳的文件全部放回桌面
            self.fences.remove(f)
            f.close()
            f.deleteLater()
            self.schedule_save()

    def create_note(self, **kw):
        n = Note(self, **kw)
        self.notes.append(n)
        n.setVisible(self.all_visible)
        self._attach_new(n)
        self.schedule_save()
        return n

    def delete_note(self, n):
        if n in self.notes:
            self.notes.remove(n)
            n.close()
            n.deleteLater()
            self.schedule_save()

    # ---- 持久化 ----
    def schedule_save(self):
        self._save_timer.start()

    def save(self):
        data = {
            "settings": self.settings,
            "all_visible": self.all_visible,
            "fences": [f.to_dict() for f in self.fences],
            "notes": [n.to_dict() for n in self.notes],
        }
        try:
            # 备份上一版，防止双实例/崩溃/覆盖丢失
            if os.path.exists(CONFIG_PATH):
                bak = CONFIG_PATH + ".bak"
                try:
                    if os.path.exists(bak):
                        os.remove(bak)
                    os.rename(CONFIG_PATH, bak)
                except OSError:
                    pass
            with open(CONFIG_PATH, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def load(self):
        data = None
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
            except (OSError, ValueError):
                data = None
        if data:
            self.settings.update(data.get("settings", {}))
            self.all_visible = data.get("all_visible", True)
            for fd in data.get("fences", []):
                self.create_fence(
                    name=fd.get("name", "格子"),
                    items=fd.get("items", []),
                    geo=(fd.get("x", 100), fd.get("y", 100),
                         fd.get("w", 360), fd.get("h", 300)),
                    collapsed=fd.get("collapsed", False),
                    color=fd.get("color", "深灰"),
                    frame=fd.get("frame", "简约描边"),
                    sort=fd.get("sort", "manual"),
                    view=fd.get("view", "icon"),
                    locked=fd.get("locked", False),
                    fence_id=fd.get("id"),
                )
            for nd in data.get("notes", []):
                self.create_note(
                    html=nd.get("html", ""),
                    geo=(nd.get("x", 520), nd.get("y", 160),
                         nd.get("w", 240), nd.get("h", 200)),
                    color=nd.get("color", "黄"),
                )
        # storage 自愈：config 丢了但收纳目录还在，每个孤儿目录自动建一个格子
        known = {f.id for f in self.fences}
        if os.path.isdir(STORAGE_DIR):
            for name in sorted(os.listdir(STORAGE_DIR)):
                p = os.path.join(STORAGE_DIR, name)
                if not os.path.isdir(p):
                    continue
                if name in known:
                    continue
                # 这个目录没登记过，把里面的文件挂成新格子
                items = []
                for entry in os.listdir(p):
                    ep = os.path.join(p, entry)
                    if os.path.isdir(ep) or os.path.isfile(ep):
                        items.append(ep)
                if not items:
                    continue
                self.create_fence(
                    name="恢复格子 %s" % name[:6],
                    items=items,
                    fence_id=name,
                )
                known.add(name)
        # 什么内容都没有时给一个起始格子，避免程序启动后"看不见"
        if not self.fences and not self.notes:
            self.create_fence(name="默认格子")
        # 应用保存的可见性（默认都是 show() 的；如果 all_visible=False 要再隐藏）
        self.set_all_visible(self.all_visible)
