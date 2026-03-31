import sys
import os
import shutil
from core import config_loader, fnt_parser, ttf_extractor, glyph_merger, atlas_packer, fnt_writer

def _auto_face(sources) -> str:
    parts = []
    for src in sources:
        stem = os.path.splitext(os.path.basename(src.path))[0]
        if src.type == "fnt":
            params = []
            if src.line_height_adjust: params.append(f"h{src.line_height_adjust:+d}")
            if src.xadvance_adjust:    params.append(f"x{src.xadvance_adjust:+d}")
            if src.y_adjust:           params.append(f"y{src.y_adjust:+d}")
            part = f"{stem}.fnt"
            if params:
                part += f"({','.join(params)})"
        elif src.type == "ttf":
            params = []
            if src.line_height_adjust: params.append(f"h{src.line_height_adjust:+d}")
            if src.xadvance_adjust:    params.append(f"x{src.xadvance_adjust:+d}")
            if src.y_adjust:           params.append(f"y{src.y_adjust:+d}")
            if src.bold:               params.append(f"b{src.bold:g}")
            params.append(f"hint:{src.hinting}")
            part = f"{stem}@{src.size}x{src.supersample}({','.join(params)})"
        else:
            continue
        parts.append(part)
    return "+".join(parts)


def run(config_path: str = "config.json"):
    run_cfg = config_loader.load(config_path)

    if run_cfg.clean_output:
        for d in dict.fromkeys(out.out_dir for out in run_cfg.outputs):
            if os.path.isdir(d):
                shutil.rmtree(d)
                print(f"[clean] {d}")

    for out in run_cfg.outputs:
        label = f"{out.dir}/{out.name}" if out.dir else out.name
        print(f"\n=== {label} ===")

        # 1. 按来源提取字形
        all_fnt_glyphs: dict = {}
        all_fnt_pages: list = []
        all_fnt_info: dict = {}
        all_fnt_kernings: list = []

        ttf_glyphs_all: dict = {}

        for src in out.sources:
            if src.type == "fnt":
                glyphs, pages, info, kernings = fnt_parser.parse(src.path)
                # 只保留 config 要求的字符
                glyphs = {cid: g for cid, g in glyphs.items() if cid in out.char_ids}
                # 重新映射 page 索引（偏移已有 pages 数量）
                page_offset = len(all_fnt_pages)
                for g in glyphs.values():
                    g.src_page += page_offset
                    g.yoffset += src.y_adjust
                all_fnt_pages.extend(pages)
                all_fnt_glyphs.update(glyphs)
                all_fnt_kernings.extend(kernings)
                if not all_fnt_info:
                    all_fnt_info = info
                if src.y_adjust:
                    all_fnt_info["base"] = all_fnt_info.get("base", 0) + src.y_adjust
                if src.xadvance_adjust:
                    for g in glyphs.values():
                        g.xadvance += src.xadvance_adjust
                if src.line_height_adjust:
                    all_fnt_info["lineHeight"] = all_fnt_info.get("lineHeight", 0) + src.line_height_adjust
                    half = src.line_height_adjust // 2
                    if half:
                        all_fnt_info["base"] = all_fnt_info.get("base", 0) + half
                        for g in glyphs.values():
                            g.yoffset += half

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
                    supersample=src.supersample,
                    hinting=src.hinting,
                    bold=src.bold,
                    starsector_xadvance_compat=src.starsector_xadvance_compat,
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
                if src.y_adjust:
                    all_fnt_info["base"] = all_fnt_info.get("base", 0) + src.y_adjust
                    for g in glyphs.values():
                        g.yoffset += src.y_adjust
                if src.xadvance_adjust:
                    for g in glyphs.values():
                        g.xadvance += src.xadvance_adjust
                if src.line_height_adjust:
                    all_fnt_info["lineHeight"] = all_fnt_info.get("lineHeight", 0) + src.line_height_adjust
                    half = src.line_height_adjust // 2
                    if half:
                        all_fnt_info["base"] = all_fnt_info.get("base", 0) + half
                        for g in glyphs.values():
                            g.yoffset += half
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

        # 4. 应用 overrides
        _FIELD_MAP = {
            "x": "dst_x", "y": "dst_y",
            "xoffset": "xoffset", "yoffset": "yoffset",
            "xadvance": "xadvance", "width": "width", "height": "height",
        }
        for char_id, fields in (out.overrides or {}).items():
            if char_id not in merged:
                continue
            g = merged[char_id]
            for field, val in fields.items():
                attr = _FIELD_MAP.get(field) or field
                setattr(g, attr, val)

        # 5. 过滤 kerning（只保留两端字符都在结果集里的 pair）
        char_set = set(merged.keys())
        filtered_kernings = [
            (f, s, a) for f, s, a in all_fnt_kernings
            if f in char_set and s in char_set
        ]

        # 6. 输出
        all_fnt_info["face"] = out.face if out.face is not None else _auto_face(out.sources)
        if out.size is not None:
            all_fnt_info["size"] = out.size
        print(f"  face: {all_fnt_info['face']}")
        fnt_writer.write(out.out_dir, out.name, merged, pages, all_fnt_info, filtered_kernings)


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else "config.yml"
    run(config)
