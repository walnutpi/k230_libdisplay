#!/usr/bin/env python3
"""
rotation-test.py — 屏幕旋转测试程序

在屏幕中央绘制一个带边框和方向标记的长方形，每隔 3 秒切换一次
旋转角度 (0° → 90° → 180° → 270°)，直观验证旋转功能是否正常。

图案说明：
  - 黑色背景
  - 中央一个白色边框的彩色矩形（矩形内部红→蓝渐变）
  - 矩形左上角有一个绿色圆点，标记 "TOP" 方向

按 Ctrl+C 退出。
"""

import time
import signal
import numpy as np
from Display import init, show, get_size, get_show_size, set_rotation, ROTATION_0

g_running = True


def sigint_handler(sig, frame):
    global g_running
    g_running = False


signal.signal(signal.SIGINT, sigint_handler)

# 旋转名称
ROTATION_NAMES = {
    0: "0°",
    1: "90°",
    2: "180°",
    3: "270°",
}


def fill_rect(img: np.ndarray, x: int, y: int, w: int, h: int,
              color_bgr: tuple) -> None:
    img[y:y + h, x:x + w] = color_bgr


def draw_center_rect(w: int, h: int) -> np.ndarray:
    """绘制中央矩形测试图案"""
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # 中央矩形尺寸：屏幕宽高的一半
    rw = w // 2
    rh = h // 2
    rx = (w - rw) // 2
    ry = (h - rh) // 2

    # 矩形内部填充渐变（从左到右：红 → 蓝，BGR 格式）
    for y in range(rh):
        for x in range(rw):
            r = 255 - x * 255 // rw  # 红色递减
            b = x * 255 // rw        # 蓝色递增
            img[ry + y, rx + x] = (b, 0, r)

    # 白色边框：4 像素宽
    white = (255, 255, 255)
    bw = 4
    fill_rect(img, rx, ry, rw, bw, white)                     # 上
    fill_rect(img, rx, ry + rh - bw, rw, bw, white)           # 下
    fill_rect(img, rx, ry, bw, rh, white)                     # 左
    fill_rect(img, rx + rw - bw, ry, bw, rh, white)           # 右

    # 在矩形左上角画绿色圆点，标记 "TOP" 方向
    green = (0, 255, 0)
    dot_cx = rx + 30
    dot_cy = ry + 30
    dot_r = 15
    for dy in range(-dot_r, dot_r + 1):
        for dx in range(-dot_r, dot_r + 1):
            if dx * dx + dy * dy <= dot_r * dot_r:
                if 0 <= dot_cy + dy < h and 0 <= dot_cx + dx < w:
                    img[dot_cy + dy, dot_cx + dx] = green

    return img


def main():
    init()
    w, h = get_size()
    print(f"===== 旋转测试 =====")
    print(f"显示分辨率: {w}x{h}")

    # 预生成竖屏和横屏两张图像
    img_portrait = draw_center_rect(w, h)       # 竖屏 (w x h)
    img_landscape = draw_center_rect(h, w)      # 横屏 (h x w)

    rotations = [0, 1, 2, 3]  # ROTATION_0, 90, 180, 270
    rot_idx = 0

    print(f"旋转: {ROTATION_NAMES[rotations[rot_idx]]}")

    set_rotation(rotations[rot_idx])
    sw, sh = get_show_size()
    show(img_landscape if sw > sh else img_portrait)

    while g_running:
        time.sleep(3)
        if not g_running:
            break

        rot_idx = (rot_idx + 1) % len(rotations)
        set_rotation(rotations[rot_idx])

        # 通过 get_show_size() 判断当前 show() 期望的图像尺寸
        sw, sh = get_show_size()
        is_landscape = (sw > sh)
        show(img_landscape if is_landscape else img_portrait)

        print(f"旋转: {ROTATION_NAMES[rotations[rot_idx]]}")

    print("\n程序退出")


if __name__ == "__main__":
    main()
