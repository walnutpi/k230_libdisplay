"""
ctypes 绑定 — 封装 libdisplay.so 的 C API

使用时需要确保 libdisplay.so 在动态库搜索路径中：
  export LD_LIBRARY_PATH=/path/to/libdisplay:$LD_LIBRARY_PATH
"""

import ctypes
from ctypes import (
    c_int, c_uint32, c_uint8, c_void_p, c_char,
    POINTER, Structure, CDLL,
)
from typing import Optional

# ── 旋转常量 ──────────────────────────────────────────────
ROTATION_0 = 0
ROTATION_90 = 1
ROTATION_180 = 2
ROTATION_270 = 3
ROTATION_REFLECT_X = 4
ROTATION_REFLECT_Y = 5

# DRM 格式常量
DRM_FORMAT_ARGB8888 = 0x34325241
DRM_FORMAT_BGR888 = 0x34324742
DRM_FORMAT_RGB888 = 0x34324752

_NAME_MAP = {
    ROTATION_0: "0°",
    ROTATION_90: "90°",
    ROTATION_180: "180°",
    ROTATION_270: "270°",
    ROTATION_REFLECT_X: "Reflect X",
    ROTATION_REFLECT_Y: "Reflect Y",
}


def rotation_name(r: int) -> str:
    return _NAME_MAP.get(r, f"Unknown({r})")


# ── 不透明指针（前向声明，供指针引用） ────────────────────
class _Display(Structure):
    pass


class _DisplayPlane(Structure):
    pass


class _DisplayBuffer(Structure):
    pass


# ── 结构体定义（仅包含 Python 侧需要的字段） ──────────────
_Display._fields_ = [
    ("fd", c_int),
    ("conn_id", c_uint32),
    ("enc_id", c_uint32),
    ("crtc_id", c_uint32),
    ("blob_id", c_uint32),
    ("crtc_idx", c_int),
    ("width", c_uint32),
    ("height", c_uint32),
    ("mmWidth", c_uint32),
    ("mmHeight", c_uint32),
    # mode (drmModeModeInfo) — 跳过，Python 不关心
    # crtc, crtc_props, conn, conn_props — 不透明指针，跳过
    # req, commitFlags, drm_event_ctx — 跳过
    ("drm_rotation", c_int),
    ("planes", POINTER(_DisplayPlane)),
]

_DisplayBuffer._fields_ = [
    ("next", POINTER(_DisplayBuffer)),
    ("plane", POINTER(_DisplayPlane)),
    ("handle", c_uint32),
    ("stride", c_uint32),
    ("width", c_uint32),
    ("height", c_uint32),
    ("size", c_uint32),
    ("dmabuf_fd", c_int),
    ("id", c_uint32),
    ("drm_rotation", c_int),
    ("map", c_void_p),
]

_DisplayPlane._fields_ = [
    ("next", POINTER(_DisplayPlane)),
    ("display", POINTER(_Display)),
    ("plane", c_void_p),          # drmModePlanePtr
    # props[MAX_PROPS] — 跳过
    ("props_count", c_uint8),
    ("plane_id", c_uint32),
    ("fourcc", c_uint32),
    ("first", c_int),             # bool in C
    ("drm_rotation", c_int),
    ("buffers", POINTER(_DisplayBuffer)),
]


# ── 加载 libdisplay.so ────────────────────────────────────
_lib: Optional[CDLL] = None


def _ensure_loaded() -> CDLL:
    global _lib
    if _lib is not None:
        return _lib
    try:
        _lib = CDLL("libdisplay.so")
    except OSError as e:
        raise RuntimeError(
            "无法加载 libdisplay.so，请确保它在动态库搜索路径中。\n"
            "  export LD_LIBRARY_PATH=/path/to/libdisplay:$LD_LIBRARY_PATH\n"
            f"原始错误: {e}"
        ) from e

    # ── 声明函数签名 ────────────────────────────────────
    _lib.display_init.argtypes = [c_uint32]
    _lib.display_init.restype = POINTER(_Display)

    _lib.display_exit.argtypes = [POINTER(_Display)]
    _lib.display_exit.restype = None

    _lib.display_get_plane.argtypes = [POINTER(_Display), c_uint32]
    _lib.display_get_plane.restype = POINTER(_DisplayPlane)

    _lib.display_free_plane.argtypes = [POINTER(_DisplayPlane)]
    _lib.display_free_plane.restype = None

    _lib.display_allocate_buffer.argtypes = [
        POINTER(_DisplayPlane), c_uint32, c_uint32,
    ]
    _lib.display_allocate_buffer.restype = POINTER(_DisplayBuffer)

    _lib.display_free_buffer.argtypes = [POINTER(_DisplayBuffer)]
    _lib.display_free_buffer.restype = None

    _lib.display_update_buffer.argtypes = [
        POINTER(_DisplayBuffer), c_uint32, c_uint32,
    ]
    _lib.display_update_buffer.restype = c_int

    _lib.display_commit.argtypes = [POINTER(_Display)]
    _lib.display_commit.restype = c_int

    _lib.display_wait_vsync.argtypes = [POINTER(_Display)]
    _lib.display_wait_vsync.restype = None

    _lib.display_handle_vsync.argtypes = [POINTER(_Display)]
    _lib.display_handle_vsync.restype = None

    _lib.display_commit_buffer_noblock.argtypes = [
        POINTER(_DisplayBuffer), c_uint32, c_uint32,
    ]
    _lib.display_commit_buffer_noblock.restype = c_int

    return _lib


# ── 高层便捷函数 ──────────────────────────────────────────

def display_init(device: int = 0) -> POINTER(_Display):
    lib = _ensure_loaded()
    d = lib.display_init(device)
    if not d:
        raise RuntimeError(f"display_init({device}) 失败（需要 root 权限？）")
    return d


def display_exit(d: POINTER(_Display)) -> None:
    _ensure_loaded().display_exit(d)


def display_get_plane(d: POINTER(_Display), fourcc: int) -> POINTER(_DisplayPlane):
    lib = _ensure_loaded()
    plane = lib.display_get_plane(d, fourcc)
    if not plane:
        raise RuntimeError(f"display_get_plane 失败 (fourcc=0x{fourcc:08x})")
    return plane


def display_free_plane(plane: POINTER(_DisplayPlane)) -> None:
    _ensure_loaded().display_free_plane(plane)


def display_allocate_buffer(
    plane: POINTER(_DisplayPlane), width: int, height: int,
) -> POINTER(_DisplayBuffer):
    lib = _ensure_loaded()
    buf = lib.display_allocate_buffer(plane, width, height)
    if not buf:
        raise RuntimeError(f"display_allocate_buffer({width}x{height}) 失败")
    return buf


def display_free_buffer(buf: POINTER(_DisplayBuffer)) -> None:
    _ensure_loaded().display_free_buffer(buf)


def display_update_buffer(buf: POINTER(_DisplayBuffer), x: int = 0, y: int = 0) -> int:
    return _ensure_loaded().display_update_buffer(buf, x, y)


def display_commit(d: POINTER(_Display)) -> int:
    return _ensure_loaded().display_commit(d)


def display_wait_vsync(d: POINTER(_Display)) -> None:
    _ensure_loaded().display_wait_vsync(d)


def display_commit_buffer_noblock(
    buf: POINTER(_DisplayBuffer), x: int = 0, y: int = 0,
) -> int:
    """非阻塞提交 buffer，不等 vsync 立即返回。"""
    return _ensure_loaded().display_commit_buffer_noblock(buf, x, y)


# ── drmWaitVBlank（来自 libdrm，不依赖 page flip 事件） ──

class _drmVBlank(Structure):
    _fields_ = [
        ("type", c_uint32),
        ("sequence", c_uint32),
        ("signal", c_uint32),
        ("_pad", c_uint32),
    ]

_DRM_VBLANK_RELATIVE = 1

_libdrm: Optional[CDLL] = None


def _ensure_libdrm() -> CDLL:
    global _libdrm
    if _libdrm is not None:
        return _libdrm
    _libdrm = CDLL("libdrm.so.2")
    _libdrm.drmWaitVBlank.argtypes = [c_int, POINTER(_drmVBlank)]
    _libdrm.drmWaitVBlank.restype = c_int
    return _libdrm


def wait_vblank(fd: int) -> None:
    """等待下一个 vblank（drmWaitVBlank ioctl）"""
    vbl = _drmVBlank()
    vbl.type = _DRM_VBLANK_RELATIVE
    vbl.sequence = 1
    vbl.signal = 0
    _ensure_libdrm().drmWaitVBlank(fd, ctypes.byref(vbl))
