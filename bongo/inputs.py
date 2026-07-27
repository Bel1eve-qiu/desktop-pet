"""全局输入采集：把键盘分成左右手两区，统计打字节奏。

标准 QWERTY 硬编码分区：以键盘中线为界，
左手区 = 1-5 / QWERT / ASDFG / ZXCVB + Tab Caps Shift Ctrl Alt 空格左半
右手区 = 6-0 / YUIOP / HJKL / NM,./ + 方向键 小键盘 回车 退格
"""

from .winapi import (key_down, cursor_pos, screen_size,
                     VK_LBUTTON, VK_RBUTTON, VK_MBUTTON)


def _vks(chars):
    return [ord(c) for c in chars]


# 左手区
LEFT_KEYS = (
    _vks("12345") + _vks("QWERT") + _vks("ASDFG") + _vks("ZXCVB") +
    [0x09,        # Tab
     0x14,        # Caps Lock
     0xA0,        # 左 Shift
     0xA2,        # 左 Ctrl
     0xA4,        # 左 Alt
     0x1B,        # Esc
     0x5B]        # 左 Win
)

# 右手区
RIGHT_KEYS = (
    _vks("67890") + _vks("YUIOP") + _vks("HJKL") + _vks("NM") +
    [0xBC, 0xBE, 0xBF,          # , . /
     0xBA, 0xDE,                # ; '
     0xDB, 0xDD, 0xDC,          # [ ] \
     0xBD, 0xBB,                # - =
     0x0D,                      # 回车
     0x08,                      # 退格
     0xA1,                      # 右 Shift
     0xA3,                      # 右 Ctrl
     0x25, 0x26, 0x27, 0x28,    # 方向键
     0x2D, 0x2E, 0x24, 0x23,    # Ins Del Home End
     0x21, 0x22]                # PgUp PgDn
    + list(range(0x60, 0x70))   # 小键盘 0-9 及运算符
)

# 空格算中间键，两只爪子随机轮流拍
SPACE = 0x20

# 画出来的键盘布局：(键帽字母, 相对行首的偏移单位)
# 只画三排字母 + 空格，够认出是键盘，又不会挤成一团。
KEY_ROWS = (
    ("QWERTYUIOP", 0.0),
    ("ASDFGHJKL", 0.5),
    ("ZXCVBNM", 1.1),
)


class InputWatcher:
    """轮询全局输入。每帧调用 poll()，不装钩子。"""

    def __init__(self):
        self.left_hit = False        # 本帧左手区是否有新按下
        self.right_hit = False
        self.left_held = False       # 左手区是否有键处于按下状态
        self.right_held = False
        self.mouse_l = False
        self.mouse_r = False
        self.mouse_m = False
        self.mx, self.my = cursor_pos()
        self.mouse_nx = 0.0        # 光标横向位置 -1..1（映射到垫子上）
        self.mouse_ny = 0.0        # 光标纵向位置 -1..1
        self.total_keys = 0          # 累计按键数
        self.wpm = 0.0               # 打字热度 0~1
        self.down = set()            # 当前按下的 VK，供键盘高亮用
        self.mouse_recent = False    # 最近是否在用鼠标（移动或点击）
        self.mouse_click = False     # 本帧是否有新的鼠标按下
        self._last_mouse = 0         # 最后一次鼠标活动的帧号
        self._prev = set()
        self._recent = []            # 最近按键的帧号，用来算热度
        self._frame = 0
        self._space_side = 0

    def poll(self):
        self._frame += 1
        now = set()

        for vk in LEFT_KEYS:
            if key_down(vk):
                now.add(vk)
        for vk in RIGHT_KEYS:
            if key_down(vk):
                now.add(vk)
        space = key_down(SPACE)
        if space:
            now.add(SPACE)

        new = now - self._prev
        self.total_keys += len(new)

        self.left_hit = any(vk in LEFT_KEYS for vk in new)
        self.right_hit = any(vk in RIGHT_KEYS for vk in new)
        if SPACE in new:
            # 空格左右爪交替
            self._space_side ^= 1
            if self._space_side:
                self.left_hit = True
            else:
                self.right_hit = True

        self.left_held = any(vk in LEFT_KEYS for vk in now) or (
            space and self._space_side == 1)
        self.right_held = any(vk in RIGHT_KEYS for vk in now) or (
            space and self._space_side == 0)

        # 鼠标按键：不再算成拍键盘，而是驱动握鼠标那只爪子点击
        ml, mr = key_down(VK_LBUTTON), key_down(VK_RBUTTON)
        mm = key_down(VK_MBUTTON)
        self.mouse_click = (ml and not self.mouse_l) or (mr and not self.mouse_r)
        self.mouse_l, self.mouse_r, self.mouse_m = ml, mr, mm

        px, py = self.mx, self.my
        self.mx, self.my = cursor_pos()
        moved = abs(self.mx - px) + abs(self.my - py) > 3
        if moved or self.mouse_click or self.mouse_held:
            self._last_mouse = self._frame

        # 真实光标位置映射到 -1..1，驱动垫子上鼠标的位置。
        # 平滑一下，否则光标一跳爪子就闪。
        sw, sh = screen_size()
        tx = self.mx / max(1, sw) * 2.0 - 1.0
        ty = self.my / max(1, sh) * 2.0 - 1.0
        k = 0.25
        self.mouse_nx += (max(-1.0, min(1.0, tx)) - self.mouse_nx) * k
        self.mouse_ny += (max(-1.0, min(1.0, ty)) - self.mouse_ny) * k
        # 鼠标停下后 1.5 秒内仍算「在用鼠标」，避免爪子来回抽搐
        self.mouse_recent = (self._frame - self._last_mouse) < 45

        # 打字热度：最近 60 帧（约 2 秒）内的按键次数归一化
        if new:
            self._recent.extend([self._frame] * len(new))
        cutoff = self._frame - 60
        self._recent = [f for f in self._recent if f > cutoff]
        self.wpm = min(1.0, len(self._recent) / 14.0)

        self.down = now
        self._prev = now
        return bool(new)

    @property
    def any_hit(self):
        return self.left_hit or self.right_hit

    @property
    def mouse_held(self):
        return self.mouse_l or self.mouse_r or self.mouse_m
