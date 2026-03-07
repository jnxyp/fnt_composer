import freetype
from PIL import Image
from .glyph import Glyph


def extract(
    ttf_path: str,
    size: int,
    char_ids: set[int],
    color: tuple = (255, 255, 255),
    stroke_width: int = 0,
    stroke_color: tuple = (0, 0, 0),
) -> dict[int, Glyph]:
    """
    从 TTF 文件渲染指定字符集，返回 dict[char_id -> Glyph]。
    字形存在 Glyph.src_image（RGBA），坐标字段留空由 atlas_packer 填写。
    """
    import io
    with open(ttf_path, "rb") as f:
        font_data = f.read()
    face = freetype.Face(io.BytesIO(font_data))
    face.set_pixel_sizes(0, size)
    ascender = face.size.ascender >> 6  # 基线距字形格顶部的像素数

    glyphs: dict[int, Glyph] = {}

    for char_id in char_ids:
        glyph_index = face.get_char_index(char_id)
        if glyph_index == 0:
            # 字体不包含此字符
            continue

        face.load_glyph(glyph_index, freetype.FT_LOAD_RENDER)
        slot = face.glyph
        bitmap = slot.bitmap

        w, h = bitmap.width, bitmap.rows
        xoffset = slot.bitmap_left
        yoffset = ascender - slot.bitmap_top   # 转为从顶部算的 yoffset
        xadvance = slot.advance.x >> 6

        if w == 0 or h == 0:
            # 空白字符（如空格），生成 1x1 透明图占位
            img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        else:
            # 构建 alpha 蒙版
            alpha = bytes(bitmap.buffer)
            img = _render_glyph(alpha, w, h, color, stroke_width, stroke_color)

        glyphs[char_id] = Glyph(
            char_id=char_id,
            xoffset=xoffset,
            yoffset=yoffset,
            xadvance=xadvance,
            src_image=img,
        )

    return glyphs


def _render_glyph(
    alpha: bytes,
    w: int,
    h: int,
    color: tuple,
    stroke_width: int,
    stroke_color: tuple,
) -> Image.Image:
    # 基础字形层
    r, g, b = color[:3]
    pixels = []
    for a in alpha:
        pixels.extend([r, g, b, a])
    base = Image.frombytes("RGBA", (w, h), bytes(pixels))

    if stroke_width <= 0:
        return base

    # 描边层：将 base 向8个方向偏移并合成
    sw = stroke_width
    canvas_w, canvas_h = w + sw * 2, h + sw * 2
    stroke_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    sr, sg, sb = stroke_color[:3]
    stroke_glyph = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i, a in enumerate(alpha):
        if a > 0:
            px, py = i % w, i // w
            stroke_glyph.putpixel((px, py), (sr, sg, sb, a))

    for dy in range(-sw, sw + 1):
        for dx in range(-sw, sw + 1):
            if dx == 0 and dy == 0:
                continue
            stroke_layer.paste(stroke_glyph, (sw + dx, sw + dy), stroke_glyph)

    # 在描边层上叠加字形
    canvas = stroke_layer.copy()
    canvas.paste(base, (sw, sw), base)
    return canvas
