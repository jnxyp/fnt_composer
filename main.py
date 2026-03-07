import sys
from core import config_loader, fnt_parser, ttf_extractor, glyph_merger, atlas_packer, fnt_writer


def run(config_path: str = "config.json"):
    outputs = config_loader.load(config_path)

    for out in outputs:
        print(f"\n=== {out.name} ===")

        # 1. 按来源提取字形
        fnt_glyphs_list = []   # list of dict[int, Glyph]，来自 fnt sources
        fnt_pages_combined = []
        all_fnt_glyphs: dict = {}
        all_fnt_pages: list = []
        all_fnt_info: dict = {}
        all_fnt_kernings: list = []

        ttf_glyphs_all: dict = {}

        fnt_char_ids: set[int] = set()

        for src in out.sources:
            if src.type == "fnt":
                glyphs, pages, info, kernings = fnt_parser.parse(src.path)
                # 只保留 config 要求的字符
                glyphs = {cid: g for cid, g in glyphs.items() if cid in out.char_ids}
                # 重新映射 page 索引（偏移已有 pages 数量）
                page_offset = len(all_fnt_pages)
                for g in glyphs.values():
                    g.src_page += page_offset
                all_fnt_pages.extend(pages)
                all_fnt_glyphs.update(glyphs)
                all_fnt_kernings.extend(kernings)
                if not all_fnt_info:
                    all_fnt_info = info

            elif src.type == "ttf":
                # 只渲染 fnt 来源没有覆盖到的字符
                needed = out.char_ids - set(all_fnt_glyphs.keys()) - set(ttf_glyphs_all.keys())
                if not needed:
                    continue
                glyphs = ttf_extractor.extract(
                    src.path, src.size, needed,
                    color=src.color,
                    stroke_width=src.stroke_width,
                    stroke_color=src.stroke_color,
                )
                # 如果 fnt 没有提供 info，用 ttf 配置补充
                if not all_fnt_info:
                    all_fnt_info = {
                        "face": src.path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
                        "size": src.size,
                        "bold": 0, "italic": 0, "charset": "",
                        "unicode": 1, "stretchH": 100,
                        "smooth": 1, "aa": 1,
                        "padding": "0,0,0,0", "spacing": "1,1", "outline": 0,
                        "lineHeight": src.size + 2,
                        "base": src.size,
                        "alphaChnl": 1, "redChnl": 0, "greenChnl": 0, "blueChnl": 0,
                    }
                ttf_glyphs_all.update(glyphs)

        # 2. 合并（fnt 优先）
        merged = glyph_merger.merge(
            out.char_ids,
            [all_fnt_glyphs, ttf_glyphs_all],
            on_missing=out.on_missing,
        )

        fnt_only = {cid: g for cid, g in merged.items() if g.src_image is None}
        ttf_only = {cid: g for cid, g in merged.items() if g.src_image is not None}
        print(f"  fnt chars: {len(fnt_only)}, ttf chars: {len(ttf_only)}")

        # 3. 装箱
        pages = atlas_packer.pack(
            fnt_only, all_fnt_pages, ttf_only,
            out.atlas_width, out.atlas_height, out.padding,
        )

        # 4. 过滤 kerning（只保留两端字符都在结果集里的 pair）
        char_set = set(merged.keys())
        filtered_kernings = [
            (f, s, a) for f, s, a in all_fnt_kernings
            if f in char_set and s in char_set
        ]

        # 5. 输出
        fnt_writer.write(out.dir, out.name, merged, pages, all_fnt_info, filtered_kernings)


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    run(config)
