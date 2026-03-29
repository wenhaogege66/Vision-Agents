"""问题文字背景图片生成器：使用 Pillow 为 HeyGen 多场景视频生成问题背景图。"""

import logging
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# 系统中文字体搜索路径（macOS / Linux / Windows）
_FONT_SEARCH_PATHS = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]

# 配色
_BG_COLOR_TOP = (26, 26, 46)       # #1a1a2e
_BG_COLOR_BOTTOM = (22, 33, 62)    # #16213e
_TEXT_COLOR = (255, 255, 255)       # white


def _find_chinese_font() -> str | None:
    """尝试在系统中查找可用的中文字体文件路径。"""
    import os

    for path in _FONT_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """加载指定大小的字体，找不到中文字体时回退到默认字体。"""
    font_path = _find_chinese_font()
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            logger.warning("无法加载字体 %s，回退到默认字体", font_path)
    else:
        logger.warning("未找到系统中文字体，回退到 Pillow 默认字体")
    return ImageFont.load_default(size)


def _draw_gradient(img: Image.Image) -> None:
    """在图片上绘制从上到下的深蓝渐变背景。"""
    width, height = img.size
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(_BG_COLOR_TOP[0] + (_BG_COLOR_BOTTOM[0] - _BG_COLOR_TOP[0]) * ratio)
        g = int(_BG_COLOR_TOP[1] + (_BG_COLOR_BOTTOM[1] - _BG_COLOR_TOP[1]) * ratio)
        b = int(_BG_COLOR_TOP[2] + (_BG_COLOR_BOTTOM[2] - _BG_COLOR_TOP[2]) * ratio)
        for x in range(width):
            img.putpixel((x, y), (r, g, b))


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    """将文本按最大宽度自动换行，返回行列表。"""
    lines: list[str] = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = font.getbbox(test_line)
        line_width = bbox[2] - bbox[0]
        if line_width > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines


class BackgroundImageGenerator:
    """使用 Pillow 生成问题文字背景图片。

    布局：左侧 40% 留给数字人 avatar，右侧 60% 显示问题序号和文字。
    配色：深蓝渐变背景 (#1a1a2e → #16213e) + 白色文字。
    """

    # 字体大小
    TITLE_FONT_SIZE = 48
    CONTENT_FONT_SIZE = 36
    MIN_CONTENT_FONT_SIZE = 20

    def generate(
        self,
        question_number: int,
        question_text: str,
        width: int = 1920,
        height: int = 1080,
    ) -> bytes:
        """生成包含问题序号和文字的 PNG 背景图片。

        Args:
            question_number: 问题序号（如 1, 2, 3）
            question_text: 问题文字内容
            width: 图片宽度，默认 1920
            height: 图片高度，默认 1080

        Returns:
            PNG 格式图片的 bytes
        """
        img = Image.new("RGB", (width, height))
        _draw_gradient(img)
        draw = ImageDraw.Draw(img)

        # 右侧文字区域：从 40% 处开始，留 padding
        padding = 40
        text_area_left = int(width * 0.4) + padding
        text_area_right = width - padding
        text_area_width = text_area_right - text_area_left

        # 绘制问题标题 "问题 N"
        title_font = _load_font(self.TITLE_FONT_SIZE)
        title_text = f"问题 {question_number}"
        title_y = int(height * 0.15)
        draw.text((text_area_left, title_y), title_text, fill=_TEXT_COLOR, font=title_font)

        # 绘制问题内容（自动换行，必要时缩小字体）
        if question_text:
            self._draw_question_content(
                draw, question_text, text_area_left, title_y, text_area_width, height, padding
            )

        # 输出 PNG bytes
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _draw_question_content(
        self,
        draw: ImageDraw.Draw,
        text: str,
        text_area_left: int,
        title_y: int,
        text_area_width: int,
        height: int,
        padding: int,
    ) -> None:
        """绘制问题内容文字，自动换行，必要时缩小字体。"""
        font_size = self.CONTENT_FONT_SIZE
        content_y_start = title_y + self.TITLE_FONT_SIZE + 40  # 标题下方留间距
        max_text_height = height - content_y_start - padding

        while font_size >= self.MIN_CONTENT_FONT_SIZE:
            content_font = _load_font(font_size)
            lines = _wrap_text(text, content_font, text_area_width)
            line_height = font_size + 12
            total_text_height = len(lines) * line_height

            if total_text_height <= max_text_height:
                # 垂直居中于可用区域
                y_offset = content_y_start + (max_text_height - total_text_height) // 2
                for line in lines:
                    draw.text((text_area_left, y_offset), line, fill=_TEXT_COLOR, font=content_font)
                    y_offset += line_height
                return

            font_size -= 2

        # 字体已缩到最小，仍然绘制（可能溢出）
        content_font = _load_font(self.MIN_CONTENT_FONT_SIZE)
        lines = _wrap_text(text, content_font, text_area_width)
        line_height = self.MIN_CONTENT_FONT_SIZE + 12
        y_offset = content_y_start
        for line in lines:
            if y_offset + line_height > height - padding:
                break
            draw.text((text_area_left, y_offset), line, fill=_TEXT_COLOR, font=content_font)
            y_offset += line_height
