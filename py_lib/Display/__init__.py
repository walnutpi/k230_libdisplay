"""
将图像显示到屏幕上的库
"""

import ctypes
import time
import numpy as np
from typing import Tuple
import cv2

from ._bindings import (
    display_init as _c_init,
    display_exit as _c_exit,
    display_get_plane as _c_get_plane,
    display_free_plane as _c_free_plane,
    display_allocate_buffer as _c_alloc_buf,
    display_free_buffer as _c_free_buf,
    display_commit_buffer_noblock as _c_commit_noblock,
    wait_vblank as _c_wait_vblank,
    ROTATION_0, ROTATION_90, ROTATION_180, ROTATION_270,
    DRM_FORMAT_ARGB8888, DRM_FORMAT_BGR888, DRM_FORMAT_RGB888,
)

# ── 模块级全局状态 ────────────────────────────────────────

_display = None
_plane = None

# 两组双缓冲
_port_buf: list = []
_land_buf: list = []

_front = 0
_initialized = False
_w = 0
_h = 0

# BGR888 模式：无需通道转换，直接 memcpy
_bgr888 = False

# ARGB8888 回退：需要缓存数组做 BGR→BGRA 转换
_port_work = None
_port_dst_base: list = []
_land_work = None
_land_dst_base: list = []

_rotation = ROTATION_0
_actual_rotation = ROTATION_0
_rotation_offset = 0


def init() -> None:
    """初始化屏幕"""
    global _display, _plane, _front, _initialized, _bgr888
    global _w, _h, _port_buf, _land_buf, _rotation, _actual_rotation, _rotation_offset
    global _port_work, _port_dst_base, _land_work, _land_dst_base

    if _initialized:
        return

    _display = _c_init(0)

    # 优先 24-bit 格式：RGB888 → BGR888 → ARGB8888 回退
    _plane = _c_get_plane(_display, DRM_FORMAT_RGB888)
    if _plane:
        _bgr888 = True
    else:
        _plane = _c_get_plane(_display, DRM_FORMAT_BGR888)
        if _plane:
            _bgr888 = True
        else:
            _plane = _c_get_plane(_display, DRM_FORMAT_ARGB8888)
            _bgr888 = False

    _w = _display.contents.width
    _h = _display.contents.height
    is_portrait = (_w < _h)
    _rotation_offset = 1 if is_portrait else 0

    # ── 竖屏双缓冲 ──
    for _ in range(2):
        b = _c_alloc_buf(_plane, _w, _h)
        ctypes.memset(b.contents.map, 0, b.contents.size)
        b.contents.drm_rotation = ROTATION_0
        _port_buf.append(b)
        if not _bgr888:
            _port_dst_base.append(
                ctypes.cast(b.contents.map, ctypes.POINTER(ctypes.c_uint8)))

    # ── 横屏双缓冲 ──
    for _ in range(2):
        b = _c_alloc_buf(_plane, _h, _w)
        ctypes.memset(b.contents.map, 0, b.contents.size)
        b.contents.drm_rotation = ROTATION_90
        _land_buf.append(b)
        if not _bgr888:
            _land_dst_base.append(
                ctypes.cast(b.contents.map, ctypes.POINTER(ctypes.c_uint8)))

    # ARGB8888 回退：预分配缓存数组
    if not _bgr888:
        _port_work = np.empty((_h, _w, 4), dtype=np.uint8)
        _land_work = np.empty((_w, _h, 4), dtype=np.uint8)

    # 首帧：noblock 提交 + 等一个 vblank
    _rotation = ROTATION_0
    # 用户 0°（逆时针语义）→ 硬件 rotation，叠加物理偏移
    _actual_rotation = ((4 - ROTATION_0) % 4 + _rotation_offset) % 4
    if _actual_rotation in (ROTATION_90, ROTATION_270):
        _c_commit_noblock(_land_buf[0], 0, 0)
    else:
        _c_commit_noblock(_port_buf[0], 0, 0)
    _c_wait_vblank(_display.contents.fd)

    _front = 0
    _initialized = True
    print(f"[Display] init: {'BGR888 (fast)' if _bgr888 else 'ARGB8888 (fallback)'} "
          f"{_w}x{_h} portrait={is_portrait}")


def show(img: np.ndarray) -> None:
    """显示图像
    参数:
        img: opencv格式的图像(bgr排列)
    返回:
        None
    """
    global _front

    if not _initialized:
        raise RuntimeError("Display 未初始化，请先调用 init()")

    if img.ndim != 3 or img.shape[2] not in (3, 4):
        raise ValueError(f"图像必须是 (H, W, 3) 或 (H, W, 4) 格式，当前 shape={img.shape}")
    if img.dtype != np.uint8:
        raise ValueError(f"图像数据类型必须为 uint8，当前为 {img.dtype}")

    h, w = img.shape[:2]
    swap = (_actual_rotation == ROTATION_90 or _actual_rotation == ROTATION_270)

    if swap:
        target_w, target_h = _h, _w
        bufs = _land_buf
        work = _land_work
        dst_list = _land_dst_base
    else:
        target_w, target_h = _w, _h
        bufs = _port_buf
        work = _port_work
        dst_list = _port_dst_base

    # ── 自动缩放：如果输入图像尺寸不匹配，用 OpenCV resize ──
    if w != target_w or h != target_h:
        img = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        h, w = target_h, target_w

    t0 = time.perf_counter()

    if _bgr888:
        # ── BGR888 快速路径：直接 memcpy，零转换 ──
        dst = ctypes.cast(bufs[1 - _front].contents.map,
                          ctypes.POINTER(ctypes.c_uint8))
        src = ctypes.cast(img.ctypes.data, ctypes.POINTER(ctypes.c_uint8))
        ctypes.memmove(dst, src, h * w * 3)
    else:
        # ── ARGB8888 回退：通道转换 + memcpy ──
        dst = dst_list[1 - _front]
        if img.shape[2] == 3:
            work[:, :, 0] = img[:, :, 0]
            work[:, :, 1] = img[:, :, 1]
            work[:, :, 2] = img[:, :, 2]
            work[:, :, 3] = 0xFF
        else:
            work[:, :, 0] = img[:, :, 0]
            work[:, :, 1] = img[:, :, 1]
            work[:, :, 2] = img[:, :, 2]
            work[:, :, 3] = img[:, :, 3]
        src = ctypes.cast(work.ctypes.data, ctypes.POINTER(ctypes.c_uint8))
        ctypes.memmove(dst, src, h * w * 4)

    t1 = time.perf_counter()

    _c_commit_noblock(bufs[1 - _front], 0, 0)
    t2 = time.perf_counter()

    _front = 1 - _front

    # if _front == 0:
    #     print(f"[perf] write={(t1-t0)*1000:.1f}ms  commit={(t2-t1)*1000:.1f}ms  "
    #           f"total={(t2-t0)*1000:.1f}ms")


def _ensure_init() -> None:
    """确保 Display 已初始化，否则抛出异常"""
    if not _initialized:
        raise RuntimeError("Display 未初始化，请先调用 init()")


def flush() -> None:
    """等待最后一帧完成（程序退出前调用）"""
    _c_wait_vblank(_display.contents.fd)


def get_width() -> int:
    """获取屏幕物理宽度
    返回:
        屏幕宽度（像素）
    """
    _ensure_init()
    return _w


def get_height() -> int:
    """获取屏幕物理高度
    返回:
        屏幕高度（像素）
    """
    _ensure_init()
    return _h


def get_size() -> Tuple[int, int]:
    """获取屏幕物理尺寸
    返回:
        屏幕尺寸元组 (width, height)
    """
    _ensure_init()
    return get_width(), get_height()


def get_rotation() -> int:
    """获取当前设置的旋转角度
    返回:
        0: 0°
        1: 90°
        2: 180°
        3: 270°
    """
    _ensure_init()
    return _rotation


def get_show_size() -> Tuple[int, int]:
    """获取当前 show() 期望输入的图像尺寸 (width, height)
    返回:
        图像尺寸元组 (width, height)
    """
    _ensure_init()
    swap = (_actual_rotation == ROTATION_90 or _actual_rotation == ROTATION_270)
    if swap:
        return _h, _w   # 期望横屏图像
    return _w, _h       # 期望竖屏图像


def set_rotation(rotation: int) -> None:
    """设置显示角度
    
    参数:
        rotation: 旋转角度, 0, 1, 2, 3对应 0°, 90°, 180°, 270°

    """
    global _rotation, _actual_rotation
    _ensure_init()
    if rotation not in (ROTATION_0, ROTATION_90, ROTATION_180, ROTATION_270):
        raise ValueError(
            f"无效旋转值 {rotation}，可用: "
            f"ROTATION_0(0), ROTATION_90(1), ROTATION_180(2), ROTATION_270(3)"
        )

    _rotation = rotation
    # 逆时针语义：用户 1（逆90°）→ 硬件 ROTATE_270（顺270°）
    # 再叠加物理屏幕方向偏移
    _actual_rotation = ((4 - rotation) % 4 + _rotation_offset) % 4

    # 更新 buffer 组的 drm_rotation（用实际硬件 rotation）
    swap = (_actual_rotation == ROTATION_90 or _actual_rotation == ROTATION_270)
    if swap:
        for b in _land_buf:
            b.contents.drm_rotation = _actual_rotation
    else:
        for b in _port_buf:
            b.contents.drm_rotation = _actual_rotation

