#
# 使用方法:
#   make           构建当前目录下所有 .c 文件为同名 .out 可执行文件
#   make clean     清理构建产物

CC      = gcc
CFLAGS  = -Wall -Wextra -std=c11 -D_GNU_SOURCE
LDFLAGS = -ldisplay -ldrm
LIBM    = -lm

# display 库的路径
LIB_DIR     = ..
INCLUDE_DIR = ../include

# libdrm 头文件路径 (根据实际安装位置修改)
LIBDRM_INCLUDE_PATH ?= /usr/include/libdrm

INCLUDES = -I$(INCLUDE_DIR) -I$(LIBDRM_INCLUDE_PATH)

# 自动发现当前目录下所有 .c 文件
SRCS    := $(wildcard *.c)
# 将每个 .c 文件映射为同名 .out 可执行文件
PROGRAMS := $(SRCS:.c=.out)

# 默认目标: 构建所有示例
all: $(PROGRAMS)

# 通用模式规则: 每个 .c -> 同名 .out
# 自动链接 libdisplay.so 和 libdrm
%.out: %.c
	$(CC) $(CFLAGS) $(INCLUDES) -o $@ $< -L$(LIB_DIR) $(LDFLAGS) $(LIBM) -Wl,-rpath,$(LIB_DIR)

clean:
	rm -f $(PROGRAMS)


.PHONY: all clean