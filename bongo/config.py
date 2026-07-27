"""配置持久化 + 照片头像处理。"""

import json
import os

from PIL import Image, ImageDraw, ImageTk

HERE = os.path.dirname(os.path.abspath(__file__))
CONF_PATH = os.path.join(HERE, "..", "settings.json")

DEFAULTS = {
    "x": None,            # None = 首次启动自动放右下角
    "y": None,
    "scale": 1.0,         # 0.5 ~ 2.0
    "opacity": 1.0,       # 0.3 ~ 1.0
    "click_through": False,
    "mirror": False,
    "face_photo": "",     # 照片路径，空则画卡通猫脸
    "hidden": False,
}


def load():
    conf = dict(DEFAULTS)
    try:
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            # 只接受已知键，避免旧版本残留字段污染
            conf.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return conf


def save(conf):
    try:
        with open(CONF_PATH, "w", encoding="utf-8") as f:
            json.dump({k: conf.get(k) for k in DEFAULTS}, f,
                      ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def make_face(path, diameter):
    """把照片裁成圆形头像，返回 ImageTk.PhotoImage。

    失败返回 None，调用方回退到卡通猫脸。
    """
    d = max(16, int(diameter))
    try:
        img = Image.open(path).convert("RGBA")
    except (OSError, ValueError):
        return None

    # 居中裁成正方形再缩放，避免拉伸变形
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2,
                    (w - side) // 2 + side, (h - side) // 2 + side))
    img = img.resize((d, d), Image.LANCZOS)

    mask = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d - 1, d - 1), fill=255)
    out = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)

    # 描一圈边，和猫身的描边风格一致
    ImageDraw.Draw(out).ellipse((0, 0, d - 1, d - 1),
                                outline=(61, 50, 38, 255),
                                width=max(2, d // 40))
    return ImageTk.PhotoImage(out)
