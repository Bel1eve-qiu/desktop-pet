"""猫咪绘制：身体 / 头 / 双爪分层，各部分独立运动。

爪子、头部朝向、眼球都由外部传入的参数驱动，
所以输入层只需要给出 0~1 的连续量，这里负责画。
"""

import math

from .inputs import KEY_ROWS

OUTLINE = "#3d3226"
FUR = "#fdfdfb"
FUR_SHADE = "#e6e3dc"
EAR_IN = "#ffb3c6"
PAD = "#ffb3c6"
DARK = "#2b2b2b"

# 键盘配色
KB_BODY = "#4a5560"
KB_SIDE = "#333c45"
KEY_CAP = "#f2f4f7"
KEY_SIDE = "#c3c9d1"
KEY_EDGE = "#8d95a0"
KEY_TXT = "#5b636e"
KEY_LIT = "#ffd166"   # 按下时亮起

# 鼠标垫
PAD_TOP = "#d9dde3"
PAD_SIDE = "#b3b9c2"

TILT_DEG = 9.0        # 键盘倾斜角度，改这个数就能调斜度

# 肩膀位置（相对身体中心，未缩放）。身体半宽 70、下缘 +50，
# 所以 52 落在身体外侧靠肩的位置，-6 在肚子上方，胳膊才像从肩膀长出来。
SHOULDER_X = 52.0
SHOULDER_Y = -6.0


def _rr_pts(x0, y0, x1, y1, r):
    """圆角矩形的顶点序列（扁平 x,y 列表）。"""
    pts = []
    for cx, cy, s, e in ((x1 - r, y0 + r, -90, 0), (x1 - r, y1 - r, 0, 90),
                         (x0 + r, y1 - r, 90, 180), (x0 + r, y0 + r, 180, 270)):
        for a in range(s, e + 1, 12):
            t = math.radians(a)
            pts += [cx + r * math.cos(t), cy + r * math.sin(t)]
    return pts


def _rr(c, x0, y0, x1, y1, r, **kw):
    """圆角矩形。"""
    return c.create_polygon(_rr_pts(x0, y0, x1, y1, r), smooth=True, **kw)


def _rr_t(c, x0, y0, x1, y1, r, tf, **kw):
    """圆角矩形，顶点先过一遍 tf 变换（用来把键盘整体转个角度）。"""
    p = _rr_pts(x0, y0, x1, y1, r)
    out = []
    for i in range(0, len(p), 2):
        out += list(tf(p[i], p[i + 1]))
    return c.create_polygon(out, smooth=True, **kw)


# 垫子和鼠标的半宽/半高（未缩放）。鼠标的外接框面积约为垫子的 1/4：
# (2*13.5 * 2*19) / (2*40 * 2*26) ≈ 0.25
PAD_HW, PAD_HH = 40.0, 26.0
MOUSE_HW, MOUSE_HH = 13.5, 19.0


def _desk_metrics(cy, s):
    """台面尺寸：键盘半宽、上下沿。垫子要在键盘之前画，所以先单独算出来。"""
    kw, kh, gap = 20 * s, 13 * s, 2.4 * s
    rowh = kh + gap
    n = len(KEY_ROWS)
    top = cy + 26 * s + rowh
    half_w = (10 * (kw + gap) + 2.2 * kw) / 2
    return {"kw": kw, "kh": kh, "gap": gap, "rowh": rowh, "n": n,
            "top": top, "half_w": half_w,
            "kb_top": top - rowh - 6 * s,
            "kb_bot": top + n * rowh + 8 * s}


def _tilt(cx, cy, s, m):
    """整块台面（键盘 + 垫子 + 鼠标）共用的倾斜变换，保证走向一致。"""
    d = _desk_metrics(cy, s)
    ang = math.radians(TILT_DEG) * -m
    ca, sa = math.cos(ang), math.sin(ang)
    pcx, pcy = cx, (d["kb_top"] + d["kb_bot"]) / 2

    def tf(x, y):
        dx, dy = x - pcx, y - pcy
        return pcx + dx * ca - dy * sa, pcy + dx * sa + dy * ca

    return tf, ang


def _oval_t(canvas, x0, y0, x1, y1, tf, **kw):
    """跟着台面倾斜的椭圆：用多边形近似，create_oval 无法旋转。"""
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    pts = []
    for i in range(36):
        a = i * math.pi / 18
        pts.extend(tf(mx + rx * math.cos(a), my + ry * math.sin(a)))
    return canvas.create_polygon(*pts, smooth=True, **kw)


def _draw_keyboard(canvas, cx, cy, s, down, m):
    """画一块**朝向猫**的键盘，按下的键会亮起并下沉。

    键盘是转过去给猫用的，所以我们看到的是它的后沿：
    空格排在最靠我们这侧（最下），ZXCVM 排其次，QWERTY 排在最远（最上）。
    字母顺序也随之左右翻转 —— 从猫那边看才是正的 QWERTY。
    返回爪子该落到的台面 y 坐标。
    """
    d = _desk_metrics(cy, s)     # 尺寸跟垫子定位共用同一套，避免两边算错叠上去
    kw, kh, gap, rowh = d["kw"], d["kh"], d["gap"], d["rowh"]
    n, top, body_w = d["n"], d["top"], d["half_w"]
    kb_top, kb_bot = d["kb_top"], d["kb_bot"]
    # 键盘斜放：绕键盘中心转 TILT 度。参考图里键盘是朝猫的右手边斜下去的，
    # 所以镜像时角度也要跟着反，否则会往反方向歪。垫子和鼠标共用这个变换。
    tf, ang = _tilt(cx, cy, s, m)

    # 键盘本体：朝我们这侧是后沿，画出后沿的厚度
    b0, b1 = cx - body_w, cx + body_w
    _rr_t(canvas, b0, kb_top + 5 * s, b1, kb_bot + 8 * s, 6 * s, tf,
          fill=KB_SIDE, outline=OUTLINE, width=max(1, int(2 * s)))
    _rr_t(canvas, b0, kb_top, b1, kb_bot, 6 * s, tf,
          fill=KB_BODY, outline=OUTLINE, width=max(1, int(2 * s)))

    hits = {}

    def cap(x0, y0, x1, y1, lit, label=None):
        sink = 2 * s if lit else 0
        face = KEY_LIT if lit else KEY_CAP
        # 键盘朝猫，我们看到的是键帽靠自己这侧的侧壁（在顶面下方）
        _rr_t(canvas, x0, y0 + sink, x1, y1 + sink + 2.5 * s, 2.6 * s, tf,
              fill=KEY_SIDE, outline="")
        _rr_t(canvas, x0, y0 + sink, x1, y1 + sink, 2.6 * s, tf,
              fill=face, outline=KEY_EDGE, width=1)
        mid = tf((x0 + x1) / 2, (y0 + y1) / 2 + sink)
        if label and s >= 0.9:
            # 字母印给猫看：整体转 180° 朝向猫那侧，再叠上键盘的倾斜角。
            # 之前只做了左右翻转没转 180°，所以字还是正对着我们。
            canvas.create_text(*mid, text=label, fill=KEY_TXT,
                               angle=(180 - math.degrees(ang)) % 360,
                               font=("Segoe UI", max(5, int(6.5 * s))))
        return mid

    # 行序反转：QWERTY 排离我们最远，画在最上面
    for r, (chars, off) in enumerate(reversed(KEY_ROWS)):
        ry = top + r * rowh
        rw = len(chars) * (kw + gap) - gap
        # 字母左右翻转，猫那侧看才是正序
        seq = chars[::-1]
        sx = cx - rw / 2 - (off - 0.55) * kw * 0.5
        for i, ch in enumerate(seq):
            x0 = sx + i * (kw + gap)
            hits[ch] = cap(x0, ry, x0 + kw, ry + kh, ord(ch) in down, ch)

    # 空格：键盘是反过来的，空格排最靠猫这一侧（我们看到的最上面）
    sy = top - rowh
    sw2 = 5.4 * kw
    cap(cx - sw2 / 2, sy, cx + sw2 / 2, sy + kh, 0x20 in down)

    # 爪子落点：取左右半区中间那一排的键面中心，跟着倾斜一起走
    rest = top + (n - 1.5) * rowh
    return {
        "left": tf(cx + 46 * s, rest),
        "right": tf(cx - 46 * s, rest),
        "far": tf(cx, kb_bot),
        "hits": hits,
    }


def _draw_pad(canvas, mx, my, s, tf, w=PAD_HW):
    """鼠标垫：参考图里鼠标下面那块浅灰板子，走向跟键盘一致。"""
    w, h = w * s, PAD_HH * s
    _rr_t(canvas, mx - w, my - h, mx + w, my + h, 7 * s, tf,
          fill=PAD_SIDE, outline=OUTLINE, width=max(1, int(2 * s)))
    _rr_t(canvas, mx - w, my - h, mx + w, my + h - 5 * s, 7 * s, tf,
          fill=PAD_TOP, outline="")


def _draw_mouse(canvas, mx, my, s, clicking, tf):
    """画一只鼠标（在猫的右手边，屏幕左侧），跟着台面一起倾斜。"""
    w, h = MOUSE_HW * s, MOUSE_HH * s
    _oval_t(canvas, mx - w, my - h + 3 * s, mx + w, my + h + 4 * s, tf,
            fill=KB_SIDE, outline="")
    _oval_t(canvas, mx - w, my - h, mx + w, my + h, tf,
            fill="#e9ecf1" if not clicking else "#cfd6e0",
            outline=OUTLINE, width=max(1, int(2 * s)))
    # 分键缝 + 滚轮朝远离猫的一侧（屏幕下方）：猫的手掌盖在靠自己那头，
    # 鼠标前端冲着外面，才是猫在用而不是我们在用。
    canvas.create_line(*tf(mx, my + h - 2 * s), *tf(mx, my + 1 * s),
                       fill=KEY_EDGE, width=max(1, int(1.4 * s)))
    _oval_t(canvas, mx - 2.2 * s, my + h * 0.2, mx + 2.2 * s, my + h * 0.62, tf,
            fill=KEY_TXT, outline="")


def draw_cat(canvas, cx, cy, s=1.0, left=0.0, right=0.0, look_x=0.0,
             look_y=0.0, eye=1.0, mirror=False, sleeping=False,
             heat=0.0, tail=0.0, face_img=None, down=None,
             on_mouse=False, mouse_click=False,
             mouse_nx=0.0, mouse_ny=0.0):
    """画猫。

    cx / cy:  身体中心
    s:        缩放
    left/right: 左右爪抬起量 0(拍下) ~ 1(抬起)
    look_x/look_y: 视线偏移 -1~1，由鼠标位置驱动
    eye:      眼睛开合 0~1
    mirror:   水平镜像（左手党）
    heat:     打字热度 0~1，影响耳朵抖动和尾巴速度
    face_img: PIL 生成的圆形头像 PhotoImage，有则贴在脸上
    """
    # 猫是面朝用户坐的，所以「它的左手」画在屏幕右侧（跟照镜子一样）。
    # 之前直接把左手画在屏幕左侧，从猫的视角看就是左右颠倒的。
    m = 1 if mirror else -1
    look_x *= -m
    # 猫要坐在整套台面（键盘左沿 ~ 垫子外沿）的正中间。
    # 关键：台面和猫身不能共用一个中心，否则一起平移，相对位置永远不变。
    # kcx = 台面中心，cx = 猫身中心（正好落在台面跨度的中点）。
    _d = _desk_metrics(cy, s)
    _off = PAD_HW * s + 3 * s      # 垫子只长在一侧造成的重心偏移
    kcx = cx - m * _off

    # ---- 鼠标垫（最底层）----
    # 层序按参考图：垫子 → 猫身 → 键盘 → 爪子。键盘压在身体和垫子之上，
    # 所以两者都不会盖住键帽。垫子还要横向躲开键盘，避免直接压上去。
    dm = _desk_metrics(cy, s)
    pad_w = PAD_HW * s
    # 垫子内缘留 6px 间隙贴在键盘外侧
    pad_x = kcx + m * (dm["half_w"] + pad_w + 6 * s)
    # 垂直上往猫那侧靠：y 越小越靠近猫
    pad_y = dm["kb_bot"] - 34 * s
    # 垫子/鼠标跟键盘共用同一个倾斜变换，走向才会一致
    tf, _ang = _tilt(kcx, cy, s, m)
    # 传未缩放的宽度：_draw_pad 内部会乘 s，这里再乘一次会变成 w*s²
    _draw_pad(canvas, pad_x, pad_y, s, tf, PAD_HW)

    # 真实光标位置映射到垫子上：鼠标在垫内可活动的范围 = 垫半径 - 鼠标半径。
    # mouse_nx 是屏幕坐标归一化的，镜像时跟着翻，方向才不会反。
    rx = (PAD_HW - MOUSE_HW - 3) * s
    ry = (PAD_HH - MOUSE_HH - 3) * s
    mouse_x = pad_x + m * mouse_nx * rx
    mouse_y = pad_y + mouse_ny * ry

    # ---- 尾巴 ----
    sw = math.sin(tail) * (14 + 16 * heat) * s
    tx = cx - m * 74 * s
    canvas.create_line(tx, cy + 26 * s,
                       tx - m * 26 * s, cy + 10 * s - sw * 0.3,
                       tx - m * 30 * s, cy - 24 * s - sw,
                       smooth=True, width=int(9 * s) or 1, capstyle="round",
                       fill=FUR_SHADE)

    # ---- 身体 ----
    bw, bh = 70 * s, 50 * s
    canvas.create_oval(cx - bw, cy - bh * 0.55, cx + bw, cy + bh,
                       fill=FUR, outline=OUTLINE, width=max(1, int(2 * s)))

    # ---- 键盘 + 鼠标（画在身体之后，压住猫的下半身，像放在猫前面）----
    kb = _draw_keyboard(canvas, kcx, cy, s, down or (), m)
    _draw_mouse(canvas, mouse_x, mouse_y, s, mouse_click and on_mouse, tf)

    # ---- 双爪 ----
    # 抬起时向上并向内收，拍下时贴在台面上。
    # 猫的右爪（屏幕左侧，side=1）在用鼠标时会移到鼠标上，只做点击的小幅起落。
    for side, amt in ((-1, left), (1, right)):
        sd = side * m
        grabbing = on_mouse and side == 1
        if grabbing:
            # 鼠标跟着台面斜了，爪子落点也要经过同一个变换才压得准
            px, py = tf(mouse_x,
                        mouse_y - 12 * s - (3 * s if not mouse_click else 0))
        else:
            # 落点来自倾斜后的键面，抬起时垂直离开台面
            bx, by = kb["left" if side == -1 else "right"]
            px, py = bx, by - 30 * s * amt
        # 手臂：根部落在肩膀（身体上缘偏外侧），不是肚皮正中。
        # 之前根部在 (±30, +20)，水平只到身体半宽的 4 成、垂直又在肚子下缘，
        # 看着就是两条胳膊从肚皮里钻出来。
        shx = cx + sd * SHOULDER_X * s
        shy = cy + SHOULDER_Y * s
        canvas.create_line(shx, shy, px, py,
                           width=int(13 * s) or 1, capstyle="round",
                           fill=FUR, joinstyle="round")
        # 肩关节：盖住手臂和身体的接缝，让连接处圆润过渡
        canvas.create_oval(shx - 9 * s, shy - 9 * s, shx + 9 * s, shy + 9 * s,
                           fill=FUR, outline="")
        # 爪垫
        canvas.create_oval(px - 15 * s, py - 11 * s, px + 15 * s, py + 11 * s,
                           fill=FUR, outline=OUTLINE, width=max(1, int(2 * s)))
        canvas.create_oval(px - 8 * s, py - 4 * s, px + 8 * s, py + 7 * s,
                           fill=PAD, outline="")
        # 拍下瞬间的冲击线（握鼠标那只不画）
        if amt < 0.15 and not grabbing:
            for k in (-1, 1):
                canvas.create_line(px + k * 19 * s, py - 3 * s,
                                   px + k * 27 * s, py - 9 * s,
                                   width=max(1, int(2 * s)), fill="#ffd166",
                                   capstyle="round")

    # ---- 头 ----
    hy = cy - 44 * s
    hr = 42 * s
    # 耳朵：打字越快抖得越明显
    jit = math.sin(tail * 3.1) * 3 * s * heat
    for side in (-1, 1):
        sd = side * m
        ex = cx + sd * 26 * s
        canvas.create_polygon(ex - 16 * s, hy - 18 * s,
                              ex + 15 * s, hy - 22 * s,
                              ex + sd * 4 * s, hy - 50 * s + jit * side,
                              fill=FUR, outline=OUTLINE,
                              width=max(1, int(2 * s)))
        canvas.create_polygon(ex - 8 * s, hy - 21 * s,
                              ex + 7 * s, hy - 23 * s,
                              ex + sd * 2 * s, hy - 40 * s + jit * side,
                              fill=EAR_IN, outline="")

    canvas.create_oval(cx - hr, hy - hr * 0.86, cx + hr, hy + hr * 0.86,
                       fill=FUR, outline=OUTLINE, width=max(1, int(2 * s)))

    if face_img is not None:
        # 照片模式：圆形头像贴在脸上，五官不再绘制
        canvas.create_image(cx + look_x * 5 * s, hy + look_y * 4 * s,
                            image=face_img)
        return

    # ---- 五官 ----
    ey = hy - 3 * s
    for side in (-1, 1):
        ex = cx + side * 15 * s + look_x * 4 * s
        if sleeping or eye < 0.12:
            canvas.create_line(ex - 8 * s, ey, ex + 8 * s, ey,
                               width=max(1, int(3 * s)), fill=DARK,
                               capstyle="round")
        else:
            rh = 10 * s * eye
            canvas.create_oval(ex - 7 * s, ey - rh, ex + 7 * s, ey + rh,
                               fill=DARK, outline="")
            gx = ex + look_x * 3 * s
            gy = ey + look_y * 3 * s
            canvas.create_oval(gx - 4 * s, gy - rh * 0.7,
                               gx - 0.5 * s, gy - rh * 0.15,
                               fill="#ffffff", outline="")

    # 鼻子 + 嘴
    ny = ey + 14 * s
    nx = cx + look_x * 4 * s
    canvas.create_polygon(nx - 4 * s, ny - 2 * s, nx + 4 * s, ny - 2 * s,
                          nx, ny + 3 * s, fill=EAR_IN, outline="")
    open_mouth = heat > 0.45 or sleeping
    if open_mouth:
        canvas.create_oval(nx - 6 * s, ny + 3 * s, nx + 6 * s, ny + 13 * s,
                           fill="#e26d5c", outline=OUTLINE)
    else:
        for k in (-1, 1):
            canvas.create_arc(nx + k * 7 * s - 7 * s, ny + 2 * s,
                              nx + k * 7 * s + 7 * s, ny + 12 * s,
                              start=180 if k < 0 else 0, extent=180,
                              style="arc", width=max(1, int(1.6 * s)),
                              outline=DARK)

    # 胡须
    for side in (-1, 1):
        sd = side * m
        for dyy in (-4, 1, 6):
            canvas.create_line(cx + sd * 24 * s, ny + dyy * s,
                               cx + sd * 46 * s, ny + dyy * s - sd * 2 * s,
                               width=max(1, int(1.3 * s)), fill="#9a9287",
                               capstyle="round")

    if sleeping:
        for i, sz in enumerate((14, 11, 8)):
            canvas.create_text(cx + 46 * s + i * 14 * s,
                               hy - 46 * s - i * 16 * s, text="z",
                               font=("Segoe UI", int(sz * s), "bold"),
                               fill=DARK)
