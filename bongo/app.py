"""主程序：透明置顶窗口 + 动画循环 + 托盘菜单。"""

import math
import random
import tkinter as tk
from tkinter import filedialog, messagebox

from . import config, winapi
from .cat import draw_cat
from .inputs import InputWatcher

TRANSPARENT = "#ff00ff"
FPS_MS = 25                  # 约 40fps，拍击手感更利落
BASE_W, BASE_H = 460, 300
IDLE_SLEEP = 1200            # 约 30 秒无输入则睡
STRIKE_HOLD = 3              # 拍下后按住的帧数，保证爪子真的落到台面

HOTKEY_HINT = "Ctrl+Alt+B"


class BongoCat:
    def __init__(self):
        winapi.set_dpi_aware()
        self.conf = config.load()
        self.root = tk.Tk()
        self.root.title("BongoCat")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass

        self.vx0, self.vy0, self.vw, self.vh = winapi.virtual_desktop(self.root)
        self.scale = float(self.conf["scale"])
        self._size()

        if self.conf["x"] is None:
            # 默认摆主屏右下角。不能用虚拟桌面右下角：多屏尺寸不一时
            # 那个角可能落在没有显示器的空洞里，窗口就彻底看不见了。
            mx, my, mw, mh, _ = winapi.primary_monitor(self.root)
            self.x = mx + mw - self.w - 40
            self.y = my + mh - self.h - 20
        else:
            self.x, self.y = self.conf["x"], self.conf["y"]
        self.clamp()

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT,
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # 动画状态
        self.left = 1.0          # 爪子当前抬起量
        self.right = 1.0
        self.left_t = 1.0        # 目标值
        self.right_t = 1.0
        self.left_hold = 0       # 拍下保持计时
        self.right_hold = 0
        self.on_mouse = False    # 右爪是否正握着鼠标
        self.look_x = self.look_y = 0.0
        self.tail = 0.0
        self.blink = 0
        self.blink_next = random.randint(70, 180)
        self.idle = 0
        self.sleeping = False
        self.heat = 0.0
        self.face_img = None
        self.drag_from = None
        self.hidden = bool(self.conf["hidden"])

        self.watch = InputWatcher()
        self._apply_geometry()
        self._apply_opacity()
        self._load_face()
        self._bind()
        self._build_menu()
        self._start_tray()
        # 穿透要在窗口映射后再设，否则句柄样式会被覆盖
        self.root.after(120, self._apply_click_through)
        if self.hidden:
            self.root.withdraw()
        self.tick()

    # ------------------------------------------------------- 尺寸与位置
    def _size(self):
        self.w = int(BASE_W * self.scale)
        self.h = int(BASE_H * self.scale)

    def clamp(self):
        """夹到当前所在的那块屏内，而不是整个虚拟桌面。

        按虚拟桌面夹会允许窗口停在屏幕间的空洞里（不属于任何显示器
        的区域），结果就是猫看不见了。
        """
        mx, my, mw, mh = winapi.monitor_at(self.root, self.x, self.y,
                                           self.w, self.h)
        self.x = max(mx, min(mx + mw - self.w, self.x))
        self.y = max(my, min(my + mh - self.h, self.y))

    def _apply_geometry(self):
        self.clamp()
        # 裸的 "-100" 会被 Tk 当成「距右边缘」，f-string 拼出 "+-100" 才是绝对坐标
        self.root.geometry(f"{self.w}x{self.h}+{int(self.x)}+{int(self.y)}")
        self.canvas.configure(width=self.w, height=self.h)

    def _apply_opacity(self):
        try:
            self.root.attributes("-alpha", float(self.conf["opacity"]))
        except tk.TclError:
            pass

    def _apply_click_through(self):
        winapi.set_click_through(self.root, bool(self.conf["click_through"]))

    def _load_face(self):
        path = self.conf.get("face_photo") or ""
        if not path:
            self.face_img = None
            return
        self.face_img = config.make_face(path, 70 * self.scale)
        if self.face_img is None:
            self.conf["face_photo"] = ""

    # ------------------------------------------------------------ 交互
    def _bind(self):
        c = self.canvas
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Button-3>", self.on_right)
        self.root.bind_all("<Control-Alt-b>", lambda e: self.toggle_hidden())
        self.root.bind_all("<Control-Alt-B>", lambda e: self.toggle_hidden())

    def on_press(self, e):
        self.drag_from = (e.x, e.y)
        self.wake()

    def on_drag(self, e):
        if not self.drag_from:
            return
        # 拖动中不夹取，否则跨屏时会被卡在当前屏边缘走不过去。
        # 松手时 on_release 再归位到落点所在的屏。
        self.x = self.root.winfo_pointerx() - self.drag_from[0]
        self.y = self.root.winfo_pointery() - self.drag_from[1]
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

    def on_release(self, e):
        self.drag_from = None
        self._apply_geometry()   # 归位到落点所在那块屏
        self._save()

    def on_right(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def wake(self):
        self.idle = 0
        self.sleeping = False

    # ------------------------------------------------------------ 菜单
    def _build_menu(self):
        m = tk.Menu(self.root, tearoff=0)

        self.v_through = tk.BooleanVar(value=self.conf["click_through"])
        self.v_mirror = tk.BooleanVar(value=self.conf["mirror"])
        self.v_auto = tk.BooleanVar(value=winapi.autostart_enabled())

        m.add_checkbutton(label="鼠标穿透", variable=self.v_through,
                          command=self.toggle_through)
        m.add_checkbutton(label="水平镜像", variable=self.v_mirror,
                          command=self.toggle_mirror)

        sub_s = tk.Menu(m, tearoff=0)
        for label, val in (("50%", 0.5), ("75%", 0.75), ("100%", 1.0),
                           ("125%", 1.25), ("150%", 1.5), ("200%", 2.0)):
            sub_s.add_command(label=label,
                              command=lambda v=val: self.set_scale(v))
        m.add_cascade(label="缩放", menu=sub_s)

        sub_o = tk.Menu(m, tearoff=0)
        for label, val in (("30%", 0.3), ("50%", 0.5), ("70%", 0.7),
                           ("85%", 0.85), ("100%", 1.0)):
            sub_o.add_command(label=label,
                              command=lambda v=val: self.set_opacity(v))
        m.add_cascade(label="不透明度", menu=sub_o)

        m.add_separator()
        m.add_command(label="选择照片当脸…", command=self.pick_photo)
        m.add_command(label="恢复猫脸", command=self.clear_photo)
        m.add_separator()
        m.add_command(label="按键统计", command=self.show_stats)
        m.add_checkbutton(label="开机自启", variable=self.v_auto,
                          command=self.toggle_autostart)
        m.add_command(label=f"隐藏 ({HOTKEY_HINT})", command=self.toggle_hidden)
        m.add_separator()
        m.add_command(label="退出", command=self.quit)
        self.menu = m

    def toggle_through(self):
        self.conf["click_through"] = self.v_through.get()
        self._apply_click_through()
        if self.conf["click_through"]:
            # 穿透后右键点不到猫，得靠托盘或热键
            self._notify("鼠标穿透已开启",
                         f"猫不再挡鼠标。要关掉请用托盘图标，或按 {HOTKEY_HINT} 隐藏。")
        self._save()

    def toggle_mirror(self):
        self.conf["mirror"] = self.v_mirror.get()
        self._save()

    def set_scale(self, v):
        self.scale = v
        self.conf["scale"] = v
        self._size()
        self._apply_geometry()
        self._load_face()
        self._save()

    def set_opacity(self, v):
        self.conf["opacity"] = v
        self._apply_opacity()
        self._save()

    def pick_photo(self):
        path = filedialog.askopenfilename(
            title="选一张照片当猫脸",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       ("所有文件", "*.*")])
        if not path:
            return
        self.conf["face_photo"] = path
        self._load_face()
        if self.face_img is None:
            messagebox.showerror("读不了这张图", "换一张试试，支持 png/jpg/bmp/gif/webp。")
        self._save()

    def clear_photo(self):
        self.conf["face_photo"] = ""
        self.face_img = None
        self._save()

    def toggle_autostart(self):
        ok = winapi.set_autostart(self.v_auto.get())
        if not ok:
            self.v_auto.set(winapi.autostart_enabled())
            messagebox.showerror("设置失败", "写注册表没成功。")

    def show_stats(self):
        messagebox.showinfo("按键统计",
                            f"本次运行敲了 {self.watch.total_keys} 下。")

    def toggle_hidden(self):
        self.hidden = not self.hidden
        if self.hidden:
            self.root.withdraw()
        else:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.after(80, self._apply_click_through)
        self.conf["hidden"] = self.hidden
        self._save()

    def _save(self):
        self.conf["x"], self.conf["y"] = int(self.x), int(self.y)
        config.save(self.conf)

    def _notify(self, title, msg):
        if self.tray is not None:
            try:
                self.tray.notify(msg, title)
                return
            except Exception:
                pass
        messagebox.showinfo(title, msg)

    # ------------------------------------------------------------ 托盘
    def _start_tray(self):
        """托盘图标。pystray 缺失时降级为无托盘，不影响主功能。"""
        self.tray = None
        try:
            import threading

            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            return

        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((8, 16, 56, 58), fill=(253, 253, 251, 255),
                  outline=(61, 50, 38, 255), width=3)
        d.polygon([(14, 22), (28, 16), (18, 4)], fill=(253, 253, 251, 255),
                  outline=(61, 50, 38, 255))
        d.polygon([(50, 22), (36, 16), (46, 4)], fill=(253, 253, 251, 255),
                  outline=(61, 50, 38, 255))
        d.ellipse((22, 30, 28, 38), fill=(43, 43, 43, 255))
        d.ellipse((36, 30, 42, 38), fill=(43, 43, 43, 255))

        def ui(fn):
            # 托盘回调在别的线程，必须切回 Tk 主线程再动界面
            return lambda *a: self.root.after(0, fn)

        menu = pystray.Menu(
            pystray.MenuItem("显示/隐藏", ui(self.toggle_hidden)),
            pystray.MenuItem(
                "鼠标穿透", ui(self._tray_toggle_through),
                checked=lambda i: bool(self.conf["click_through"])),
            pystray.MenuItem(
                "水平镜像", ui(self._tray_toggle_mirror),
                checked=lambda i: bool(self.conf["mirror"])),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("选择照片当脸", ui(self.pick_photo)),
            pystray.MenuItem("恢复猫脸", ui(self.clear_photo)),
            pystray.MenuItem("按键统计", ui(self.show_stats)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", ui(self.quit)),
        )
        self.tray = pystray.Icon("bongocat", img, "BongoCat", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _tray_toggle_through(self):
        self.v_through.set(not self.conf["click_through"])
        self.toggle_through()

    def _tray_toggle_mirror(self):
        self.v_mirror.set(not self.conf["mirror"])
        self.toggle_mirror()

    # ------------------------------------------------------------ 循环
    def tick(self):
        hit = self.watch.poll()
        self.heat += (self.watch.wpm - self.heat) * 0.18
        self.tail += 0.10 + 0.22 * self.heat

        if hit or self.watch.mouse_held:
            self.idle = 0
            self.sleeping = False
        else:
            self.idle += 1
            if self.idle > IDLE_SLEEP:
                self.sleeping = True

        # 爪子：按下时锁定「拍下」若干帧，保证真的落到台面上再抬起。
        # 少了这个保持期，下一帧目标就被改回抬起，爪子只会抖一下不落地。
        if self.watch.left_hit:
            self.left_t, self.left_hold = 0.0, STRIKE_HOLD
        if self.watch.right_hit:
            self.right_t, self.right_hold = 0.0, STRIKE_HOLD

        # 用鼠标时右爪离开键盘去握鼠标，打字优先（有键按下就收回来）
        self.on_mouse = self.watch.mouse_recent and not self.watch.right_held

        for name in ("left", "right"):
            hold = getattr(self, name + "_hold")
            held = getattr(self.watch, name + "_held")
            if name == "right" and self.on_mouse:
                setattr(self, name + "_t", 1.0)
                setattr(self, name, 1.0)
                continue
            if hold > 0:
                setattr(self, name + "_hold", hold - 1)
            elif not held:
                setattr(self, name + "_t", 1.0)

            cur = getattr(self, name)
            tgt = getattr(self, name + "_t")
            k = 0.75 if tgt < cur else 0.22   # 拍下快，抬起慢
            setattr(self, name, cur + (tgt - cur) * k)

        # 视线跟随鼠标：以窗口中心为原点，归一化到 -1~1
        ccx = self.x + self.w / 2
        ccy = self.y + self.h / 2
        self.look_x += (max(-1, min(1, (self.watch.mx - ccx) / 480.0))
                        - self.look_x) * 0.16
        self.look_y += (max(-1, min(1, (self.watch.my - ccy) / 360.0))
                        - self.look_y) * 0.16

        self.blink_next -= 1
        if self.blink_next <= 0:
            self.blink = 5
            self.blink_next = random.randint(80, 200)
        if self.blink > 0:
            self.blink -= 1

        if not self.hidden:
            self.render()
        self.root.after(FPS_MS, self.tick)

    def render(self):
        c = self.canvas
        c.delete("all")
        draw_cat(c, self.w / 2, self.h * 0.38, self.scale,
                 left=self.left, right=self.right,
                 look_x=self.look_x, look_y=self.look_y,
                 eye=0.0 if self.blink > 0 else 1.0,
                 mirror=bool(self.conf["mirror"]),
                 sleeping=self.sleeping, heat=self.heat,
                 tail=self.tail, face_img=self.face_img,
                 down=self.watch.down,
                 on_mouse=self.on_mouse,
                 mouse_click=self.watch.mouse_held,
                 mouse_nx=self.watch.mouse_nx,
                 mouse_ny=self.watch.mouse_ny)

    def quit(self):
        self._save()
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()
