/**
 * red-black.c — 全屏红黑交替显示示例（双缓冲，死循环 + FPS 统计）
 *
 * 功能：打开屏幕，交替显示全屏红色和全屏黑色，死循环运行。
 *       使用双缓冲技术，每秒在控制台输出一次 FPS。
 *
 * 编译：
 *   gcc -o red-black red-black.c -I../include -I/usr/include/libdrm \
 *       -L.. -ldisplay -ldrm -Wl,-rpath,..
 *
 * 运行（需要 root 或 video 组权限）：
 *   sudo ./red-black
 */

#include "display.h"
#include <drm/drm_fourcc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <signal.h>

static volatile int g_running = 1;

/** 信号处理：按 Ctrl+C 优雅退出 */
static void sigint_handler(int sig)
{
    (void)sig;
    g_running = 0;
}

/** 获取当前时间（秒，浮点精度） */
static double get_time_sec(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

/** 快速填充缓冲区（ARGB8888）
 *  利用整行 memset 加速，比逐像素循环快得多
 */
static void fill_color_fast(struct display_buffer *buf, uint32_t width, uint32_t height,
                            uint32_t color)
{
    uint32_t stride_pixels = buf->stride / 4;
    uint32_t *pixels = (uint32_t *)buf->map;

    /* 如果颜色是 0xFF000000（黑色），直接用 memset 清零，最快 */
    if (color == 0xFF000000) {
        for (uint32_t y = 0; y < height; y++)
            memset(&pixels[y * stride_pixels], 0, width * 4);
    } else {
        /* 非零颜色：先填充第一行，然后逐行 memcpy 复制 */
        for (uint32_t x = 0; x < width; x++)
            pixels[x] = color;
        for (uint32_t y = 1; y < height; y++)
            memcpy(&pixels[y * stride_pixels], pixels, width * 4);
    }
}

int main(void)
{
    struct display *d;
    struct display_plane *plane;
    struct display_buffer *buf[2];
    int frame = 0;
    double last_fps_time;
    int frames_since_last = 0;

    /* 注册 Ctrl+C 信号处理 */
    signal(SIGINT, sigint_handler);

    /* 1. 初始化显示设备 */
    d = display_init(0);
    if (!d) {
        fprintf(stderr, "错误: display_init 失败 (需要 root 权限?)\n");
        return -1;
    }
    printf("显示分辨率: %u x %u\n", d->width, d->height);

    /* 2. 获取 ARGB8888 图层 */
    plane = display_get_plane(d, DRM_FORMAT_ARGB8888);
    if (!plane) {
        fprintf(stderr, "错误: 无法获取 ARGB8888 图层\n");
        display_exit(d);
        return -1;
    }

    /* 3. 分配双缓冲 */
    for (int i = 0; i < 2; i++) {
        buf[i] = display_allocate_buffer(plane, d->width, d->height);
        if (!buf[i]) {
            fprintf(stderr, "错误: 分配缓冲区 buf[%d] 失败\n", i);
            for (int j = 0; j < i; j++) display_free_buffer(buf[j]);
            display_free_plane(plane);
            display_exit(d);
            return -1;
        }
    }

    /* 4. 初始填充并显示第一帧（红色） */
    fill_color_fast(buf[0], d->width, d->height, 0xFFFF0000);
    fill_color_fast(buf[1], d->width, d->height, 0xFFFF0000);
    display_update_buffer(buf[0], 0, 0);
    display_commit(d);
    display_wait_vsync(d);

    last_fps_time = get_time_sec();

    /* 5. 死循环：红 ↔ 黑 交替显示 */
    while (g_running) {
        int front = frame % 2;
        int back  = 1 - front;
        uint32_t color = (frame % 2 == 0) ? 0xFF000000  /* 黑色 */
                                          : 0xFFFF0000; /* 红色 */

        /* 后台绘制 */
        fill_color_fast(buf[back], d->width, d->height, color);

        /* 交换前后台 */
        display_update_buffer(buf[back], 0, 0);
        display_commit(d);
        display_wait_vsync(d);

        frame++;
        frames_since_last++;

        /* 每秒输出一次 FPS */
        double now = get_time_sec();
        if (now - last_fps_time >= 1.0) {
            double fps = frames_since_last / (now - last_fps_time);
            printf("FPS: %.1f  (已运行 %d 帧)\n", fps, frame);
            last_fps_time = now;
            frames_since_last = 0;
        }
    }

    /* 6. 清理 */
    for (int i = 0; i < 2; i++) display_free_buffer(buf[i]);
    display_free_plane(plane);
    display_exit(d);
    printf("\n程序正常退出，共运行 %d 帧\n", frame);
    return 0;
}