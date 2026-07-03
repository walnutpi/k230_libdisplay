"""
K230 Display Python 库
"""

import ctypes
import numpy as np
from typing import Tuple

from ._bindings import (
    display_init as _c_init,
    display_exit as _c_exit,
    display_get_plane as _c_get_plane,
    display_free_plane as _c_free_plane,
    display_allocate_buffer as _c_alloc_buf,
    display_free_buffer as _c_free_buf,
    display_update_buffer as _c_update_buf,
    display_commit as _c_commit,
    display_wait_vsync as _c_wait_vsync,
    ROTATION_0,
    ROTATION_90,
    ROTATION_180,
    ROTATION_270,
)

# ── 模块级全局状态 ────────────────────────────────────────

_display = None
_plane = None

# 两组双缓冲
_port_buf: list = []      # 竖屏 (phys_w x phys_h)
_land_buf: list = []      # 横屏 (phys_h x phys_w)

_front = 0
_initialized = False
_w = 0
_h = 0

# 预缓存 — 竖屏
_port_stride = 0
_port_row_bytes = 0
_port_work = None
_port_dst_base = None      # ctypes 指针，缓存 buf->map 的 LP_c_uint8

# 预缓存 — 横屏
_land_stride = 0
_land_row_bytes = 0
_land_work = None
_land_dst_base = None

# 运行中不变的"常量"
_DRM_FORMAT_ARGB8888 = 0x34325241

# 当前旋转角度
_rotation = ROTATION_0

# 流水线状态：上一帧是否已 commit 但尚未 wait_vsync
_pending_vsync = False


def init() -> None:
    """初始化屏幕，分配竖屏和横屏两组双缓冲"""
    global _display, _plane, _front, _initialized, _pending_vsync
    global _w, _h
    global _port_buf, _port_stride, _port_row_bytes, _port_work, _port_dst_base
    global _land_buf, _land_stride, _land_row_bytes, _land_work, _land_dst_base
    global _rotation

    if _initialized:
        return

    _display = _c_init(0)
    _plane = _c_get_plane(_display, _DRM_FORMAT_ARGB8888)
    _w = _display.contents.width
    _h = _display.contents.height

    is_portrait = (_w < _h)

    # ── 竖屏双缓冲 ──
    _port_buf = [_c_alloc_buf(_plane, _w, _h),
                 _c_alloc_buf(_plane, _w, _h)]
    _port_stride = _port_buf[0].contents.stride
    _port_row_bytes = _w * 4
    for b in _port_buf:
        ctypes.memset(b.contents.map, 0, b.contents.size)
        b.contents.drm_rotation = ROTATION_0
    _port_work = np.empty((_h, _w, 4), dtype=np.uint8)
    # 缓存两个 buffer 的 map 指针（避免每次 show 都 cast）
    _port_dst_base = [
        ctypes.cast(_port_buf[0].contents.map, ctypes.POINTER(ctypes.c_uint8)),
        ctypes.cast(_port_buf[1].contents.map, ctypes.POINTER(ctypes.c_uint8)),
    ]

    # ── 横屏双缓冲 ──
    _land_buf = [_c_alloc_buf(_plane, _h, _w),
                 _c_alloc_buf(_plane, _h, _w)]
    _land_stride = _land_buf[0].contents.stride
    _land_row_bytes = _h * 4
    for b in _land_buf:
        ctypes.memset(b.contents.map, 0, b.contents.size)
        b.contents.drm_rotation = ROTATION_90
    _land_work = np.empty((_w, _h, 4), dtype=np.uint8)
    _land_dst_base = [
        ctypes.cast(_land_buf[0].contents.map, ctypes.POINTER(ctypes.c_uint8)),
        ctypes.cast(_land_buf[1].contents.map, ctypes.POINTER(ctypes.c_uint8)),
    ]

    # 竖屏 → 默认横屏模式
    if is_portrait:
        _rotation = ROTATION_90
        _c_update_buf(_land_buf[0], 0, 0)
    else:
        _rotation = ROTATION_0
        _c_update_buf(_port_buf[0], 0, 0)

    _c_commit(_display)
    _c_wait_vsync(_display)

    _front = 0
    _pending_vsync = False
    _initialized = True


def show(img: np.ndarray) -> None:
    """显示图像（流水线模式）

    在准备当前帧之前，先等待上一帧的 vsync 完成。
    这样 CPU 工作与 vsync 等待在时间上重叠。

    参数:
        img: (H, W, 3/4) uint8 BGR/BGRA 图像
    """
    global _front, _pending_vsync

    if not _initialized:
        raise RuntimeError("Display 未初始化，请先调用 init()")

    if img.ndim != 3 or img.shape[2] not in (3, 4):
        raise ValueError(f"图像必须是 (H, W, 3) 或 (H, W, 4) 格式，当前 shape={img.shape}")
    if img.dtype != np.uint8:
        raise ValueError(f"图像数据类型必须为 uint8，当前为 {img.dtype}")

    # ── 先等待上一帧 vsync（与当前帧的 CPU 准备重叠） ──
    if _pending_vsync:
        _c_wait_vsync(_display)

    h, w = img.shape[:2]
    swap = (_rotation == ROTATION_90 or _rotation == ROTATION_270)

    if swap:
        if w != _h or h != _w:
            raise ValueError(
                f"当前旋转 {_rotation}° 期望横屏图像 {_h}x{_w}，"
                f"当前为 {w}x{h}"
            )
        stride = _land_stride
        row_bytes = _land_row_bytes
        work = _land_work
        dst = _land_dst_base[1 - _front]
    else:
        if w != _w or h != _h:
            raise ValueError(
                f"当前旋转 {_rotation}° 期望竖屏图像 {_w}x{_h}，"
                f"当前为 {w}x{h}"
            )
        stride = _port_stride
        row_bytes = _port_row_bytes
        work = _port_work
        dst = _port_dst_base[1 - _front]

    channels = img.shape[2]

    if channels == 3:
        work[:, :, 0] = img[:, :, 0]
        work[:, :, 1] = img[:, :, 1]
        work[:, :, 2] = img[:, :, 2]
        work[:, :, 3] = 0xFF
    else:
        work[:, :, 0] = img[:, :, 0]
        work[:, :, 1] = img[:, :, 1]
        work[:, :, 2] = img[:, :, 2]
        work[:, :, 3] = img[:, :, 3]

    # ── work → C buffer（整帧或逐行） ──
    src = ctypes.cast(work.ctypes.data, ctypes.POINTER(ctypes.c_uint8))
    if stride == row_bytes:
        ctypes.memmove(dst, src, h * row_bytes)
    else:
        for y in range(h):
            ctypes.memmove(
                ctypes.byref(dst[y * stride]),
                ctypes.byref(src[y * row_bytes]),
                row_bytes,
            )

    # ── 提交当前帧（不立即等 vsync，留给下一帧开头等） ──
    if swap:
        _c_update_buf(_land_buf[1 - _front], 0, 0)
    else:
        _c_update_buf(_port_buf[1 - _front], 0, 0)

    _c_commit(_display)
    _front = 1 - _front
    _pending_vsync = True


def flush() -> None:
    """等待最后一帧 vsync 完成（程序退出前调用）"""
    global _pending_vsync
    if _pending_vsync:
        _c_wait_vsync(_display)
        _pending_vsync = False


def _ensure_init() -> None:
    """确保 Display 已初始化，否则抛出异常"""
    if not _initialized:
        raise RuntimeError("Display 未初始化，请先调用 init()")


def get_width() -> int:
    """获取屏幕物理宽度（像素）"""
    _ensure_init()
    return _w


def get_height() -> int:
    """获取屏幕物理高度（像素）"""
    _ensure_init()
    return _h


def get_size() -> Tuple[int, int]:
    return get_width(), get_height()


def get_rotation() -> int:
    """获取当前设置的旋转角度"""
    _ensure_init()
    return _rotation


def set_rotation(rotation: int) -> None:
    """设置旋转角度

    决定后续 show() 期望的图像方向：
      ROTATION_0/180 → 竖屏图像 (phys_w x phys_h)
      ROTATION_90/270 → 横屏图像 (phys_h x phys_w)
    """
    global _rotation
    _ensure_init()
    if rotation not in (ROTATION_0, ROTATION_90, ROTATION_180, ROTATION_270):
        raise ValueError(
            f"无效旋转值 {rotation}，可用: "
            f"ROTATION_0(0), ROTATION_90(1), ROTATION_180(2), ROTATION_270(3)"
        )

    _rotation = rotation

    # 更新 buffer 组的 drm_rotation
    swap = (rotation == ROTATION_90 or rotation == ROTATION_270)
    if swap:
        for b in _land_buf:
            b.contents.drm_rotation = rotation
    else:
        for b in _port_buf:
            b.contents.drm_rotation = rotation

