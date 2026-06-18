/**
 * rotation-test.c — 屏幕旋转测试程序
 *
 * 功能：在屏幕中央绘制一个带边框和方向标记的长方形，每隔数秒切换一次
 *       旋转角度 (0° → 90° → 180° → 270°)，直观验证旋转功能是否正常。
 *
 * 编译：
 *   make
 *
 * 运行（需要 root 或 video 组权限）：
 *   sudo ./rotation-test
 *
 * 按键操作：
 *   Ctrl+C 退出程序
 */

#include "display.h"
#include <drm/drm_fourcc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>

static volatile int g_running = 1;

static void sigint_handler(int sig)
{
    (void)sig;
    g_running = 0;
}

/** 填充矩形区域 (ARGB8888) */
static void fill_rect(uint32_t *pixels, int stride_px,
                      int x, int y, int w, int h, uint32_t color)
{
    for (int row = y; row < y + h; row++)
        for (int col = x; col < x + w; col++)
            pixels[row * stride_px + col] = color;
}

/**
 * 绘制中央矩形测试图案
 *
 * 图案说明：
 *   - 黑色背景
 *   - 中央一个白色边框的彩色矩形
 *   - 矩形内部填充红→蓝渐变（水平方向）
 *   - 矩形左上角有一个绿色圆点，标记 "TOP" 方向，便于肉眼判断旋转
 */
static void draw_center_rect(uint32_t *pixels, int screen_w, int screen_h, int stride_px)
{
    /* 黑色背景 */
    fill_rect(pixels, stride_px, 0, 0, screen_w, screen_h, 0xFF000000);

    /* 中央矩形尺寸：屏幕宽高的一半 */
    int rw = screen_w / 2;
    int rh = screen_h / 2;
    int rx = (screen_w - rw) / 2;
    int ry = (screen_h - rh) / 2;

    /* 矩形内部填充渐变（从左到右：红 → 蓝） */
    for (int y = 0; y < rh; y++) {
        for (int x = 0; x < rw; x++) {
            uint8_t r = (uint8_t)(255 - x * 255 / rw);
            uint8_t g = 0;
            uint8_t b = (uint8_t)(x * 255 / rw);
            pixels[(ry + y) * stride_px + (rx + x)] = 0xFF000000 | (r << 16) | (g << 8) | b;
        }
    }

    /* 白色边框：4 像素宽 */
    uint32_t border_color = 0xFFFFFFFF;
    int bw = 4;
    fill_rect(pixels, stride_px, rx, ry, rw, bw, border_color);               /* 上 */
    fill_rect(pixels, stride_px, rx, ry + rh - bw, rw, bw, border_color);     /* 下 */
    fill_rect(pixels, stride_px, rx, ry, bw, rh, border_color);               /* 左 */
    fill_rect(pixels, stride_px, rx + rw - bw, ry, bw, rh, border_color);     /* 右 */

    /* 在矩形左上角画绿色圆点，标记 "TOP" 方向 */
    int dot_cx = rx + 30;
    int dot_cy = ry + 30;
    int dot_r = 15;
    for (int dy = -dot_r; dy <= dot_r; dy++) {
        for (int dx = -dot_r; dx <= dot_r; dx++) {
            if (dx * dx + dy * dy <= dot_r * dot_r) {
                pixels[(dot_cy + dy) * stride_px + (dot_cx + dx)] = 0xFF00FF00;
            }
        }
    }
}

static const char *rotation_name(enum drm_rotation r)
{
    switch (r) {
        case rotation_0:         return "0°";
        case rotation_90:        return "90°";
        case rotation_180:       return "180°";
        case rotation_270:       return "270°";
        case rotation_reflect_x: return "Reflect X";
        case rotation_reflect_y: return "Reflect Y";
        default:                 return "Unknown";
    }
}

int main(void)
{
    struct display *d;
    struct display_plane *plane;
    struct display_buffer *buf[2];
    int back = 0;
    int rot_idx = 0;
    static const enum drm_rotation rotations[] = {
        rotation_0,
        rotation_90,
        rotation_180,
        rotation_270,
    };
    const int num_rots = sizeof(rotations) / sizeof(rotations[0]);

    signal(SIGINT, sigint_handler);

    /* 1. 初始化显示设备 */
    d = display_init(0);
    if (!d) {
        fprintf(stderr, "错误: display_init 失败 (需要 root 权限?)\n");
        return -1;
    }
    printf("===== 旋转测试 =====\n");
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

    /* 4. 初始化时绘制一次，两个缓冲区内容相同 */
    for (int i = 0; i < 2; i++) {
        draw_center_rect((uint32_t *)buf[i]->map, d->width, d->height,
                         buf[i]->stride / 4);
        buf[i]->drm_rotation = rotation_0;
    }
    display_update_buffer(buf[0], 0, 0);
    display_commit(d);
    display_wait_vsync(d);

    printf("旋转: %s\n", rotation_name(rotations[rot_idx]));

    /* 5. 循环：每 3 秒切换一个旋转角度（测试 DRM 旋转功能） */
    while (g_running) {
        sleep(3);
        if (!g_running) break;

        rot_idx = (rot_idx + 1) % num_rots;
        back = 1 - back;  /* 切换缓冲区 */

        /* 仅更新旋转角度，不重复绘制 */
        buf[back]->drm_rotation = rotations[rot_idx];
        display_update_buffer(buf[back], 0, 0);
        display_commit(d);
        display_wait_vsync(d);

        printf("旋转: %s\n", rotation_name(rotations[rot_idx]));
    }

    /* 6. 清理 */
    printf("\n正在清理...\n");
    for (int i = 0; i < 2; i++) display_free_buffer(buf[i]);
    display_free_plane(plane);
    display_exit(d);
    printf("程序退出\n");
    return 0;
}
