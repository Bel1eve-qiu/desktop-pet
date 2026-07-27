"""桌宠角色绘制。

角色完全由 Canvas 图元（椭圆 / 圆弧 / 多边形）画出来，
所以整个项目不需要任何外部图片素材，也没有第三方依赖。
"""

import math

# 配色
BODY = "#8ecae6"
BODY_DARK = "#5fa8d3"
BELLY = "#eaf7fc"
DARK = "#22333b"
BLUSH = "#ff9aa2"
BUBBLE = "#ffffff"


def draw_pet(canvas, cx, baseline, scale=1.0, squash=0.0, eye=1.0,
             mouth="smile", facing=1, tail_phase=0.0, sleeping=False):
    """在 canvas 上画一只桌宠。

    cx / baseline: 角色的水平中心与脚底所在的 y 坐标
    scale:    整体缩放
    squash:   挤压量，>0 压扁（落地），<0 拉长（起跳）
    eye:      眼睛开合度 0~1，用来做眨眼
    mouth:    smile / open / flat
    facing:   1 朝右，-1 朝左
    tail_phase: 尾巴摆动相位
    sleeping: 睡眠状态（闭眼 + Zzz）
    """
    w = 96 * scale * (1 + 0.13 * squash)
    h = 88 * scale * (1 - 0.18 * squash)
    cy = baseline - h / 2

    # 影子
    canvas.create_oval(cx - w * 0.42, baseline - 7 * scale,
                       cx + w * 0.42, baseline + 5 * scale,
                       fill="#b9c6cc", outline="")

    # 尾巴：跟着相位左右摆
    swing = math.sin(tail_phase) * 16 * scale
    tx = cx - facing * w * 0.42
    canvas.create_line(tx, cy + h * 0.18,
                       tx - facing * 22 * scale, cy + h * 0.05 - swing * 0.3,
                       tx - facing * 26 * scale, cy - h * 0.28 - swing,
                       smooth=True, width=int(7 * scale) or 1,
                       capstyle="round", fill=BODY_DARK)

    # 耳朵
    for side in (-1, 1):
        ex = cx + side * w * 0.30
        canvas.create_polygon(ex - 15 * scale, cy - h * 0.36,
                              ex + 13 * scale, cy - h * 0.30,
                              ex + side * 3 * scale, cy - h * 0.72,
                              fill=BODY_DARK, outline="")

    # 身体 + 肚皮
    canvas.create_oval(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2,
                       fill=BODY, outline=BODY_DARK, width=max(1, int(2 * scale)))
    canvas.create_oval(cx - w * 0.27, cy + h * 0.02,
                       cx + w * 0.27, cy + h * 0.44,
                       fill=BELLY, outline="")

    # 脚
    for side in (-1, 1):
        fx = cx + side * w * 0.22
        canvas.create_oval(fx - 13 * scale, baseline - 13 * scale,
                           fx + 13 * scale, baseline + 2 * scale,
                           fill=BODY_DARK, outline="")

    # 眼睛
    ey = cy - h * 0.10
    for side in (-1, 1):
        ex = cx + side * w * 0.20 + facing * 3 * scale
        if sleeping or eye < 0.12:
            canvas.create_line(ex - 9 * scale, ey, ex + 9 * scale, ey,
                               width=max(1, int(3 * scale)), fill=DARK,
                               capstyle="round")
        else:
            rh = 11 * scale * eye
            canvas.create_oval(ex - 8 * scale, ey - rh, ex + 8 * scale, ey + rh,
                               fill=DARK, outline="")
            canvas.create_oval(ex - 5 * scale, ey - rh * 0.75,
                               ex - 1 * scale, ey - rh * 0.2,
                               fill="#ffffff", outline="")

    # 腮红
    for side in (-1, 1):
        bx = cx + side * w * 0.36
        canvas.create_oval(bx - 8 * scale, ey + 12 * scale,
                           bx + 8 * scale, ey + 22 * scale,
                           fill=BLUSH, outline="")

    # 嘴
    my = cy + h * 0.14
    if mouth == "open":
        canvas.create_oval(cx - 8 * scale, my - 5 * scale,
                           cx + 8 * scale, my + 10 * scale,
                           fill="#e26d5c", outline=DARK)
    elif mouth == "flat":
        canvas.create_line(cx - 7 * scale, my, cx + 7 * scale, my,
                           width=max(1, int(2 * scale)), fill=DARK,
                           capstyle="round")
    else:
        canvas.create_arc(cx - 12 * scale, my - 12 * scale,
                          cx + 12 * scale, my + 8 * scale,
                          start=200, extent=140, style="arc",
                          width=max(1, int(2 * scale)), outline=DARK)

    if sleeping:
        for i, s in enumerate((13, 10, 8)):
            canvas.create_text(cx + w * 0.45 + i * 13 * scale,
                               cy - h * 0.55 - i * 15 * scale,
                               text="z", font=("Segoe UI", int(s * scale), "bold"),
                               fill=DARK)


def draw_bubble(canvas, cx, bottom, text, scale=1.0):
    """在角色头顶画一个气泡对话框。"""
    font = ("Microsoft YaHei", max(8, int(10 * scale)))
    tid = canvas.create_text(cx, bottom - 26 * scale, text=text, font=font,
                             fill=DARK, justify="center", width=180 * scale)
    x0, y0, x1, y1 = canvas.bbox(tid)
    pad = 9 * scale
    rect = canvas.create_polygon(
        x0 - pad, y0 - pad, x1 + pad, y0 - pad,
        x1 + pad, y1 + pad, cx + 8 * scale, y1 + pad,
        cx, y1 + pad + 10 * scale, cx - 6 * scale, y1 + pad,
        x0 - pad, y1 + pad,
        fill=BUBBLE, outline=BODY_DARK, width=max(1, int(2 * scale)),
        smooth=False)
    canvas.tag_raise(tid, rect)
    return tid
