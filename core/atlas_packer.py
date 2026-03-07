from PIL import Image
from .glyph import Glyph


def pack(
    fnt_glyphs: dict[int, Glyph],
    fnt_pages: list[Image.Image],
    ttf_glyphs: dict[int, Glyph],
    atlas_width: int,
    atlas_height: int,
    padding: int,
) -> list[Image.Image]:
    """
    两阶段装箱：
    1. 将 fnt 的原始 page 整张复制到输出图集开头（像素保真）
    2. 用 Shelf 算法将 ttf 字形追加进剩余空间

    更新所有 Glyph 的 dst_page / dst_x / dst_y。
    返回输出图集列表。
    """
    output_pages: list[Image.Image] = []

    # ── 阶段1：fnt pages 整张复制 ────────────────────────────────────────
    for page_idx, src_img in enumerate(fnt_pages):
        if src_img.width > atlas_width or src_img.height > atlas_height:
            raise ValueError(
                f"fnt page {page_idx} size {src_img.size} exceeds atlas "
                f"size {atlas_width}x{atlas_height}"
            )
        canvas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))
        canvas.paste(src_img, (0, 0))
        output_pages.append(canvas)

    # fnt 字形坐标平移（page 内坐标不变，只更新 dst_page/dst_x/dst_y）
    for g in fnt_glyphs.values():
        g.dst_page = g.src_page
        g.dst_x = g.src_x
        g.dst_y = g.src_y

    # ── 阶段2：ttf 字形 Shelf 装箱 ──────────────────────────────────────
    if not ttf_glyphs:
        return output_pages

    # 按高度降序排列（减少 shelf 浪费）
    sorted_glyphs = sorted(ttf_glyphs.values(), key=lambda g: g.height, reverse=True)

    # 当前装箱状态
    cur_page = len(output_pages) - 1 if output_pages else -1
    shelf_x = 0
    shelf_y = 0
    shelf_h = 0  # 当前行最大高度

    # 如果没有 fnt pages，或者最后一张 fnt page 还有剩余空间，在其上继续装箱
    if not output_pages:
        output_pages.append(Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0)))
        cur_page = 0
        shelf_x = 0
        shelf_y = 0
        shelf_h = 0
    else:
        # 从最后一张 fnt page 下方开始（fnt page 已完整铺满其原始内容）
        # 找 fnt 最后一张 page 中最低像素行，以此为起点
        last_fnt_height = fnt_pages[-1].height if fnt_pages else 0
        shelf_y = last_fnt_height
        shelf_x = 0
        shelf_h = 0

    def new_page():
        nonlocal cur_page, shelf_x, shelf_y, shelf_h
        output_pages.append(Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0)))
        cur_page = len(output_pages) - 1
        shelf_x = 0
        shelf_y = 0
        shelf_h = 0

    for g in sorted_glyphs:
        gw = g.width + padding * 2
        gh = g.height + padding * 2

        if gw > atlas_width or gh > atlas_height:
            print(f"[warning] glyph U+{g.char_id:04X} size {g.width}x{g.height} "
                  f"too large for atlas, skipped")
            continue

        # 当前行放不下 → 换行
        if shelf_x + gw > atlas_width:
            shelf_y += shelf_h
            shelf_x = 0
            shelf_h = 0

        # 当前 page 放不下 → 新 page
        if shelf_y + gh > atlas_height:
            new_page()

        # 贴图
        canvas = output_pages[cur_page]
        canvas.paste(g.src_image, (shelf_x + padding, shelf_y + padding), g.src_image)

        g.dst_page = cur_page
        g.dst_x = shelf_x + padding
        g.dst_y = shelf_y + padding

        shelf_x += gw
        shelf_h = max(shelf_h, gh)

    return output_pages
