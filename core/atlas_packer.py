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
    统一 Shelf 装箱：
    - fnt 字形从原始 page 裁剪出像素后，与 ttf 字形一起重新排布
    - 不再整页复制，充分利用空间

    更新所有 Glyph 的 dst_page / dst_x / dst_y。
    返回输出图集列表。
    """
    unlimited_height = atlas_height == -1

    # ── fnt 字形：从原始 page 裁剪出 src_image（像素原样保留，R=G=B=A）──
    for g in fnt_glyphs.values():
        src_page = fnt_pages[g.src_page]
        assert src_page is not None, f"fnt page {g.src_page} is None"
        g.src_image = src_page.crop((g.src_x, g.src_y, g.src_x + g.width, g.src_y + g.height))

    # ── ttf 字形：(255,255,255,A) → (A,A,A,A)，与 fnt 格式统一 ──────────
    for g in ttf_glyphs.values():
        if g.src_image is not None:
            a = g.src_image.split()[3]
            g.src_image = Image.merge("RGBA", (a, a, a, a))

    # ── 所有字形按高度降序排列后统一装箱 ───────────────────────────────
    all_glyphs = list(fnt_glyphs.values()) + list(ttf_glyphs.values())
    sorted_glyphs = sorted(all_glyphs, key=lambda g: g.height, reverse=True)

    output_pages: list[Image.Image] = []

    if not sorted_glyphs:
        return output_pages

    h = atlas_height if not unlimited_height else 0
    output_pages.append(Image.new("RGBA", (atlas_width, h), (0, 0, 0, 0)))
    cur_page = 0
    shelf_x = 0
    shelf_y = 0
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
        # 不使用 mask：canvas 背景透明，直接覆盖保留原始像素值
        canvas.paste(g.src_image, (shelf_x + padding, shelf_y + padding))

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
