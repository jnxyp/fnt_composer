from PIL import Image
from .glyph import Glyph


def _next_pow2(n: int) -> int:
    if n <= 0:
        return 1
    p = 1
    while p < n:
        p <<= 1
    return p


def pack(
    fnt_glyphs: dict[int, Glyph],
    fnt_pages: list[Image.Image | None],
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
    unlimited_height = atlas_height == -1
    output_pages: list[Image.Image] = []

    # ── 阶段1：fnt pages 整张复制 ────────────────────────────────────────
    for page_idx, src_img in enumerate(fnt_pages):
        assert src_img is not None, f"fnt page {page_idx} is None"
        if src_img.width > atlas_width:
            raise ValueError(
                f"fnt page {page_idx} width {src_img.width} exceeds atlas width {atlas_width}"
            )
        if not unlimited_height and src_img.height > atlas_height:
            raise ValueError(
                f"fnt page {page_idx} height {src_img.height} exceeds atlas height {atlas_height}"
            )
        h = atlas_height if not unlimited_height else src_img.height
        canvas = Image.new("RGBA", (atlas_width, h), (0, 0, 0, 0))
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
        h = atlas_height if not unlimited_height else 0
        output_pages.append(Image.new("RGBA", (atlas_width, h), (0, 0, 0, 0)))
        cur_page = 0
        shelf_x = 0
        shelf_y = 0
        shelf_h = 0
    else:
        last_page = fnt_pages[-1] if fnt_pages else None
        last_fnt_height = last_page.height if last_page is not None else 0
        shelf_y = last_fnt_height
        shelf_x = 0
        shelf_h = 0

    def new_page():
        nonlocal cur_page, shelf_x, shelf_y, shelf_h
        h = atlas_height if not unlimited_height else 0
        output_pages.append(Image.new("RGBA", (atlas_width, h), (0, 0, 0, 0)))
        cur_page = len(output_pages) - 1
        shelf_x = 0
        shelf_y = 0
        shelf_h = 0

    for g in sorted_glyphs:
        gw = g.width + padding * 2
        gh = g.height + padding * 2

        if gw > atlas_width:
            print(f"[warning] glyph U+{g.char_id:04X} size {g.width}x{g.height} "
                  f"too wide for atlas, skipped")
            continue
        if not unlimited_height and gh > atlas_height:
            print(f"[warning] glyph U+{g.char_id:04X} size {g.width}x{g.height} "
                  f"too tall for atlas, skipped")
            continue

        # 当前行放不下 → 换行
        if shelf_x + gw > atlas_width:
            shelf_y += shelf_h
            shelf_x = 0
            shelf_h = 0

        # 有限高度模式：当前 page 放不下 → 新 page
        if not unlimited_height and shelf_y + gh > atlas_height:
            new_page()

        # unlimited 模式：动态扩展当前 page 高度
        if unlimited_height:
            canvas = output_pages[cur_page]
            needed_h = shelf_y + gh
            if needed_h > canvas.height:
                expanded = Image.new("RGBA", (atlas_width, needed_h), (0, 0, 0, 0))
                expanded.paste(canvas, (0, 0))
                output_pages[cur_page] = expanded

        canvas = output_pages[cur_page]
        assert g.src_image is not None
        canvas.paste(g.src_image, (shelf_x + padding, shelf_y + padding), g.src_image)

        g.dst_page = cur_page
        g.dst_x = shelf_x + padding
        g.dst_y = shelf_y + padding

        shelf_x += gw
        shelf_h = max(shelf_h, gh)

    # unlimited 模式：将每张图的高度对齐到 2^n
    if unlimited_height:
        for i, page in enumerate(output_pages):
            target_h = _next_pow2(page.height)
            if target_h != page.height:
                padded = Image.new("RGBA", (atlas_width, target_h), (0, 0, 0, 0))
                padded.paste(page, (0, 0))
                output_pages[i] = padded

    return output_pages
