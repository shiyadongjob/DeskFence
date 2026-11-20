# -*- coding: utf-8 -*-
"""格子文件的物理移动：拖入收纳目录、放回桌面"""
import os
import shutil

from common import STORAGE_DIR, desktop_path


def _unique(dest_dir, name):
    """重名时自动加 (1)(2) 后缀"""
    stem, ext = os.path.splitext(name)
    candidate = os.path.join(dest_dir, name)
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, "%s (%d)%s" % (stem, n, ext))
        n += 1
    return candidate


def fence_dir(fence_id):
    return os.path.join(STORAGE_DIR, fence_id)


def is_in_storage(path):
    """路径是否位于收纳目录内（区分实体收纳与历史引用）"""
    try:
        return os.path.commonpath(
            [os.path.abspath(path), os.path.abspath(STORAGE_DIR)]
        ) == os.path.abspath(STORAGE_DIR)
    except ValueError:
        return False


def move_into(fence_id, src):
    """把文件移入指定格子的收纳目录，返回新路径；失败返回 None"""
    try:
        d = fence_dir(fence_id)
        os.makedirs(d, exist_ok=True)
        dst = _unique(d, os.path.basename(src))
        shutil.move(src, dst)
        return dst
    except (OSError, shutil.Error):
        return None


def release(path):
    """把文件移回桌面，返回新路径；失败返回 None"""
    try:
        dst = _unique(desktop_path(), os.path.basename(path))
        shutil.move(path, dst)
        return dst
    except (OSError, shutil.Error):
        return None


def release_dir(fence_id):
    """把格子收纳目录里所有内容放回桌面，并删除该目录"""
    d = fence_dir(fence_id)
    if os.path.isdir(d):
        for name in os.listdir(d):
            release(os.path.join(d, name))
        shutil.rmtree(d, ignore_errors=True)
