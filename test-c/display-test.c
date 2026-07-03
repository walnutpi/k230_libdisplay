/**
 * display-test.c — 综合显示测试程序
 *
 * 功能：在屏幕上循环显示多种有意义的测试图形，便于目视检查显示质量。
 *       无需查看源码，仅凭屏幕显示即可判断显示是否存在问题。
 *
 * 测试图形列表：
 *   1. BORDER MARK  — 边框 + X 对角线 + 原点标记（检测边框位置与坐标原点）
 *   2. COLOR BARS   — 标准8色彩条（白/黄/青/绿/品/红/蓝/黑）
 *   3. GRAYSCALE    — 16级灰度阶梯
 *   4. RGB GRADIENT — RGB三通道渐变
 *   5. COLOR SQUARES— 纯色方块（检测颜色准确性）
 *
 * 编译：
 *   make
 *
 * 运行（需要 root 或 video 组权限）：
 *   sudo ./display-test
 *
 * 按键操作：
 *   Ctrl+C 退出程序
 */

#include "display.h"
#include <drm/drm_fourcc.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdint.h>
#include <math.h>

/* ---- 像素绘制工具函数 ---- */

/** 在 (x,y) 处画一个像素点 */
static inline void draw_pixel(uint32_t *pixels, int stride_px,
                              int x, int y, uint32_t color)
{
    if (x < 0 || y < 0) return;
    pixels[y * stride_px + x] = color;
}

/** 填充矩形区域 */
static void fill_rect(uint32_t *pixels, int stride_px,
                      int x, int y, int w, int h, uint32_t color)
{
    for (int row = y; row < y + h; row++)
        for (int col = x; col < x + w; col++)
            pixels[row * stride_px + col] = color;
}


/* ==================================================================
 * 测试图形生成函数
 * ================================================================*/

/* ---- 1. 标准 8 色彩条 ---- */
static void draw_pattern_color_bars(uint32_t *p, int w, int h, int spx)
{
    static const uint32_t bars[8] = {
        0xFFFFFFFF, /* 白 */ 0xFFFFFF00, /* 黄 */ 0xFF00FFFF, /* 青 */
        0xFF00FF00, /* 绿 */ 0xFFFF00FF, /* 品 */ 0xFFFF0000, /* 红 */
        0xFF0000FF, /* 蓝 */ 0xFF000000, /* 黑 */
    };
    int bar_w = w / 8;
    for (int i = 0; i < 8; i++)
        fill_rect(p, spx, i * bar_w, 0, bar_w, h, bars[i]);
}

/* ---- 2. 16 级灰度阶梯 ---- */
static void draw_pattern_grayscale(uint32_t *p, int w, int h, int spx)
{
    int steps = 16;
    int bar_w = w / steps;
    for (int i = 0; i < steps; i++) {
        uint8_t v = (uint8_t)(i * 255 / (steps - 1));
        uint32_t color = 0xFF000000 | (v << 16) | (v << 8) | v;
        fill_rect(p, spx, i * bar_w, 0, bar_w, h, color);
    }
}

/* ---- 3. RGB 三通道渐变 ---- */
static void draw_pattern_rgb_gradient(uint32_t *p, int w, int h, int spx)
{
    int seg_w = w / 3;
    for (int x = 0; x < seg_w; x++) {
        uint8_t v = (uint8_t)(x * 255 / seg_w);
        uint32_t r = 0xFF000000 | (v << 16);
        uint32_t g = 0xFF000000 | (v << 8);
        uint32_t b = 0xFF000000 | v;
        for (int y = 0; y < h; y++) {
            p[y * spx + x]            = r;          /* R */
            p[y * spx + seg_w + x]    = g;          /* G */
            p[y * spx + seg_w * 2 + x] = b;         /* B */
        }
    }
}




/* ---- 7. 边框定位 + X 对角线 ---- */
static void draw_pattern_border_mark(uint32_t *p, int w, int h, int spx)
{
    /* 黑色背景 */
    fill_rect(p, spx, 0, 0, w, h, 0xFF000000);

    int border = w < 800 ? 2 : 4; /* 边框粗细，自适应分辨率 */

    /* 外边框 — 红色亮边 */
    uint32_t border_color = 0xFFFF0000;
    fill_rect(p, spx, 0, 0, w, border, border_color);                /* 上 */
    fill_rect(p, spx, 0, h - border, w, border, border_color);       /* 下 */
    fill_rect(p, spx, 0, 0, border, h, border_color);                /* 左 */
    fill_rect(p, spx, w - border, 0, border, h, border_color);       /* 右 */

    /* 四角标记 — 加粗的 L 形角标（黄色），更易看清边界 */
    int cw = (w < 800) ? 20 : 40;
    uint32_t corner_color = 0xFFFFFF00; /* 黄色 */
    /* 左上角 */
    fill_rect(p, spx, 0, 0, cw, border * 2, corner_color);
    fill_rect(p, spx, 0, 0, border * 2, cw, corner_color);
    /* 右上角 */
    fill_rect(p, spx, w - cw, 0, cw, border * 2, corner_color);
    fill_rect(p, spx, w - border * 2, 0, border * 2, cw, corner_color);
    /* 左下角 */
    fill_rect(p, spx, 0, h - border * 2, cw, border * 2, corner_color);
    fill_rect(p, spx, 0, h - cw, border * 2, cw, corner_color);
    /* 右下角 */
    fill_rect(p, spx, w - cw, h - border * 2, cw, border * 2, corner_color);
    fill_rect(p, spx, w - border * 2, h - cw, border * 2, cw, corner_color);

    /* X 对角线 — 青色，从四角交叉到中心 */
    uint32_t x_color = 0xFF00FFFF;

    /* 用 Bresenham 画两条对角线 */
    int steps = (w > h) ? w : h;
    for (int t = 0; t <= steps; t++) {
        /* 左上 → 右下 */
        int x1 = t * w / steps;
        int y1 = t * h / steps;
        draw_pixel(p, spx, x1, y1, x_color);
        /* 右上 → 左下 */
        int x2 = w - t * w / steps;
        int y2 = t * h / steps;
        draw_pixel(p, spx, x2, y2, x_color);
    }


    /* 坐标原点标记 — 左上角 (0,0)，绿色圆点 + L 形坐标轴 */
    int origin_size = (w < 800) ? 30 : 50;
    uint32_t origin_color = 0xFF00FF00;       /* 绿色 */
    uint32_t axis_color   = 0xFF00FF80;       /* 青绿 — 坐标轴 */
    uint32_t label_color  = 0xFFFFFFFF;       /* 白色 — 标签 */

    /* 绿色大圆点标记原点精确位置 */
    int dot_r = (w < 800) ? 6 : 10;
    for (int dy = -dot_r; dy <= dot_r; dy++) {
        for (int dx = -dot_r; dx <= dot_r; dx++) {
            if (dx * dx + dy * dy <= dot_r * dot_r) {
                int px = border + dx;
                int py = border + dy;
                if (px >= 0 && py >= 0)
                    draw_pixel(p, spx, px, py, origin_color);
            }
        }
    }

    /* X 轴正向箭头 → (向右) */
    for (int i = 0; i < origin_size; i++) {
        draw_pixel(p, spx, border + i, border, axis_color);      /* 轴线 */
        if (i < origin_size / 3) {
            /* 箭头下侧 */
            draw_pixel(p, spx, border + i, border + i / 2, axis_color);
        }
    }
    /* 箭头尖端 */
    int ax_end = border + origin_size;
    for (int dy = -3; dy <= 3; dy++)
        draw_pixel(p, spx, ax_end, border + dy, axis_color);
    for (int dy = -2; dy <= 2; dy++) {
        draw_pixel(p, spx, ax_end - 1, border + dy, axis_color);
    }
    /* X 轴标签 "X" */
    for (int dy = -3; dy <= 3; dy++)
        draw_pixel(p, spx, ax_end + 4, border + dy, label_color);

    /* Y 轴正向箭头 ↓ (向下) */
    for (int i = 0; i < origin_size; i++) {
        draw_pixel(p, spx, border, border + i, axis_color);      /* 轴线 */
        if (i < origin_size / 3) {
            /* 箭头右侧 */
            draw_pixel(p, spx, border + i / 2, border + i, axis_color);
        }
    }
    /* 箭头尖端 */
    int ay_end = border + origin_size;
    for (int dx = -3; dx <= 3; dx++)
        draw_pixel(p, spx, border + dx, ay_end, axis_color);
    for (int dx = -2; dx <= 2; dx++) {
        draw_pixel(p, spx, border + dx, ay_end - 1, axis_color);
    }
    /* Y 轴标签 "Y" */
    for (int dx = -3; dx <= 3; dx++)
        draw_pixel(p, spx, border + dx, ay_end + 4, label_color);

    /* "(0,0)" 标签 — 在原点右下侧用像素绘出文字轮廓 */
    int lx = border + dot_r + 4;
    int ly = border + dot_r + 4;
    /* 简化的 "(0,0)" 文字 — 画一个方框代表标签区域 */
    int tw = (w < 800) ? 20 : 28;
    int th = (w < 800) ? 8 : 12;
    fill_rect(p, spx, lx, ly, tw, th, 0xFF002200);
    for (int i = 0; i < tw; i++) {
        draw_pixel(p, spx, lx + i, ly, label_color);
        draw_pixel(p, spx, lx + i, ly + th - 1, label_color);
    }
    for (int i = 0; i < th; i++) {
        draw_pixel(p, spx, lx, ly + i, label_color);
        draw_pixel(p, spx, lx + tw - 1, ly + i, label_color);
    }
}

/* ---- 8. 纯色方块 + 灰度方块 ---- */
static void draw_pattern_color_squares(uint32_t *p, int w, int h, int spx)
{
    /* 黑色背景 */
    fill_rect(p, spx, 0, 0, w, h, 0xFF404040);

    int cols = 5, rows = 3;
    int sw = w / cols, sh = h / rows;

    static const uint32_t colors[] = {
        0xFFFF0000, /* 红 */ 0xFF00FF00, /* 绿 */ 0xFF0000FF, /* 蓝 */
        0xFFFFFF00, /* 黄 */ 0xFFFF00FF, /* 品 */
        0xFF00FFFF, /* 青 */ 0xFFFFFFFF, /* 白 */ 0xFF000000, /* 黑 */
        0xFFFF8000, /* 橙 */ 0xFF8000FF, /* 紫 */ 0xFF0080FF, /* 天蓝 */
        0xFF00FF80, /* 青绿 */ 0xFF80FF00, /* 黄绿 */ 0xFFFF0080, /* 粉 */
        0xFF808080, /* 灰 */
    };

    int n = sizeof(colors) / sizeof(colors[0]);
    int idx = 0;
    for (int row = 0; row < rows && idx < n; row++) {
        for (int col = 0; col < cols && idx < n; col++, idx++) {
            int mx = col * sw + 10;
            int my = row * sh + 10;
            int mw = sw - 20;
            int mh = sh - 20;
            fill_rect(p, spx, mx, my, mw, mh, colors[idx]);
        }
    }
}

/* ---- 测试图案表 ---- */
struct test_pattern {
    const char *name;
    void (*draw)(uint32_t *pixels, int w, int h, int stride_px);
};

static const struct test_pattern patterns[] = {
    { "Border Mark",      draw_pattern_border_mark      },
    { "Color Bars",       draw_pattern_color_bars       },
    { "Grayscale",        draw_pattern_grayscale        },
    { "RGB Gradient",     draw_pattern_rgb_gradient     },
    { "Color Squares",    draw_pattern_color_squares    },
};
#define NUM_PATTERNS  (sizeof(patterns) / sizeof(patterns[0]))

/* ==================================================================
 * 主程序
 * ================================================================*/

int main(void)
{
    struct display *d;
    struct display_plane *plane;
    struct display_buffer *buf[2];
    int pattern_idx = 0;

    /* 1. 初始化显示设备 */
    d = display_init(0);
    if (!d) {
        fprintf(stderr, "错误: display_init 失败 (需要 root 权限?)\n");
        return -1;
    }
    printf("===== K230 Display Test =====\n");
    printf("显示分辨率: %u x %u\n", d->width, d->height);
    printf("物理尺寸: %u x %u mm\n", d->mmWidth, d->mmHeight);
    printf("共 %zu 种测试图形, 每 3 秒切换\n\n", NUM_PATTERNS);

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
            fprintf(stderr, "错误: 分配 buf[%d] 失败\n", i);
            for (int j = 0; j < i; j++) display_free_buffer(buf[j]);
            display_free_plane(plane);
            display_exit(d);
            return -1;
        }
    }

    /* 4. 首次提交：显示第一个图案 */
    patterns[0].draw((uint32_t *)buf[0]->map, d->width, d->height,
                     buf[0]->stride / 4);
    patterns[0].draw((uint32_t *)buf[1]->map, d->width, d->height,
                     buf[1]->stride / 4);
    display_update_buffer(buf[0], 0, 0);
    display_commit(d);
    display_wait_vsync(d);

    printf("[P1] %s\n", patterns[0].name);

    /* 5. 循环切换测试图形 */
    for (int frame = 0;; frame++) {
        int back = 1 - (frame % 2);

        /* 每约 3 秒切换一个图案 (60 fps × 180 帧 ≈ 3 秒) */
        if (frame > 0 && frame % 180 == 0) {
            pattern_idx = (pattern_idx + 1) % NUM_PATTERNS;
            printf("[P%d] %s\n", pattern_idx + 1, patterns[pattern_idx].name);
        }

        /* 在后台缓冲区绘制当前图案 */
        patterns[pattern_idx].draw((uint32_t *)buf[back]->map,
                                   d->width, d->height,
                                   buf[back]->stride / 4);

        display_update_buffer(buf[back], 0, 0);
        display_commit(d);
        display_wait_vsync(d);
    }

    /* 6. 清理 (实际上不会到达这里, 用 Ctrl+C 退出) */
    for (int i = 0; i < 2; i++) display_free_buffer(buf[i]);
    display_free_plane(plane);
    display_exit(d);
    return 0;
}
