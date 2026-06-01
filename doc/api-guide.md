# k230_display 库接口说明文档

## 概述

`k230_display` 是一个基于 Linux DRM (Direct Rendering Manager) 子系统的显示库，封装了 libdrm 的原子 (Atomic) 模式设置接口，提供简洁的 C 语言 API 用于显示输出。同时提供了一个 C++ 的 Pipeline 框架，支持基于 DMA-BUF 的多媒体数据流水线处理。

该库支持以下像素格式：
- NV12 / NV21（YUV 半平面格式）
- RGB565 / BGR565
- RGB888 / BGR888
- ARGB8888 / ABGR8888 / RGBA8888 / BGRA8888

---

## 目录

1. [C 语言 API](#1-c-语言-api)
   - [1.1 显示初始化与退出](#11-显示初始化与退出)
   - [1.2 图层 (Plane) 管理](#12-图层-plane-管理)
   - [1.3 缓冲区管理](#13-缓冲区管理)
   - [1.4 提交显示](#14-提交显示)
   - [1.5 VSync 同步](#15-vsync-同步)
   - [1.6 C API 调用示例](#16-c-api-调用示例)
2. [C++ Pipeline API](#2-c-pipeline-api)
   - [2.1 Pipeline 框架](#21-pipeline-框架)
   - [2.2 Display 类](#22-display-类)
   - [2.3 VideoCapture 类](#23-videocapture-类)
   - [2.4 C++ API 调用示例](#24-c-api-调用示例)
3. [编译与安装](#3-编译与安装)
4. [常见问题](#4-常见问题)

---

## 1. C 语言 API

### 数据结构

#### `struct display`

核心显示设备对象，保存 DRM 文件描述符、连接器 (Connector)、CRTC、编码器 (Encoder) 等信息。

```c
struct display {
    int fd;                              // DRM 设备文件描述符
    uint32_t conn_id, enc_id, crtc_id, blob_id;
    int crtc_idx;
    uint32_t width, height;              // 当前显示分辨率
    uint32_t mmWidth, mmHeight;          // 显示器物理尺寸 (mm)
    drmModeModeInfo mode;                // 当前显示模式
    drmModeCrtcPtr crtc;
    drmModePropertyPtr crtc_props[MAX_PROPS];
    uint32_t crtc_props_count;
    drmModeConnectorPtr conn;
    drmModePropertyPtr conn_props[MAX_PROPS];
    uint32_t conn_props_count;
    drmModeAtomicReqPtr req;             // 原子请求对象
    uint32_t commitFlags;
    drmEventContext drm_event_ctx;       // DRM 事件上下文
    enum drm_rotation drm_rotation;      // 旋转角度
    struct display_plane* planes;        // 已获取的图层链表
};
```

#### `struct display_plane`

表示一个 DRM 图层 (Plane)。

```c
struct display_plane {
    struct display_plane* next;          // 链表下一节点
    struct display* display;             // 所属 display 对象
    drmModePlanePtr plane;
    drmModePropertyPtr props[MAX_PROPS];
    uint8_t props_count;
    uint32_t plane_id;
    unsigned int fourcc;                 // 像素格式 (如 DRM_FORMAT_NV12)
    bool first;                          // 是否首次提交 (标记是否需 modeset)
    enum drm_rotation drm_rotation;      // 旋转角度
    struct display_buffer* buffers;      // 关联的缓冲区链表
};
```

#### `struct display_buffer`

表示一个显示缓冲区 (基于 dumb buffer)。

```c
struct display_buffer {
    struct display_buffer* next;         // 链表下一节点
    struct display_plane* plane;         // 所属图层
    uint32_t handle;                     // dumb buffer 句柄
    uint32_t stride, width, height;      // 步幅、宽、高
    uint32_t size;                       // 缓冲区大小 (字节)
    int dmabuf_fd;                       // dma-buf 文件描述符 (用于与其他模块共享)
    uint32_t id;                         // framebuffer 对象 ID
    enum drm_rotation drm_rotation;      // 旋转角度
    void* map;                           // mmap 映射地址 (CPU 可直接读写)
};
```

#### `enum drm_rotation`

```c
enum drm_rotation {
    rotation_0   = 0,  // 不旋转
    rotation_90  = 1,  // 顺时针旋转 90°
    rotation_180 = 2,  // 旋转 180°
    rotation_270 = 3,  // 顺时针旋转 270°
};
```

---

### 1.1 显示初始化与退出

#### `display_init()`

```c
struct display* display_init(unsigned device);
```

**功能**：初始化显示设备。

- **参数** `device`：DRM 设备编号。例如 `0` 对应 `/dev/dri/card0`。
- **返回值**：成功返回 `struct display*` 指针；失败返回 `NULL`。
- **说明**：该函数会打开 DRM 设备、查找已连接的显示器、选择最佳显示模式（优先选择不超过 1920×1080@60Hz 的模式）、设置原子 (Atomic) 模式、获取 CRTC 和 Connector 的属性列表。
- **注意**：内部调用 `drmSetClientCap(fd, DRM_CLIENT_CAP_ATOMIC, 1)` 启用原子 API，要求内核 DRM 驱动支持原子接口。

#### `display_exit()`

```c
void display_exit(struct display* display);
```

**功能**：释放显示设备资源。

- **参数** `display`：由 `display_init()` 返回的指针。
- **说明**：会依次释放所有已分配的图层 (Plane) 和缓冲区，关闭 DRM 设备文件描述符，最后释放 `display` 对象本身。

---

### 1.2 图层 (Plane) 管理

#### `display_get_plane()`

```c
struct display_plane* display_get_plane(struct display* display, unsigned int fourcc);
```

**功能**：从 DRM 设备中获取一个支持指定像素格式且未被占用的图层 (Plane)。

- **参数**：
  - `display`：显示设备对象。
  - `fourcc`：所需的像素格式，使用 DRM FourCC 编码，如 `DRM_FORMAT_NV12`、`DRM_FORMAT_ARGB8888` 等。
- **返回值**：成功返回 `struct display_plane*`；失败返回 `NULL`。
- **说明**：
  - 遍历系统中的所有 Plane，寻找与指定 CRTC 兼容且支持目标格式的 Plane。
  - 已经通过本函数获取过的 Plane（在 `display->planes` 链表中）会被跳过，不会重复获取。
  - 对于 NV12 格式且旋转角度为 90° 或 270° 的情况，会额外检查 Plane 是否支持 `rotation` 属性。
  - 获取到的 Plane 会自动添加到 `display->planes` 链表中。

#### `display_free_plane()`

```c
void display_free_plane(struct display_plane* plane);
```

**功能**：释放一个图层及其所有关联的缓冲区。

- **参数** `plane`：要释放的图层对象。
- **说明**：会从 `display->planes` 链表中移除该节点，释放该图层下的所有缓冲区，然后释放 Plane 对象本身。

---

### 1.3 缓冲区管理

#### `display_allocate_buffer()`

```c
struct display_buffer* display_allocate_buffer(struct display_plane* plane,
                                                uint32_t width, uint32_t height);
```

**功能**：为指定图层分配一个显示缓冲区。

- **参数**：
  - `plane`：目标图层。
  - `width`、`height`：缓冲区宽度和高度（像素）。
- **返回值**：成功返回 `struct display_buffer*`；失败返回 `NULL`。
- **说明**：
  - 内部创建 dumb buffer，根据图层的 fourcc 格式自动计算 bits per pixel。
  - 对于 NV12/NV21 格式，内部高度会自动扩展为 `height * 3 / 2` 以容纳 Y 和 UV 两个平面。
  - 创建 dma-buf 文件描述符 (`dmabuf_fd`)，可用于与其他硬件模块（如 ISP、VPU）共享缓冲区。
  - 通过 mmap 将缓冲区映射到用户空间，可直接通过 `map` 指针读写像素数据。
  - 缓冲区清零后自动添加到 `plane->buffers` 链表中。
  - 调用 `drmModeAddFB2` 注册 framebuffer。

#### `display_free_buffer()`

```c
void display_free_buffer(struct display_buffer* buffer);
```

**功能**：释放一个显示缓冲区。

- **参数** `buffer`：要释放的缓冲区对象。
- **说明**：会 munmap 解除映射、销毁 dumb buffer、从 `plane->buffers` 链表中移除，并释放内存。

---

### 1.4 提交显示

#### `display_update_buffer()`

```c
int display_update_buffer(struct display_buffer* buffer, uint32_t x, uint32_t y);
```

**功能**：将缓冲区的内容设置到待提交的原子请求中。

- **参数**：
  - `buffer`：要显示的缓冲区。
  - `x`、`y`：显示在屏幕上的起始坐标。
- **返回值**：成功返回 `0`；失败返回负值。
- **说明**：
  - 该函数**不直接提交**到硬件，而是将属性添加到 `display->req`（原子请求对象）中。
  - 如果该图层是首次提交 (`plane->first == true`)，则会额外添加 `MODE_ID`、`ACTIVE` 和 `CRTC_ID` 等连接器/CRTC 属性，并设置 `DRM_MODE_ATOMIC_ALLOW_MODESET` 标志。
  - 设置的属性包括：`FB_ID`（帧缓冲 ID）、`CRTC_ID`、`SRC_*`（源裁剪区域，16.16 定点格式）、`CRTC_*`（目标显示位置和大小）。
  - 对于 NV12 格式，会根据 `drm_rotation` 设置旋转属性。

#### `display_commit_buffer()`

```c
int display_commit_buffer(const struct display_buffer* buffer, uint32_t x, uint32_t y);
```

**功能**：**一步式**提交缓冲区显示（分配原子请求 → 设置属性 → 提交）。

- **参数**：
  - `buffer`：要显示的缓冲区。
  - `x`、`y`：显示在屏幕上的起始坐标。
- **返回值**：成功返回 `0`；失败返回 `-1`。
- **说明**：
  - 该函数内部会自行创建原子请求 (`drmModeAtomicReqPtr`)，设置所有属性后立即调用 `drmModeAtomicCommit`。
  - 适用于简单的一次性显示场景，不需要后续的缓冲区更新。
  - 如果该图层是首次提交，会设置 `DRM_MODE_ATOMIC_ALLOW_MODESET` 标志。

#### `display_commit()`

```c
int display_commit(struct display* display);
```

**功能**：提交累积的原子请求到硬件（配合 `display_update_buffer` 使用）。

- **参数** `display`：显示设备对象。
- **返回值**：成功返回 `0`；失败返回 `-1`。
- **说明**：
  - 将之前通过 `display_update_buffer()` 累积的属性一次性提交。
  - 适用于需要同时更新多个 Plane 的场景（例如主图层和光标图层同时更新）。
  - 提交后，`display->commitFlags` 会被重置为 `DRM_MODE_PAGE_FLIP_EVENT`。

---

### 1.5 VSync 同步

#### `display_wait_vsync()`

```c
void display_wait_vsync(struct display* display);
```

**功能**：等待下一次垂直同步信号（阻塞方式）。

- **参数** `display`：显示设备对象。
- **说明**：
  - 使用 `select()` 系统调用阻塞等待 DRM 事件。
  - 收到事件后调用 `drmHandleEvent()` 处理 page flip 事件。
  - 最后释放原子请求对象 (`display->req`)。
  - **注意**：此函数会阻塞当前线程，在高帧率流水线场景中推荐使用非阻塞方式处理事件。

#### `display_handle_vsync()`

```c
void display_handle_vsync(struct display* display);
```

**功能**：处理 VSync 事件（非阻塞方式）。

- **参数** `display`：显示设备对象。
- **说明**：
  - 调用 `drmHandleEvent()` 处理已就绪的 DRM 事件。
  - 释放原子请求对象。
  - 配合 `select()`/`poll()` 在事件循环中使用，不会阻塞等待。

---

### 1.6 C API 调用示例

以下是一个完整的使用 C API 显示一帧画面的流程：

```c
#include "display.h"
#include <drm/drm_fourcc.h>
#include <string.h>

int main(void) {
    // 1. 初始化显示设备
    struct display* d = display_init(0);
    if (!d) return -1;

    // 2. 获取一个 NV12 格式的图层
    struct display_plane* plane = display_get_plane(d, DRM_FORMAT_NV12);
    if (!plane) {
        display_exit(d);
        return -1;
    }

    // 3. 分配缓冲区 (1920×1080)
    struct display_buffer* buf = display_allocate_buffer(plane, 1920, 1080);
    if (!buf) {
        display_free_plane(plane);
        display_exit(d);
        return -1;
    }

    // 4. 填充像素数据（通过 mmap 映射直接写入）
    //    对于 NV12，Y 平面在前，UV 平面在后
    memset(buf->map, 0x80, buf->size);  // 填充灰色

    // 5. 提交到显示
    if (display_commit_buffer(buf, 0, 0) != 0) {
        fprintf(stderr, "commit failed\n");
    }

    // 6. 等待 VSync
    display_wait_vsync(d);

    // 7. 清理资源
    display_free_buffer(buf);
    display_free_plane(plane);
    display_exit(d);
    return 0;
}
```

**多缓冲区 + 双缓冲更新的典型流程：**

```c
struct display* d = display_init(0);
struct display_plane* plane = display_get_plane(d, DRM_FORMAT_ARGB8888);

// 分配多个缓冲区（例如 3 个，实现三缓冲）
struct display_buffer* bufs[3];
for (int i = 0; i < 3; i++) {
    bufs[i] = display_allocate_buffer(plane, 1920, 1080);
}

// 渲染循环
int cur = 0;
while (running) {
    // 向 bufs[cur] 中填充新帧
    render_frame(bufs[cur]->map, bufs[cur]->size);

    // 更新显示
    display_update_buffer(bufs[cur], 0, 0);
    display_commit(d);

    // 等待 VSync 处理完成
    display_wait_vsync(d);

    cur = (cur + 1) % 3;
}

// 清理
for (int i = 0; i < 3; i++) display_free_buffer(bufs[i]);
display_free_plane(plane);
display_exit(d);
```

---

## 2. C++ Pipeline API

Pipeline 框架定义在 `pipeline.hpp` 中，位于 `pipeline` 命名空间下。它提供了一套基于 `select()` 事件驱动和 DMA-BUF 缓冲区共享的数据流处理框架，用于将数据源（如摄像头）与数据接收端（如显示）连接起来。

### 2.1 Pipeline 框架

#### `pipeline::Endpoint`（抽象基类）

所有数据流端点（数据源或数据接收端）的基类。

```cpp
class Endpoint {
public:
    virtual Capbility get_capbility() = 0;          // 获取能力：支持导入/导出/两者
    virtual bool set_buffer_num(unsigned channel, unsigned num) = 0;  // 设置缓冲区数量
    virtual bool import_buffer(unsigned channel, int fd, unsigned index, unsigned size);
    virtual int export_buffer(unsigned channel, unsigned index, unsigned& size);
    virtual bool buffer_in(unsigned channel, unsigned index) = 0;     // 接收缓冲区
    virtual int buffer_out(unsigned channel) = 0;    // 输出缓冲区（返回索引）
    virtual bool start();                            // 启动端点
    virtual void stop();                             // 停止端点
    virtual int fd_to_select() = 0;                  // 返回可 select 的文件描述符
};
```

#### `pipeline::Pipeline`（流水线引擎）

管理数据源到数据接收端的连接和事件循环。

```cpp
class Pipeline {
public:
    Pipeline();
    ~Pipeline();

    bool link(Endpoint& source, Endpoint& sink, unsigned bufferNum = 5);
    // 连接数据源和数据接收端。
    // bufferNum: 缓冲区数量（默认为 5）。
    // 返回值: 成功返回 true。
    // 说明:
    //   - 从接收端导出缓冲区（export_buffer），导入到数据源（import_buffer）；
    //     如果接收端不支持导出，则尝试从数据源导出。
    //   - 将双方的 fd 添加到 select 监听集合中。

    int run();
    // 启动流水线事件循环。
    // 说明:
    //   - 调用所有端点的 start() 方法。
    //   - 使用 select() 轮询所有端点的文件描述符。
    //   - 当数据源有数据可读时: 调用 buffer_out() 取出缓冲区，
    //     然后传递给所有已连接的数据接收端的 buffer_in()。
    //   - 当数据接收端有数据可读时: 调用 buffer_out() 取出缓冲区，
    //     归还给对应的数据源。
    //   - 超时 100ms 后重新轮询。

    void stop();
    // 停止流水线。调用所有端点的 stop() 方法，设置运行标志为 false。
};
```

#### 枚举 `Capbility`

```cpp
enum Capbility {
    SupportImport = 1,  // 支持导入缓冲区（从外部接收 dma-buf）
    SupportExport = 2,  // 支持导出缓冲区（对外提供 dma-buf）
    SupportBoth   = 3   // 同时支持导入和导出
};
```

---

### 2.2 Display 类

`pipeline::Display` 是显示输出端点，继承自 `Endpoint`，封装了 C API 的显示功能。

#### 静态工厂方法

```cpp
static std::optional<Display> create(unsigned device = 0);
```

创建 Display 对象。

- **参数** `device`：DRM 设备编号，默认为 0。
- **返回值**：成功返回 `std::optional<Display>`；失败返回 `std::nullopt`。
- **说明**：内部调用 `display_init()` 初始化显示设备。

#### 构造函数

```cpp
Display(struct display* d);           // 从已有的 display 对象构造
Display(Display&& ds);                // 移动构造
~Display();                           // 析构时自动调用 display_exit()
```

#### 通道管理

```cpp
bool createChannel(unsigned width, unsigned height, uint32_t fourcc);
```

创建一个显示通道（即一个图层 Plane）。

- **参数**：
  - `width`、`height`：显示分辨率。
  - `fourcc`：像素格式（如 `DRM_FORMAT_NV12`）。
- **返回值**：成功返回 `true`。
- **说明**：内部调用 `display_get_plane()` 获取图层。可在同一个 Display 上多次调用以创建多个图层（如主视频 + UI 叠加）。

#### Endpoint 接口实现

```cpp
Capbility get_capbility();     // 返回 SupportExport（仅支持导出）
bool start();                  // 提交第一个缓冲区到显示
bool set_buffer_num(unsigned channel, unsigned num);  // 设置缓冲区数量（调整 vector 大小）
int export_buffer(unsigned channel, unsigned index, unsigned& size);  // 分配并导出 dma-buf
bool buffer_in(unsigned channel, unsigned index);     // 送入缓冲区用于显示
int buffer_out(unsigned channel);                     // 取出已显示的缓冲区
int fd_to_select();            // 返回 DRM 文件描述符
```

---

### 2.3 VideoCapture 类

`pipeline::VideoCapture` 是 V4L2 摄像头采集端点，继承自 `Endpoint`。

#### 静态工厂方法

```cpp
static std::optional<VideoCapture> create(unsigned device, unsigned width,
                                          unsigned height, uint32_t fourcc);
```

打开 V4L2 视频采集设备。

- **参数**：
  - `device`：V4L2 设备编号，例如 `1` 对应 `/dev/video1`。
  - `width`、`height`：采集分辨率。
  - `fourcc`：像素格式（如 `V4L2_PIX_FMT_NV12`）。
- **返回值**：成功返回 `std::optional<VideoCapture>`；失败返回 `std::nullopt`。
- **说明**：打开设备时会枚举并打印该设备支持的所有格式，然后设置指定格式和分辨率。

#### Endpoint 接口实现

```cpp
Capbility get_capbility();     // 返回 SupportBoth（导入、导出都支持）
bool start();                  // VIDIOC_STREAMON 启动采集
void stop();                   // VIDIOC_STREAMOFF 停止采集
bool set_buffer_num(unsigned channel, unsigned num);  // VIDIOC_REQBUFS 申请缓冲区
int export_buffer(unsigned channel, unsigned index, unsigned& size);  // MMAP + VIDIOC_EXPBUF
bool import_buffer(unsigned channel, int fd, unsigned index, unsigned size);  // DMABUF 方式 QBUF
int buffer_out(unsigned channel);    // VIDIOC_DQBUF 出队
bool buffer_in(unsigned channel, unsigned index);    // VIDIOC_QBUF 入队
int fd_to_select();            // 返回 V4L2 设备文件描述符
```

---

### 2.4 C++ API 调用示例

以下示例展示如何将摄像头采集的数据直接通过 Pipeline 流水线显示到屏幕上：

```cpp
#include "display.h"
#include "pipeline.hpp"
#include <drm/drm_fourcc.h>
#include <linux/videodev2.h>
#include <signal.h>

using namespace pipeline;

Pipeline main_pipe;

void sighandler(int sig) {
    main_pipe.stop();
}

int main(void) {
    // 1. 初始化显示设备
    auto d = display_init(0);
    if (!d) {
        fprintf(stderr, "display_init failed\n");
        return -1;
    }

    // 2. 创建 Display 端点并创建显示通道
    auto display = Display(d);
    if (!display.createChannel(1920, 1080, DRM_FORMAT_NV12)) {
        fprintf(stderr, "create display channel error\n");
        return -1;
    }

    // 3. 创建 VideoCapture 端点（摄像头 /dev/video1）
    auto vicap = VideoCapture::create(1, 1920, 1080, V4L2_PIX_FMT_NV12);
    if (!vicap) {
        fprintf(stderr, "create video capture error\n");
        return -1;
    }

    // 4. 连接数据源（摄像头）到数据接收端（显示）
    //    内部会自动分配 dma-buf 缓冲区并在两端共享
    if (!main_pipe.link(*vicap, display)) {
        fprintf(stderr, "link error\n");
        return -1;
    }

    // 5. 注册信号处理函数以便 Ctrl+C 时优雅退出
    signal(SIGINT, sighandler);
    signal(SIGTERM, sighandler);

    // 6. 启动流水线事件循环
    main_pipe.run();

    return 0;
}
```

**多图层叠加示例（视频 + UI 叠加）：**

```cpp
auto d = display_init(0);
auto display = Display(d);

// 创建两个显示通道：视频层 + UI 层
display.createChannel(1920, 1080, DRM_FORMAT_NV12);  // 通道 0: 视频
display.createChannel(1920, 1080, DRM_FORMAT_ARGB8888); // 通道 1: UI 叠加

auto vicap = VideoCapture::create(1, 1920, 1080, V4L2_PIX_FMT_NV12);
auto ui_source = ...;  // 另一个数据源

main_pipe.link(*vicap, display);   // 摄像头 → 视频层 (通道 0)
main_pipe.link(*ui_source, display); // UI → UI 层 (通道 1)

main_pipe.run();
```

---

## 3. 编译与安装

### 使用 Makefile 编译

```shell
# 编译库和测试程序
make

# 仅编译库
make library

# 仅编译测试程序
make test

# 安装到系统
sudo make install

# 卸载
sudo make uninstall
```

### 使用 CMake 编译

```shell
mkdir build && cd build
cmake .. -DBUILD_TEST=1
make
```

### 依赖

- libdrm（必需）
- Linux 内核 DRM 驱动支持 Atomic API
- pkg-config（CMake 编译时需要）

### 安装位置

- 头文件：`/usr/local/include/`
- 库文件：`/usr/local/lib/libdisplay.so`
- pkg-config：`/usr/local/lib/pkgconfig/display.pc`

### 在自己的项目中使用

通过 pkg-config 链接：

```makefile
CFLAGS += $(shell pkg-config --cflags display)
LDFLAGS += $(shell pkg-config --libs display)
```

或直接链接：

```shell
gcc -o myapp myapp.c -ldisplay -ldrm
```

---

## 4. 常见问题

### Q: 调用 `display_init()` 返回 NULL

可能的原因：
- 没有足够的权限访问 DRM 设备（尝试以 root 运行或添加用户到 `video` 组）。
- 内核 DRM 驱动不支持原子 (Atomic) API。
- 没有检测到已连接的显示器。

### Q: `display_get_plane()` 返回 NULL

可能的原因：
- 系统中没有可用的、支持指定格式的 Plane。
- 所有兼容的 Plane 已被占用。
- 指定了不支持的 FourCC 格式。

### Q: NV12 旋转不生效

NV12 格式在旋转 90° 或 270° 时要求 Plane 支持 `rotation` 属性。请确认：
1. DRM 驱动支持 Plane 级别的旋转。
2. `display->drm_rotation` 已正确设置。
3. 使用的 Plane 确实包含 `rotation` 属性。

### Q: Pipeline 运行后没有画面

排查步骤：
1. 确认摄像头设备节点正确（如 `/dev/video1`）。
2. 确认摄像头支持所请求的像素格式和分辨率。
3. 检查 dma-buf 是否成功在 VideoCapture 和 Display 之间传递。
4. 确认 `display.createChannel()` 的 fourcc 格式与摄像头输出格式匹配。
