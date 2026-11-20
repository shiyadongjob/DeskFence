# -*- coding: utf-8 -*-
"""调用 Windows 原生文件右键菜单（与桌面 / 资源管理器一致）

直接用 ctypes 调 IContextMenu，不依赖第三方库。
"""
import ctypes
from ctypes import (POINTER, Structure, byref, c_char_p, c_int, c_uint,
                    c_uint16, c_uint32, c_ubyte, c_void_p, c_wchar_p, cast)

import win32con
import win32gui

shell32 = ctypes.windll.shell32
ole32 = ctypes.windll.ole32

# QueryContextMenu 标志：常规项 + 扩展项
CMF_NORMAL_EXTENDED = 0x00000100
ID_CMD_FIRST = 1


class GUID(Structure):
    _fields_ = [("Data1", c_uint32), ("Data2", c_uint16), ("Data3", c_uint16),
                ("Data4", c_ubyte * 8)]


def _guid(text):
    g = GUID()
    ole32.IIDFromString(c_wchar_p(text), byref(g))
    return g


IID_IShellFolder = _guid("{000214E6-0000-0000-C000-000000000046}")
IID_IContextMenu = _guid("{000214E4-0000-0000-C000-000000000046}")


class CMINVOKECOMMANDINFO(Structure):
    _fields_ = [("cbSize", c_uint32), ("fMask", c_uint32), ("hwnd", c_void_p),
                ("lpVerb", c_void_p), ("lpParameters", c_void_p),
                ("lpDirectory", c_void_p), ("nShow", c_int),
                ("dwHotKey", c_uint32), ("hIcon", c_void_p)]


def _method(punk, index, *argtypes):
    """取 COM 接口虚表第 index 个方法"""
    vtbl = cast(punk, POINTER(POINTER(c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, *argtypes)
    return proto(vtbl[index])


def _release(punk):
    if punk:
        _method(punk, 2)(punk)


def build_menu(path, hwnd, flags=CMF_NORMAL_EXTENDED):
    """返回 (hmenu, pcm, psf, pidl) 或 None"""
    pidl = c_void_p()
    if shell32.SHParseDisplayName(c_wchar_p(path), None, byref(pidl), 0, None) != 0:
        return None

    psf = c_void_p()
    child = c_void_p()
    if shell32.SHBindToParent(pidl, byref(IID_IShellFolder),
                              byref(psf), byref(child)) != 0:
        ole32.CoTaskMemFree(pidl)
        return None

    pcm = c_void_p()
    apidl = (c_void_p * 1)(child)
    get_ui = _method(psf, 10, c_void_p, c_uint, POINTER(c_void_p),
                     POINTER(GUID), c_uint, POINTER(c_void_p))
    hr = get_ui(psf, hwnd, 1, cast(apidl, POINTER(c_void_p)),
                byref(IID_IContextMenu), 0, byref(pcm))
    if hr != 0 or not pcm:
        _release(psf)
        ole32.CoTaskMemFree(pidl)
        return None

    hmenu = win32gui.CreatePopupMenu()
    query = _method(pcm, 3, c_void_p, c_uint, c_uint, c_uint, c_uint)
    query(pcm, hmenu, 0, ID_CMD_FIRST, 0x7FFF, flags)
    return hmenu, pcm, psf, pidl


def get_verb(pcm, offset):
    """取命令对应的规范动词（open / edit / copy / delete …）

    offset = 菜单项 ID - idCmdFirst，GetCommandString 认这个偏移量。
    """
    if offset < 0:
        return ""
    buf = ctypes.create_string_buffer(256)
    fn = _method(pcm, 5, ctypes.c_size_t, c_uint, c_void_p, c_char_p, c_uint)
    if fn(pcm, offset, 0, None, buf, 256) != 0:      # GCS_VERBA
        return ""
    return buf.value.decode("mbcs", "ignore")

def invoke(pcm, hwnd, offset, verb=""):
    """执行菜单命令

    优先用规范动词（如 "edit"）执行，彻底避免偏移量换算错位；
    少数没有动词的项（属性等）回退成偏移量。
    """
    info = CMINVOKECOMMANDINFO()
    info.cbSize = ctypes.sizeof(CMINVOKECOMMANDINFO)
    info.hwnd = hwnd
    buf = None
    if verb:
        buf = ctypes.create_string_buffer(verb.encode("mbcs"))
        info.lpVerb = ctypes.cast(buf, c_void_p)
    else:
        info.lpVerb = offset
    info.nShow = win32con.SW_SHOWNORMAL
    call = _method(pcm, 4, POINTER(CMINVOKECOMMANDINFO))
    return call(pcm, byref(info))


def release_menu(hmenu, pcm, psf, pidl):
    win32gui.DestroyMenu(hmenu)
    _release(pcm)
    _release(psf)
    ole32.CoTaskMemFree(pidl)


def show_shell_menu(path, hwnd, pos):
    """在屏幕坐标 pos 处弹出系统右键菜单，成功返回 True"""
    built = build_menu(path, hwnd)
    if not built:
        return False
    hmenu, pcm, psf, pidl = built
    try:
        win32gui.SetForegroundWindow(hwnd)
        cmd = win32gui.TrackPopupMenu(
            hmenu, win32con.TPM_RETURNCMD | win32con.TPM_RIGHTBUTTON,
            pos.x(), pos.y(), 0, hwnd, None)
        if cmd:
            offset = cmd - ID_CMD_FIRST
            invoke(pcm, hwnd, offset, get_verb(pcm, offset))
        return True
    finally:
        release_menu(hmenu, pcm, psf, pidl)
