import freetype
from PIL import Image, ImageFilter
from .glyph import Glyph


def extract(
    ttf_path: str,
    size: int,
    char_ids: set[int],
    color: tuple = (255, 255, 255),
    stroke_width: int = 0,
    stroke_color: tuple = (0, 0, 0),
    supersample: int = 1,
    hinting: str = "normal",
    bold: float = 0,
    starsector_xadvance_compat: bool = False,
) -> dict[int, Glyph]:
    """
    从 TTF 文件渲染指定字符集，返回 dict[char_id -> Glyph]。
    supersample: 超采样倍数（1=不超采样，2/4=2x/4x），渲染后 Lanczos 降采样。
    hinting: "normal" | "light" | "none"
    """
    import io
    with open(ttf_path, "rb") as f:
        font_data = f.read()
    face = freetype.Face(io.BytesIO(font_data))

    ss = max(1, supersample)
    face.set_pixel_sizes(0, size * ss)
    ascender = face.size.ascender >> 6  # 高分辨率下的 ascender

    if hinting == "light":
        load_flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_LIGHT
    elif hinting == "none":
        load_flags = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING
    else:
        load_flags = freetype.FT_LOAD_RENDER

    # 固定 canvas 高度：所有字形共用同一 Y 轴缩放比，消除逐字形独立缩放引起的 ±1px 垂直抖动
    descender_budget = round(size * ss * 0.5)
    canvas_h_ss = ascender + descender_budget
    canvas_th = max(1, round(canvas_h_ss / ss))  # 对所有字形完全一致

    sw_ss = stroke_width * ss
    bold_ss = round(bold * ss)  # 高分辨率下的膨胀半径

    # metrics（xadvance/xoffset）从原始 size 获取，与超采样倍数无关，避免舍入差异
    metrics_face = freetype.Face(io.BytesIO(font_data))
    metrics_face.set_pixel_sizes(0, size)
    metrics_flags = freetype.FT_LOAD_DEFAULT | freetype.FT_LOAD_NO_HINTING

    glyphs: dict[int, Glyph] = {}

    for char_id in char_ids:
        glyph_index = face.get_char_index(char_id)
        if glyph_index == 0:
            continue

        metrics_face.load_glyph(glyph_index, metrics_flags)
        mslot = metrics_face.glyph
        xoffset  = mslot.bitmap_left - stroke_width
        xadvance = mslot.advance.x >> 6

        face.load_glyph(glyph_index, load_flags)

        slot = face.glyph
        bitmap = slot.bitmap

        w, h = bitmap.width, bitmap.rows

        if w == 0 or h == 0:
            img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            yoffset = 0
        else:
            alpha = bytes(bitmap.buffer)
            glyph_img_ss = _render_glyph(alpha, w, h, color, sw_ss, stroke_color)
            # glyph_img_ss 尺寸：(w + 2*sw_ss, h + 2*sw_ss)

            if bold_ss > 0:
                r, g, b, a = glyph_img_ss.split()
                a = a.filter(ImageFilter.MaxFilter(2 * bold_ss + 1))
                glyph_img_ss = Image.merge("RGBA", (r, g, b, a))

            canvas_w_ss = w + sw_ss * 2
            canvas_ss = Image.new("RGBA", (canvas_w_ss, canvas_h_ss), (0, 0, 0, 0))

            # 字形在 canvas 中的纵向位置：顶边 = ascender - bitmap_top（含描边偏移）
            paste_y = (ascender - slot.bitmap_top) - sw_ss

            # 裁剪超出 canvas 的部分
            src_y0 = max(0, -paste_y)
            dst_y0 = max(0, paste_y)
            paste_h = min(glyph_img_ss.height - src_y0, canvas_h_ss - dst_y0)
            if paste_h > 0:
                region = glyph_img_ss.crop((0, src_y0, glyph_img_ss.width, src_y0 + paste_h))
                canvas_ss.paste(region, (0, dst_y0), region)

            # 下采样：canvas_th 对所有字形相同，保证 Y 缩放一致
            tw = max(1, round(canvas_w_ss / ss))
            canvas_down = canvas_ss.resize((tw, canvas_th), Image.LANCZOS)

            bbox = canvas_down.getbbox()
            if bbox:
                img = canvas_down.crop(bbox)
                yoffset = bbox[1]
            else:
                img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
                yoffset = 0

        if starsector_xadvance_compat and xoffset > 0:
            xadvance = xadvance - xoffset

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
