# -*- coding: utf-8 -*-
"""公共常量与工具"""
import ctypes
import json
import os
import sys
import winreg
from ctypes import wintypes

from PySide6.QtCore import QFileInfo, QSize
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QWindow
from PySide6.QtWidgets import QFileIconProvider

FROZEN = bool(getattr(sys, "frozen", False))

# 资源目录：syd.png 等随程序打包的只读资源（打包后位于 PyInstaller 临时目录）
RESOURCE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(RESOURCE_DIR, "syd.png")

# 数据目录默认值（config.json + storage）
if FROZEN:
    DEFAULT_DATA_DIR = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "DeskFence")
else:
    DEFAULT_DATA_DIR = os.path.dirname(os.path.abspath(__file__))


REG_KEY = r"Software\DeskFence"


def set_data_dir_override(path):
    """把自定义数据目录写入注册表（权威）+ 默认位置 marker 文件（冗余）"""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            winreg.SetValueEx(k, "DataDir", 0, winreg.REG_SZ, path)
    except OSError:
        pass
    try:
        with open(os.path.join(DEFAULT_DATA_DIR, "data_dir.txt"), "w",
                  encoding="utf-8") as fp:
            fp.write(path)
    except OSError:
        pass


def _resolve_data_dir():
    r"""启动时决定数据目录（按优先级）：
    1. 注册表 HKCU\Software\DeskFence\DataDir
    2. 默认位置的 data_dir.txt marker
    3. 默认位置 config.json 的 settings.data_dir
    4. 默认位置
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            alt, _ = winreg.QueryValueEx(k, "DataDir")
            if alt and os.path.isdir(alt):
                return alt
    except OSError:
        pass
    marker = os.path.join(DEFAULT_DATA_DIR, "data_dir.txt")
    if os.path.exists(marker):
        try:
            with open(marker, "r", encoding="utf-8") as fp:
                alt = fp.read().strip()
            if alt and os.path.isdir(alt):
                return alt
        except OSError:
            pass
    cfg = os.path.join(DEFAULT_DATA_DIR, "config.json")
    if os.path.exists(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as fp:
                d = json.load(fp)
            alt = d.get("settings", {}).get("data_dir")
            if alt and os.path.isdir(alt):
                return alt
        except (OSError, ValueError):
            pass
    return DEFAULT_DATA_DIR


DATA_DIR = _resolve_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
STORAGE_DIR = os.path.join(DATA_DIR, "storage")

TITLE_H = 42      # 加大标题栏，给鼠标更多命中空间
EDGE_HIT = 8      # 边缘 resize 检测宽度

MAX_H = 16777215  # QWIDGETSIZE_MAX

# 格子底色：深色 + 浅色 + 彩色
FENCE_COLORS = {
    # 深色系
    "深灰": "#191c22",
    "深蓝": "#162232",
    "深绿": "#162e26",
    "深紫": "#261c34",
    "深红": "#341a1e",
    "深橙": "#3a2414",
    "深青": "#0f2a2a",
    # 浅色系
    "浅灰": "#e8e8e8",
    "米白": "#f5f0e2",
    "浅蓝": "#d3e2f5",
    "浅绿": "#d8f0dd",
    "浅粉": "#f5d8e2",
    "浅紫": "#e4d5f0",
    "浅黄": "#fef3c7",
    # 彩色系
    "橙色": "#fb923c",
    "青色": "#22d3ee",
    "翠绿": "#10b981",
    "玫红": "#ec4899",
}

# 边框样式（在 fence.py paintEvent 里按 type 分支绘制）
# type: simple / glow / neon / topbar / thick / glass / corners
FENCE_FRAMES = {
    "简约描边":   dict(type="simple",  radius=12, border_w=1),
    "大圆角":     dict(type="simple",  radius=20, border_w=1),
    "直角":       dict(type="simple",  radius=0,  border_w=1),
    "加粗":       dict(type="simple",  radius=12, border_w=3),
    "发光":       dict(type="glow",    radius=14, border_w=2, glow=18),
    "霓虹":       dict(type="neon",    radius=14, border_w=2, glow=24),
    "顶部彩条":   dict(type="topbar",  radius=12, border_w=1, bar_h=4),
    "玻璃":       dict(type="glass",   radius=14, border_w=1),
    "角落装饰":   dict(type="corners", radius=12, border_w=2),
    "虚线":       dict(type="dashed",  radius=12, border_w=2),
    "无边框":     dict(type="simple",  radius=12, border_w=0),
}

NOTE_COLORS = {
    "黄": "#ffe082",
    "绿": "#a5d6a7",
    "蓝": "#90caf9",
    "粉": "#f48fb1",
    "紫": "#b39ddb",
    "橙": "#ffcc80",
    "青": "#80deea",
}

# 排序方式
SORTS = {
    "手动": "manual",
    "按名称": "name",
    "按类型": "type",
}

# 视图模式
VIEWS = {
    "图标": "icon",
    "列表": "list",
}

DEFAULT_SETTINGS = {
    "autostart": False,
    "fence_alpha": 170,
    "icon_size": 40,
}

_icon_provider = QFileIconProvider()


def is_light(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6


def frame_info(style_name):
    return FENCE_FRAMES.get(style_name, FENCE_FRAMES["简约描边"])


def cell_size(icon_size):
    return icon_size + 44, icon_size + 52


def file_pixmap(path, size):
    icon = _icon_provider.icon(QFileInfo(path))
    if icon.isNull():
        icon = _icon_provider.icon(
            QFileIconProvider.Folder if os.path.isdir(path) else QFileIconProvider.File)
    return icon.pixmap(QSize(size, size))


def display_name(path):
    base = os.path.basename(path.rstrip("\\/")) or path
    stem, ext = os.path.splitext(base)
    return stem if ext.lower() == ".lnk" else base


def desktop_path():
    try:
        fid = ctypes.c_buffer(16)
        fid.raw = bytes.fromhex("3ACCBFB42CDB4C42B0297FE99A87C641")
        ptr = wintypes.LPWSTR()
        ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(fid), 0, None, ctypes.byref(ptr))
        path = ptr.value
        ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(ptr, ctypes.c_void_p))
        if path:
            return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


# ---- Win32 边缘 hit test ----
WM_NCHITTEST = 0x0084
HTLEFT = 10; HTRIGHT = 11; HTTOP = 12; HTTOPLEFT = 13; HTTOPRIGHT = 14
HTBOTTOM = 15; HTBOTTOMLEFT = 16; HTBOTTOMRIGHT = 17


def hit_test_rect(widget, pos):
    """返回边缘 resize 命中值；None 表示不命中。pos 是窗口本地坐标。"""
    r = widget.rect()
    m = EDGE_HIT
    x, y = pos.x(), pos.y()
    hit_left   = x <= m
    hit_right  = x >= r.width() - m
    hit_top    = y <= m
    hit_bottom = y >= r.height() - m
    if hit_top and hit_left:       return HTTOPLEFT
    if hit_top and hit_right:      return HTTOPRIGHT
    if hit_bottom and hit_left:    return HTBOTTOMLEFT
    if hit_bottom and hit_right:   return HTBOTTOMRIGHT
    if hit_left:    return HTLEFT
    if hit_right:   return HTRIGHT
    if hit_top:     return HTTOP
    if hit_bottom:  return HTBOTTOM
    return None


# ---- Win32 桌面层级：把窗口挂成桌面子窗口（与桌面图标同层） ----
# 目标：格子/便签始终显示在桌面上，但位于浏览器/IDE/文件夹等普通窗口之下；
# 且任务栏"显示桌面"、Win+D 时不会消失。
# 做法：SetParent 到桌面窗口（持有 SHELLDLL_DefView 的 WorkerW，找不到则
# Progman）成为子窗口。桌面子窗口天然满足上述层级，不依赖 WS_EX_TOPMOST。

GW_CHILD = 5
GA_PARENT = 1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SW_SHOW = 5
HWND_TOP = 0

_z_user32 = ctypes.WinDLL("user32", use_last_error=True)
_z_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_z_user32.FindWindowW.restype = wintypes.HWND
_z_user32.FindWindowExW.argtypes = [
    wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
_z_user32.FindWindowExW.restype = wintypes.HWND
_z_user32.GetParent.argtypes = [wintypes.HWND]
_z_user32.GetParent.restype = wintypes.HWND
_z_user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
_z_user32.SetParent.restype = wintypes.HWND
_z_user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
_z_user32.GetAncestor.restype = wintypes.HWND
_z_user32.IsWindow.argtypes = [wintypes.HWND]
_z_user32.IsWindow.restype = wintypes.BOOL
_z_user32.IsIconic.argtypes = [wintypes.HWND]
_z_user32.IsIconic.restype = wintypes.BOOL
_z_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_z_user32.ShowWindow.restype = wintypes.BOOL
_z_user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT]
_z_user32.SetWindowPos.restype = wintypes.BOOL


def _hwnd_int(v):
    return int(v) if v else 0


def get_desktop_parent():
    """返回桌面层 HWND：优先持有 SHELLDLL_DefView 的 WorkerW，否则 Progman。"""
    progman = _hwnd_int(_z_user32.FindWindowW("Progman", None))
    if progman and _hwnd_int(_z_user32.FindWindowExW(
            progman, 0, "SHELLDLL_DefView", None)):
        return progman
    worker = 0
    for _ in range(256):
        worker = _hwnd_int(_z_user32.FindWindowExW(0, worker, "WorkerW", None))
        if not worker:
            break
        if _hwnd_int(_z_user32.FindWindowExW(
                worker, 0, "SHELLDLL_DefView", None)):
            return worker
    return progman


# 桌面父窗口的 QWindow 包装：必须缓存，避免重复 fromWinId 造成句柄失效
_desktop_qwindow = None
_desktop_qwindow_hwnd = 0


def _get_desktop_qwindow():
    """返回桌面层窗口的 QWindow 包装（缓存）。"""
    global _desktop_qwindow, _desktop_qwindow_hwnd
    hwnd = get_desktop_parent()
    if not hwnd:
        return None
    if _desktop_qwindow is None or _desktop_qwindow_hwnd != hwnd:
        try:
            _desktop_qwindow = QWindow.fromWinId(hwnd)
            _desktop_qwindow_hwnd = hwnd
        except Exception:
            return None
    return _desktop_qwindow


def attach_to_desktop(widgets, force_raise=False):
    """用 Qt 原生 setParent 把窗口挂到桌面层（与桌面图标同层）。

    widgets: QWidget 或 QWidget 列表。
    关键：必须用 Qt 的 windowHandle().setParent()，不能用 Win32 SetParent。
    否则 Qt 仍认为窗口是顶层，冷启动时坐标映射/鼠标命中会错乱，
    只有 hide→show 重走一遍流程才恢复。

    桌面窗口位于 (0,0)，所以窗口的相对坐标与屏幕坐标一致，位置不会偏移。
    force_raise: 新建/恢复显示时传 True，把窗口抬到桌面子窗口 Z 序顶部，
                 避免被同位置旧格子挡住。
    """
    if widgets is None:
        return
    if not isinstance(widgets, (list, tuple)):
        widgets = [widgets]
    parent_qw = _get_desktop_qwindow()
    if parent_qw is None:
        return
    for w in widgets:
        try:
            wh = w.windowHandle()
            if wh is None:
                continue
            need_raise = bool(force_raise)
            if wh.parent() is not parent_qw:
                wh.setParent(parent_qw)
                need_raise = True
            if need_raise:
                hwnd = int(wh.winId())
                # 抬到桌面子窗口顶部：在图标/旧格子之上，
                # 但因是桌面子窗口，仍在所有普通应用窗口之下
                _z_user32.SetWindowPos(
                    hwnd, HWND_TOP, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            continue


def detach_from_desktop(widgets):
    """退出前解除桌面挂载。

    fromWinId 包装的桌面窗口若仍作为父窗口，Qt 事件循环会无法正常退出
    （app.quit() 卡住）。退出前必须把所有子窗口 setParent(None)。
    """
    global _desktop_qwindow, _desktop_qwindow_hwnd
    if widgets is None:
        widgets = []
    if not isinstance(widgets, (list, tuple)):
        widgets = [widgets]
    for w in widgets:
        try:
            wh = w.windowHandle()
            if wh is not None:
                wh.setParent(None)
        except Exception:
            continue
    _desktop_qwindow = None
    _desktop_qwindow_hwnd = 0

