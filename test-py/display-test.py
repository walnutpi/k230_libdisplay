#!/usr/bin/env python3
"""
display-test.py — 综合显示测试程序

在屏幕上循环显示多种测试图形，便于目视检查显示质量。
测试图形列表：
  1. BORDER MARK  — 边框 + X 对角线 + 原点标记
  2. COLOR BARS   — 标准 8 色彩条
  3. GRAYSCALE    — 16 级灰度阶梯
  4. RGB GRADIENT — RGB 三通道渐变
  5. COLOR SQUARES— 纯色方块

按 Ctrl+C 退出。
"""

import time
import signal
import sys
import numpy as np
from Display import init, show, get_size, set_rotation

# ── 全局运行标志 ──────────────────────────────────────────
g_running = True


def sigint_handler(sig, frame):
    global g_running
    g_running = False


signal.signal(signal.SIGINT, sigint_handler)


# ── 绘图工具函数 ──────────────────────────────────────────

def fill_rect(img: np.ndarray, x: int, y: int, w: int, h: int,
              color_bgr: tuple) -> None:
    """填充矩形区域 (BGR 格式)"""
    img[y:y + h, x:x + w] = color_bgr


def draw_pixel(img: np.ndarray, x: int, y: int, color_bgr: tuple) -> None:
    """画一个像素点"""
    if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]:
        img[y, x] = color_bgr


# ── 测试图形 ──────────────────────────────────────────────

def draw_border_mark(w: int, h: int) -> np.ndarray:
    """边框定位 + X 对角线 + 原点标记"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    border = min(w, h) // 200 + 2  # 自适应粗细

    # 红色外边框
    red = (0, 0, 255)
    fill_rect(img, 0, 0, w, border, red)
    fill_rect(img, 0, h - border, w, border, red)
    fill_rect(img, 0, 0, border, h, red)
    fill_rect(img, w - border, 0, border, h, red)

    # 黄色四角 L 形标记
    yellow = (0, 255, 255)
    cw = 40
    fill_rect(img, 0, 0, cw, border * 2, yellow)
    fill_rect(img, 0, 0, border * 2, cw, yellow)
    fill_rect(img, w - cw, 0, cw, border * 2, yellow)
    fill_rect(img, w - border * 2, 0, border * 2, cw, yellow)
    fill_rect(img, 0, h - border * 2, cw, border * 2, yellow)
    fill_rect(img, 0, h - cw, border * 2, cw, yellow)
    fill_rect(img, w - cw, h - border * 2, cw, border * 2, yellow)
    fill_rect(img, w - border * 2, h - cw, border * 2, cw, yellow)

    # X 对角线（青色）
    cyan = (255, 255, 0)
    steps = max(w, h)
    for t in range(steps + 1):
        x1 = t * (w - 1) // steps
        y1 = t * (h - 1) // steps
        x2 = (w - 1) - t * (w - 1) // steps
        y2 = t * (h - 1) // steps
        draw_pixel(img, x1, y1, cyan)
        draw_pixel(img, x2, y2, cyan)

    # 原点标记 — 绿色圆点
    green = (0, 255, 0)
    dot_r = 10
    for dy in range(-dot_r, dot_r + 1):
        for dx in range(-dot_r, dot_r + 1):
            if dx * dx + dy * dy <= dot_r * dot_r:
                draw_pixel(img, border + dx, border + dy, green)

    # X 轴（向右）
    axis_color = (128, 255, 0)
    origin_size = 50
    for i in range(origin_size):
        draw_pixel(img, border + i, border, axis_color)
    for dy in range(-3, 4):
        draw_pixel(img, border + origin_size, border + dy, (255, 255, 255))
        draw_pixel(img, border + origin_size - 1, border + dy, (255, 255, 255))

    # Y 轴（向下）
    for i in range(origin_size):
        draw_pixel(img, border, border + i, axis_color)
    for dx in range(-3, 4):
        draw_pixel(img, border + dx, border + origin_size, (255, 255, 255))
        draw_pixel(img, border + dx, border + origin_size - 1, (255, 255, 255))

    return img


def draw_color_bars(w: int, h: int) -> np.ndarray:
    """标准 8 色彩条 (白/黄/青/绿/品/红/蓝/黑)"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    bars_bgr = [
        (255, 255, 255),  # 白
        (0, 255, 255),    # 黄
        (255, 255, 0),    # 青
        (0, 255, 0),      # 绿
        (255, 0, 255),    # 品
        (0, 0, 255),      # 红
        (255, 0, 0),      # 蓝
        (0, 0, 0),        # 黑
    ]
    bar_w = w // 8
    for i, color in enumerate(bars_bgr):
        fill_rect(img, i * bar_w, 0, bar_w, h, color)
    return img


def draw_grayscale(w: int, h: int) -> np.ndarray:
    """16 级灰度阶梯"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    steps = 16
    bar_w = w // steps
    for i in range(steps):
        v = i * 255 // (steps - 1)
        fill_rect(img, i * bar_w, 0, bar_w, h, (v, v, v))
    return img


def draw_rgb_gradient(w: int, h: int) -> np.ndarray:
    """RGB 三通道渐变"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    seg_w = w // 3
    for x in range(seg_w):
        v = x * 255 // seg_w
        img[:, x] = (0, 0, v)            # B
        img[:, seg_w + x] = (0, v, 0)    # G
        img[:, seg_w * 2 + x] = (v, 0, 0)  # R
    return img


def draw_color_squares(w: int, h: int) -> np.ndarray:
    """纯色方块"""
    img = np.full((h, w, 3), 64, dtype=np.uint8)
    colors_bgr = [
        (0, 0, 255),    # 红
        (0, 255, 0),    # 绿
        (255, 0, 0),    # 蓝
        (0, 255, 255),  # 黄
        (255, 0, 255),  # 品
        (255, 255, 0),  # 青
        (255, 255, 255),# 白
        (0, 0, 0),      # 黑
        (0, 128, 255),  # 橙
        (255, 0, 128),  # 紫
        (255, 128, 0),  # 天蓝
        (128, 255, 0),  # 青绿
        (0, 255, 128),  # 黄绿
        (128, 0, 255),  # 粉
        (128, 128, 128),# 灰
    ]
    cols, rows = 5, 3
    sw, sh = w // cols, h // rows
    idx = 0
    for row in range(rows):
        for col in range(cols):
            if idx >= len(colors_bgr):
                break
            mx = col * sw + 10
            my = row * sh + 10
            mw = sw - 20
            mh = sh - 20
            fill_rect(img, mx, my, mw, mh, colors_bgr[idx])
            idx += 1
    return img


# ── 测试图案列表 ──────────────────────────────────────────

PATTERNS = [
    ("Border Mark", draw_border_mark),
    ("Color Bars", draw_color_bars),
    ("Grayscale", draw_grayscale),
    ("RGB Gradient", draw_rgb_gradient),
    ("Color Squares", draw_color_squares),
]


# ── 主程序 ────────────────────────────────────────────────

def main():
    init()
    w, h = get_size()
    set_rotation(0)
    print(f"===== K230 Display Test =====")
    print(f"显示分辨率: {w}x{h}")
    print(f"共 {len(PATTERNS)} 种测试图形, 每 3 秒切换")
    print()

    # 预生成所有图案
    frames = [draw_fn(w, h) for _, draw_fn in PATTERNS]

    pattern_idx = 0
    last_switch = time.monotonic()
    frame_count = 0

    print(f"[P1] {PATTERNS[0][0]}")

    while g_running:
        # 每 3 秒切换图案
        now = time.monotonic()
        if now - last_switch >= 3.0:
            pattern_idx = (pattern_idx + 1) % len(PATTERNS)
            print(f"[P{pattern_idx + 1}] {PATTERNS[pattern_idx][0]}")
            last_switch = now

        show(frames[pattern_idx])
        frame_count += 1

    print(f"\n程序退出, 共显示 {frame_count} 帧")


if __name__ == "__main__":
    main()
