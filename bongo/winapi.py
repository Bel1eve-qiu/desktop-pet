"""Windows 平台相关：全局输入轮询、窗口穿透、开机自启。

全部用 ctypes 直接调用系统 API，不需要第三方库，也不需要管理员权限。
GetAsyncKeyState 是轮询式的，不安装全局钩子，所以不会被安全软件拦。
"""

import ctypes
import ctypes.wintypes as wt
import os
import sys

user32 = ctypes.windll.user32
IS_WIN = sys.platform == "win32"

# 扩展窗口样式
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000       # 分层窗口，支持整体透明度
WS_EX_TRANSPARENT = 0x00000020   # 鼠标穿透：点击直接落到下层窗口
WS_EX_NOACTIVATE = 0x08000000    # 点了也不抢焦点

# 虚拟键码
VK_LBUTTON, VK_RBUTTON, VK_MBUTTON = 0x01, 0x02, 0x04

# 虚拟桌面度量
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "BongoCatPet"


def set_dpi_aware():
    """让窗口坐标按物理像素走，多屏不同缩放时位置才准。"""
    if not IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


_ENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                               ctypes.POINTER(wt.RECT), ctypes.c_double)


def monitors(root):
    """每块显示器的工作区 [(x, y, w, h, is_primary), ...]。

    虚拟桌面只是所有屏的外包矩形，屏幕摆放不规则时中间会有空洞
    （比如两块屏高度不同，矮的那块下方就是无效区域）。
    窗口摆到空洞里会完全看不见，所以位置计算必须按单块屏来。
    工作区已排除任务栏。
    """
    out = []
    if IS_WIN:
        try:
            def cb(hmon, hdc, lprc, data):
                mi = _MONITORINFO()
                mi.cbSize = ctypes.sizeof(_MONITORINFO)
                if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    r = mi.rcWork
                    out.append((r.left, r.top, r.right - r.left,
                                r.bottom - r.top, bool(mi.dwFlags & 1)))
                return 1

            user32.EnumDisplayMonitors(0, 0, _ENUMPROC(cb), 0)
        except Exception:
            out = []
    if not out:
        out = [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight(),
                True)]
    return out


def primary_monitor(root):
    mons = monitors(root)
    for m in mons:
        if m[4]:
            return m
    return mons[0]


def monitor_at(root, x, y, w, h):
    """找窗口重叠面积最大的那块屏；没有重叠就返回主屏。"""
    best, best_area = None, 0
    for mx, my, mw, mh, _ in monitors(root):
        ox = max(0, min(x + w, mx + mw) - max(x, mx))
        oy = max(0, min(y + h, my + mh) - max(y, my))
        if ox * oy > best_area:
            best, best_area = (mx, my, mw, mh), ox * oy
    if best is None:
        m = primary_monitor(root)
        return m[0], m[1], m[2], m[3]
    return best


def virtual_desktop(root):
    """所有显示器拼成的整块区域 (x, y, w, h)。

    winfo_screenwidth() 只认主屏；副屏在左边或上边时坐标为负，
    会被夹回主屏。这里问系统要真正的虚拟桌面边界。
    """
    if IS_WIN:
        try:
            g = user32.GetSystemMetrics
            x, y = g(SM_XVIRTUALSCREEN), g(SM_YVIRTUALSCREEN)
            w, h = g(SM_CXVIRTUALSCREEN), g(SM_CYVIRTUALSCREEN)
            if w > 0 and h > 0:
                return x, y, w, h
        except Exception:
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def hwnd_of(root):
    """取 Tk 窗口的原生句柄。"""
    root.update_idletasks()
    return int(root.frame(), 16)


def set_click_through(root, enabled):
    """开关鼠标穿透。开启后整个窗口不再接收鼠标事件。"""
    if not IS_WIN:
        return False
    try:
        h = hwnd_of(root)
        style = user32.GetWindowLongW(h, GWL_EXSTYLE) | WS_EX_LAYERED
        if enabled:
            style |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
        else:
            style &= ~WS_EX_TRANSPARENT & ~WS_EX_NOACTIVATE
        user32.SetWindowLongW(h, GWL_EXSTYLE, style)
        return True
    except Exception:
        return False


def cursor_pos():
    """全局鼠标坐标，跨副屏有效。"""
    if not IS_WIN:
        return 0, 0
    p = wt.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def screen_size():
    """主屏分辨率，用来把光标坐标归一化。取不到就给个安全默认值。"""
    if not IS_WIN:
        return 1920, 1080
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return (w or 1920), (h or 1080)


def key_down(vk):
    """某个虚拟键当前是否按下。取高位，忽略「按过」的低位。"""
    if not IS_WIN:
        return False
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


# ----------------------------------------------------------- 开机自启
def _launch_cmd():
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                          "bongocat.py"))
    return f'"{exe}" "{script}"'


def autostart_enabled():
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
        return True
    except OSError:
        return False


def set_autostart(enabled):
    """写 HKCU 的 Run 键。只动当前用户，不需要管理员。"""
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _launch_cmd())
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except OSError:
                    pass
        return True
    except OSError:
        return False
