import os
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib import rcParams


def setup_chinese_font():
    """配置matplotlib中文字体"""
    # 常见中文字体路径
    font_paths = [
        # macOS
        "/Users/rzcn86/Library/Fonts/SimHei.ttf",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        # Linux
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Windows
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
    ]

    # 查找可用的中文字体
    chinese_font = None
    for font_path in font_paths:
        if os.path.exists(font_path):
            chinese_font = font_path
            break

    if chinese_font:
        # 添加字体到matplotlib
        fm.fontManager.addfont(chinese_font)
        font_prop = fm.FontProperties(fname=chinese_font)

        # 设置全局字体
        rcParams["font.family"] = font_prop.get_name()
        rcParams["axes.unicode_minus"] = False

        return font_prop
    else:
        # 如果没有找到中文字体，使用系统默认
        rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "sans-serif"]
        rcParams["axes.unicode_minus"] = False
        return None


def get_font_properties():
    """获取字体属性对象"""
    font_paths = [
        "/Users/rzcn86/Library/Fonts/SimHei.ttf",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            return fm.FontProperties(fname=font_path)

    return None


# 初始化字体
font_prop = setup_chinese_font()
