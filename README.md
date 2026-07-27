# BongoCat 桌宠

一只坐在桌面上的猫，跟着你真实的键盘和鼠标动作敲键盘、握鼠标。零依赖，只用系统自带的 Python + tkinter，角色是 Canvas 画出来的，不需要任何图片素材。

![platform](https://img.shields.io/badge/platform-Windows-blue)
![python](https://img.shields.io/badge/python-3.8%2B-green)

## 运行

```bash
python bongocat.py
```

或者双击 `启动BongoCat.bat`（用 pythonw 启动，不留黑窗口）。

仓库里还有一个早期的通用桌宠版本 `pet.py`，是会自己溜达、跳跃、睡觉的状态机版：

```bash
python pet.py
```

## 它会做什么

- **敲键盘**：你按左半区的键左爪落下，右半区右爪落下，键盘上对应的键会亮起并下沉
- **握鼠标**：动鼠标时右爪移到鼠标垫上，垫子上那只小鼠标跟着你的真实光标同向移动，点击时爪子会压下去
- **看光标**：眼球跟着鼠标位置转
- **打字热度**：敲得越快，耳朵抖得越厉害，尾巴摆得越快
- **发呆和睡觉**：闲置一会儿会打哈欠、睡着冒 Zzz

键盘、鼠标垫、鼠标是朝着猫摆的（猫在用，不是我们在用），三者共用同一个倾斜变换，键帽上的字母也转向猫那侧，从猫的视角读才是正序的 QWERTY。

## 操作

- 拖动：按住左键把猫拖到桌面任意位置，位置会记住
- 右键：菜单，可以调缩放、透明度、左右镜像、鼠标穿透、贴自己的头像
- 退出：右键菜单里退出

## 项目结构

```
bongocat.py        入口
bongo/
  app.py           窗口、主循环、右键菜单、状态
  cat.py           角色与桌面（键盘/鼠标垫/鼠标）绘制
  inputs.py        全局键鼠监听、打字热度、光标归一化
  winapi.py        Win32 调用封装（置顶、穿透、透明色）
  config.py        配置读写
pet.py, sprite.py  早期通用桌宠版本（独立可运行）
```

想改外观，配色常量都在 `bongo/cat.py` 顶部；桌面倾斜角度是同一个文件里的 `TILT_DEG`，改一处键盘、垫子、鼠标一起转。

## 平台说明

窗口透明依赖 Windows 的 `-transparentcolor` 属性，全局键鼠监听走的是 Win32 API，所以完整效果目前只在 Windows 上。代码里对非 Windows 做了兜底不会崩，但会退化成一个带底色的方块。

## License

MIT
