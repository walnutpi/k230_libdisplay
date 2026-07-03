# k230_libdisplay
提供用于操作k230上drm的libdisplay库

- `src` libdisplay库的源码
- `include` libdisplay库对应的头文件
- `test-c` 测试程序

```shell
# 编译
make

# 安装到系统中
sudo make install
```

## Python 库使用方式

```python
import Display

Display.init()           # 初始化屏幕
Display.show(img)        # 将图像显示到屏幕上
Display.flush()          # 等待最后一帧完成（程序退出前调用）

print(Display.get_width())    # 获取屏幕宽度
print(Display.get_height())   # 获取屏幕高度
print(Display.get_size())     # 获取屏幕尺寸 (width, height)

Display.set_rotation(Display.ROTATION_90)  # 设置旋转角度
rotation = Display.get_rotation()           # 获取当前旋转角度
```

