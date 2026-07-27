"""桌宠主程序：无边框透明窗口 + 状态机 + 鼠标交互。

运行：  python pet.py
退出：  右键菜单 → 退出，或双击角色后选退出
"""

import ctypes
import math
import random
import sys
import tkinter as tk

from sprite import draw_pet, draw_bubble


def virtual_desktop(root):
    """返回所有显示器拼成的整块区域 (x, y, w, h)。

    tkinter 的 winfo_screenwidth() 只认主屏，副屏在主屏左边或上边时
    坐标是负数，会被夹回主屏。这里问 Windows 要真正的虚拟桌面边界。
    """
    if sys.platform == "win32":
        try:
            g = ctypes.windll.user32.GetSystemMetrics
            # 76/77 = 虚拟桌面左上角，78/79 = 虚拟桌面宽高
            x, y, w, h = g(76), g(77), g(78), g(79)
            if w > 0 and h > 0:
                return x, y, w, h
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()

# 透明色：窗口里这个颜色的像素会被系统抠掉，只留下角色
TRANSPARENT = "#ff00ff"

W, H = 200, 200          # 窗口尺寸
FPS_MS = 33              # 每帧间隔，约 30fps
SCALE = 1.0
GROUND = H - 26          # 角色脚底在窗口内的 y 坐标

TALK = [
    "阿正，写代码记得歇会儿～",
    "今天也要加油哦！",
    "要不要摸摸我的头？",
    "咕……有点饿了",
    "我在这里陪你敲代码",
    "拖我到别处也可以呀",
]


class Pet:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("桌宠")
        self.root.overrideredirect(True)          # 去掉标题栏
        self.root.attributes("-topmost", True)    # 永远置顶
        self.root.configure(bg=TRANSPARENT)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass  # 非 Windows 平台不支持，退化成有底色的方块

        # 整块虚拟桌面（含所有副屏）作为活动范围
        vx, vy, vw, vh = virtual_desktop(self.root)
        self.vx0, self.vy0, self.vw, self.vh = vx, vy, vw, vh
        self.x = vx + vw - W - 60
        self.y = vy + vh - H - 90
        self.root.geometry(f"{W}x{H}")
        self.move_window()

        self.canvas = tk.Canvas(self.root, width=W, height=H,
                                bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack()

        # ---- 状态 ----
        self.state = "idle"       # idle / walk / jump / drag / pet / sleep
        self.timer = 0            # 当前状态已持续的帧数
        self.facing = 1
        self.vx = 0.0
        self.vy = 0.0
        self.pet_y = 0.0          # 角色在窗口内的额外垂直偏移（跳跃用）
        self.squash = 0.0
        self.tail = 0.0
        self.blink = 0
        self.blink_next = random.randint(60, 150)
        self.bubble = ""
        self.bubble_left = 0
        self.idle_since_input = 0
        self.drag_dx = self.drag_dy = 0
        self.drag_last = (self.x, self.y)
        self.happy = 0

        self._bind()
        self._menu()
        self.say("阿正，我来啦！", 90)
        self.tick()

    # ------------------------------------------------------------ 交互
    def _bind(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Double-Button-1>", self.on_double)
        c.bind("<Button-3>", self.on_right)
        c.bind("<Enter>", lambda e: self.wake())

    def _menu(self):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="打个招呼", command=lambda: self.set_state("pet"))
        m.add_command(label="跳一下", command=self.jump)
        m.add_command(label="去散步", command=lambda: self.set_state("walk"))
        m.add_command(label="睡觉", command=lambda: self.set_state("sleep"))
        m.add_separator()
        m.add_command(label="退出", command=self.root.destroy)
        self.menu = m

    def on_press(self, e):
        self.wake()
        self.drag_dx, self.drag_dy = e.x, e.y
        self.drag_last = (self.x, self.y)
        self.set_state("drag")

    def on_drag(self, e):
        if self.state != "drag":
            return
        self.drag_last = (self.x, self.y)
        self.x = self.root.winfo_pointerx() - self.drag_dx
        self.y = self.root.winfo_pointery() - self.drag_dy
        self.clamp()
        self.move_window()

    def on_release(self, e):
        if self.state != "drag":
            return
        # 松手时把拖拽速度转成惯性
        self.vx = max(-14, min(14, (self.x - self.drag_last[0]) * 0.6))
        self.set_state("jump")
        self.vy = -4

    def on_double(self, e):
        self.happy += 1
        self.set_state("pet")
        self.say(random.choice(TALK), 110)

    def on_right(self, e):
        self.wake()
        self.menu.tk_popup(e.x_root, e.y_root)

    def wake(self):
        self.idle_since_input = 0
        if self.state == "sleep":
            self.set_state("idle")
            self.say("唔……醒了", 60)

    # ------------------------------------------------------------ 状态
    def set_state(self, s):
        self.state = s
        self.timer = 0
        if s == "walk":
            self.vx = random.choice((-2.2, 2.2))
            self.facing = 1 if self.vx > 0 else -1
        elif s == "sleep":
            self.vx = 0
            self.say("Zzz……", 70)
        elif s == "pet":
            self.vx = 0

    def jump(self):
        if self.state in ("drag",):
            return
        self.set_state("jump")
        self.vy = -11
        self.squash = -0.5

    def say(self, text, frames):
        self.bubble = text
        self.bubble_left = frames

    def clamp(self):
        self.x = max(self.vx0, min(self.vx0 + self.vw - W, self.x))
        self.y = max(self.vy0, min(self.vy0 + self.vh - H, self.y))

    def move_window(self):
        """写窗口位置。

        geometry 里裸的 "-100" 会被 Tk 理解成「距右边缘 100」，
        所以负的绝对坐标要写成 "+-100" —— f-string 拼出来正好是这个形式，
        副屏在主屏左侧（x 为负）时才不会跑错屏。
        """
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

    # ------------------------------------------------------------ 主循环
    def tick(self):
        self.timer += 1
        self.tail += 0.18 if self.state != "sleep" else 0.05
        self.idle_since_input += 1

        if self.bubble_left > 0:
            self.bubble_left -= 1

        # 眨眼
        self.blink_next -= 1
        if self.blink_next <= 0:
            self.blink = 6
            self.blink_next = random.randint(70, 190)
        if self.blink > 0:
            self.blink -= 1

        getattr(self, f"_upd_{self.state}")()

        # 挤压量缓慢回弹
        self.squash *= 0.82

        self.move_window()
        self.render()
        self.root.after(FPS_MS, self.tick)

    def _upd_idle(self):
        if self.idle_since_input > 900:      # 约 30 秒没人理 → 睡觉
            self.set_state("sleep")
            return
        if self.timer > random.randint(90, 220):
            self.set_state(random.choice(("walk", "walk", "jump", "idle")))
            if self.state == "jump":
                self.vy = -11
            if self.state == "idle" and random.random() < 0.5:
                self.say(random.choice(TALK), 110)

    def _upd_walk(self):
        self.x += self.vx
        # 撞到整块虚拟桌面的左右边缘才转身，中间的屏幕接缝可以直接走过去
        if self.x <= self.vx0 or self.x >= self.vx0 + self.vw - W:
            self.vx = -self.vx
            self.facing = 1 if self.vx > 0 else -1
        self.clamp()
        if self.timer > random.randint(70, 190):
            self.set_state("idle")

    def _upd_jump(self):
        self.vy += 0.85                      # 重力
        self.pet_y += self.vy
        self.x += self.vx
        self.vx *= 0.94
        if self.x <= self.vx0 or self.x >= self.vx0 + self.vw - W:
            self.vx = -self.vx * 0.7
        self.clamp()
        if self.pet_y >= 0:                  # 落地
            self.pet_y = 0
            self.vy = 0
            self.squash = 0.9
            self.set_state("idle")

    def _upd_drag(self):
        self.pet_y = 0
        self.squash = -0.25                  # 被拎着时身体拉长

    def _upd_pet(self):
        self.squash = 0.25 * math.sin(self.timer * 0.4)
        if self.timer > 60:
            self.set_state("idle")

    def _upd_sleep(self):
        self.squash = 0.12 + 0.06 * math.sin(self.timer * 0.06)

    # ------------------------------------------------------------ 绘制
    def render(self):
        c = self.canvas
        c.delete("all")

        eye = 0.0 if self.blink > 0 else 1.0
        mouth = "smile"
        if self.state == "pet":
            mouth = "open"
        elif self.state == "drag":
            mouth = "flat"

        baseline = GROUND + self.pet_y
        draw_pet(c, W / 2, baseline, SCALE,
                 squash=self.squash, eye=eye, mouth=mouth,
                 facing=self.facing, tail_phase=self.tail,
                 sleeping=(self.state == "sleep"))

        if self.bubble_left > 0 and self.state != "sleep":
            draw_bubble(c, W / 2, baseline - 96 * SCALE, self.bubble, SCALE)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Pet().run()
