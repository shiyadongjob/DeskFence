# -*- coding: utf-8 -*-
"""桌面收纳格子 —— 入口

模块划分：
- common.py    常量、颜色、工具函数
- storage.py   文件实体移动（拖入收纳 / 放回桌面）
- fence.py     收纳格子（图标项 + 标题栏 + 格子窗口）
- note.py      便签
- settings.py  设置中心 + 开机自启
- manager.py   托盘、格子/便签管理、配置持久化
"""
import os
import sys
import time
import traceback

from PySide6.QtCore import QSharedMemory, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from common import DATA_DIR, ICON_PATH
from manager import Manager
from settings import ensure_autostart


APP_ICON_PATH = ICON_PATH
LOG_PATH = os.path.join(DATA_DIR, "startup.log")


def log(msg):
    """启动日志：打包后没有控制台，出问题靠它定位"""
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 300_000:
            os.remove(LOG_PATH)
        with open(LOG_PATH, "a", encoding="utf-8") as fp:
            fp.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def main():
    log("启动 exe=%s argv=%s" % (sys.executable, sys.argv))
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei", 9))

    # 加载自定义图标（任务栏、窗口、托盘通用）
    if os.path.exists(APP_ICON_PATH):
        icon = QIcon(APP_ICON_PATH)
        app.setWindowIcon(icon)
    log("QApplication 就绪")

    # 单实例：已有实例在运行时直接退出，避免多进程互相覆盖配置
    shm = QSharedMemory("deskfence_single_instance")
    if shm.attach() or not shm.create(1):
        log("检测到已有实例在运行，本实例退出")
        sys.exit(0)

    manager = Manager(app)
    log("界面就绪：格子 %d 个 / 便签 %d 个"
        % (len(manager.fences), len(manager.notes)))

    # 开机自启自愈：配置里开着，但启动项被删 / exe 换了位置，就补写回去
    if manager.settings.get("autostart"):
        ok = ensure_autostart()
        log("启动项自检：%s" % ("正常" if ok else "写入失败"))
    if "--smoke" in sys.argv:  # 冒烟测试：启动后自动退出
        QTimer.singleShot(1500, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        log("启动异常:\n" + traceback.format_exc())
        raise
