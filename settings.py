# -*- coding: utf-8 -*-
"""设置中心窗口 + 开机自启（注册表 Run 键）+ 数据目录迁移"""
import os
import shutil
import sys
import winreg

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from common import (DATA_DIR, DEFAULT_DATA_DIR, STORAGE_DIR,
                    set_data_dir_override)

APP_NAME = "DeskFence"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def ensure_autostart():
    """启动时自愈：配置里开着自启但注册表值丢失 / 路径变了，就补写回去"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            cur, _ = winreg.QueryValueEx(k, APP_NAME)
    except OSError:
        cur = ""
    if cur != _start_cmd():
        return set_autostart(True)
    return True


def _start_cmd():
    # 打包后直接指向 exe 自身；源码运行时用 pythonw 启动 main.py
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    exe = sys.executable
    wexe = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(wexe):
        exe = wexe
    here = os.path.dirname(os.path.abspath(__file__))
    return '"%s" "%s"' % (exe, os.path.join(here, "main.py"))


def get_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            val, _ = winreg.QueryValueEx(k, APP_NAME)
            return bool(val)
    except OSError:
        return False


def set_autostart(enable):
    """写入 / 删除开机启动项，返回是否成功"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _start_cmd())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass
    # 回读校验，确认真的写进去了
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            val, _ = winreg.QueryValueEx(k, APP_NAME)
            return bool(val) == enable
    except OSError:
        return not enable


class SettingsWindow(QWidget):
    """设置中心：全部显示勾选 + 开机自启 + 不透明度 + 图标大小"""

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.setWindowTitle("设置中心")
        self.setMinimumWidth(340)

        lay = QVBoxLayout(self)
        form = QFormLayout()

        # —— 全部显示/隐藏 ——
        self.chk_show = QCheckBox("显示全部格子与便签")
        self.chk_show.setChecked(manager.all_visible)
        self.chk_show.toggled.connect(self._on_show_toggled)
        manager.all_visible_changed.connect(self._update_show)
        form.addRow(self.chk_show)

        # —— 开机自启 ——
        self.chk_autostart = QCheckBox("开机自动启动")
        self.chk_autostart.setChecked(get_autostart())
        self.chk_autostart.toggled.connect(self._on_autostart)
        form.addRow(self.chk_autostart)

        # —— 格子不透明度 ——
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(60, 250)
        self.slider.setValue(manager.settings.get("fence_alpha", 170))
        self.lbl_alpha = QLabel(str(self.slider.value()))
        self.slider.valueChanged.connect(self._on_alpha)
        form.addRow("格子不透明度", self.slider)
        form.addRow("", self.lbl_alpha)

        # —— 图标大小 ——
        self.combo = QComboBox()
        self.combo.addItems(["32", "40", "48"])
        self.combo.setCurrentText(str(manager.settings.get("icon_size", 40)))
        self.combo.currentTextChanged.connect(self._on_icon_size)
        form.addRow("图标大小", self.combo)

        # —— 数据目录 ——
        self.dir_edit = QLineEdit(DATA_DIR)
        self.dir_edit.setReadOnly(True)
        self.btn_browse = QPushButton("更改…")
        self.btn_browse.clicked.connect(self._choose_dir)
        row = QHBoxLayout()
        row.addWidget(self.dir_edit, 1)
        row.addWidget(self.btn_browse)
        wrap = QWidget(); wrap.setLayout(row)
        form.addRow("数据目录", wrap)

        lay.addLayout(form)
        tip = QLabel("托盘图标双击 = 一键显示/隐藏全部")
        tip.setStyleSheet("color:#888;")
        lay.addWidget(tip)

    # —— 全部显示勾选 ——
    def _on_show_toggled(self, checked):
        self.manager.set_all_visible(checked)

    def _update_show(self, visible):
        # 防止触发信号再调用 set_all_visible 造成循环
        self.chk_show.blockSignals(True)
        self.chk_show.setChecked(visible)
        self.chk_show.blockSignals(False)

    # —— 其他 ——
    def _on_autostart(self, checked):
        ok = set_autostart(checked)
        self.manager.set_setting("autostart", checked)
        if checked and not ok:
            QMessageBox.warning(self, "开机自启", "写入启动项失败，请检查系统权限。")
        elif checked:
            QMessageBox.information(
                self, "开机自启",
                "已设为开机启动，将在下次登录 / 重启后生效。\n\n"
                "如果重启后仍未启动，请查看日志：\n%%APPDATA%%\\DeskFence\\startup.log")

    def _on_alpha(self, v):
        self.lbl_alpha.setText(str(v))
        self.manager.set_setting("fence_alpha", v)

    def _on_icon_size(self, s):
        self.manager.set_setting("icon_size", int(s))

    # —— 数据目录迁移 ——
    def _choose_dir(self):
        new_dir = QFileDialog.getExistingDirectory(
            self, "选择新的数据存放目录", DATA_DIR)
        if not new_dir:
            return
        new_dir = os.path.abspath(new_dir)
        if os.path.realpath(new_dir) == os.path.realpath(DATA_DIR):
            QMessageBox.information(self, "数据目录", "已经是当前目录。")
            return
        if os.path.exists(os.path.join(new_dir, "config.json")):
            ret = QMessageBox.question(
                self, "数据目录",
                "目标目录里已经有 DeskFence 的配置。\n\n"
                "是要**切换过去使用那套配置**，还是**把当前配置迁移过去**覆盖它？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes)
            if ret == QMessageBox.Cancel:
                return
            migrate = (ret == QMessageBox.No)
            # Yes = 切换（不改当前，只在默认位置的 config 里写 data_dir 指向新目录）
            # No  = 迁移（把当前内容复制过去覆盖）
        else:
            migrate = True

        if migrate:
            # 迁移：复制所有内容到新目录
            try:
                os.makedirs(new_dir, exist_ok=True)
                for name in os.listdir(DATA_DIR):
                    src = os.path.join(DATA_DIR, name)
                    dst = os.path.join(new_dir, name)
                    if os.path.isdir(src):
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                # 关键：把新目录 config.json 里指向旧 DATA_DIR 的路径改成新 DATA_DIR
                self._rewrite_item_paths(os.path.join(new_dir, "config.json"),
                                         os.path.join(DATA_DIR, "storage"),
                                         os.path.join(new_dir, "storage"))
            except OSError as e:
                QMessageBox.critical(
                    self, "迁移失败",
                    "复制到新目录时出错：\n\n%s\n\n"
                    "请检查目标目录是否有写入权限，或磁盘空间是否充足。" % e)
                return

        # 写入数据目录指向：注册表（权威）+ marker 文件 + config 字段（冗余）
        self._write_data_dir(new_dir)

        QMessageBox.information(
            self, "数据目录",
            "已设置为：\n%s\n\n"
            "请**关闭程序后重新打开**生效。\n"
            "重启后原位置的文件不会自动删除，确认新位置正常后可以手动清理。"
            % new_dir)

    def _rewrite_item_paths(self, cfg_path, old_storage, new_storage):
        """把 config.json 里所有以 old_storage 开头的路径替换成 new_storage 开头"""
        import json
        if not os.path.exists(cfg_path):
            return
        try:
            with open(cfg_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, ValueError):
            return
        old_storage_n = os.path.normpath(old_storage).lower()
        new_storage_n = os.path.normpath(new_storage)
        changed = 0
        for fence in data.get("fences", []):
            items = fence.get("items", [])
            new_items = []
            for p in items:
                # 同时兼容正斜杠和反斜杠
                p_norm = os.path.normpath(p).lower()
                if p_norm.startswith(old_storage_n + os.sep) or \
                   p_norm == old_storage_n:
                    rel = p[len(os.path.normpath(old_storage)):]
                    new_items.append(new_storage_n + rel)
                    changed += 1
                else:
                    new_items.append(p)
            fence["items"] = new_items
        if changed:
            with open(cfg_path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)

    def _write_data_dir(self, new_dir):
        """注册表为主，marker 文件与 config 字段为冗余备份"""
        import json

        set_data_dir_override(new_dir)

        def _patch(cfg_path):
            if not os.path.exists(cfg_path):
                return
            try:
                with open(cfg_path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
            except (OSError, ValueError):
                return
            data.setdefault("settings", {})["data_dir"] = new_dir
            with open(cfg_path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)

        _patch(os.path.join(DEFAULT_DATA_DIR, "config.json"))
        _patch(os.path.join(new_dir, "config.json"))
