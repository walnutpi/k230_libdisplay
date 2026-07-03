#!/usr/bin/env python3
"""
double-buffer.py — 全屏红黑交替显示示例（双缓冲 + FPS 统计）

功能：打开屏幕，交替显示全屏红色和全屏黑色。
      使用双缓冲技术，每秒在控制台输出一次 FPS。

按 Ctrl+C 退出。
"""

import time
import signal
import numpy as np
from Display import init, show, get_size, set_rotation

g_running = True


def sigint_handler(sig, frame):
    global g_running
    g_running = False


signal.signal(signal.SIGINT, sigint_handler)


def main():
    init()
    set_rotation(0)
    w, h = get_size()
    print(f"显示分辨率: {w}x{h}")

    # 预生成红色和黑色帧
    red_frame = np.full((h, w, 3), (0, 0, 255), dtype=np.uint8)
    black_frame = np.zeros((h, w, 3), dtype=np.uint8)

    frame_count = 0
    last_fps_time = time.monotonic()
    frames_since_last = 0

    while g_running:
        # 交替选择红/黑
        img = red_frame if frame_count % 2 == 0 else black_frame
        show(img)

        frame_count += 1
        frames_since_last += 1

        # 每秒输出一次 FPS
        now = time.monotonic()
        elapsed = now - last_fps_time
        if elapsed >= 1.0:
            fps = frames_since_last / elapsed
            print(f"FPS: {fps:.1f}  (已运行 {frame_count} 帧)")
            last_fps_time = now
            frames_since_last = 0

    print(f"\n程序正常退出，共运行 {frame_count} 帧")


if __name__ == "__main__":
    main()
