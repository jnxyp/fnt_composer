import sys
import os
import shutil
from core import config_loader, fnt_parser, ttf_extractor, glyph_merger, atlas_packer, fnt_writer


def _apply_vertical_adjustments(base: int, line_height: int, y_adjust: int, extra_line_height: int) -> tuple[int, int, int]:
    return base + y_adjust, line_height + extra_line_height, y_adjust


def _auto_face(sources) -> str:
    parts = []
    for src in sources:
        stem = os.path.splitext(os.path.basename(src.path))[0]
        if src.type == "fnt":
            params = []
            if src.extra_line_height:
                params.append(f"h{src.extra_line_height:+d}")
            if src.xadvance_adjust:
                params.append(f"x{src.xadvance_adjust:+d}")
            if src.y_adjust:
                params.append(f"y{src.y_adjust:+d}")
            part = f"{stem}.fnt"
            if params:
                part += f"({','.join(params)})"
        elif src.type == "ttf":
            params = []
            if src.extra_line_height:
                params.append(f"h{src.extra_line_height:+d}")
            if src.xadvance_adjust:
                params.append(f"x{src.xadvance_adjust:+d}")
            if src.y_adjust:
                params.append(f"y{src.y_adjust:+d}")
            if src.bold:
                params.append(f"b{src.bold:g}")
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

        all_fnt_glyphs: dict = {}
        all_fnt_pages: list = []
        all_fnt_info: dict = {}
        all_fnt_kernings: list = []
        source_line_heights: list[int] = []
        source_bases: list[int] = []

        ttf_glyphs_all: dict = {}

        for src in out.sources:
            if src.type == "fnt":
                glyphs, pages, info, kernings = fnt_parser.parse(src.path)
                src_base, src_line_height, yoffset_delta = _apply_vertical_adjustments(
                    info.get("base", 0),
                    info.get("lineHeight", 0),
                    src.y_adjust,
                    src.extra_line_height,
                )
                source_bases.append(src_base)
                source_line_heights.append(src_line_height)

                glyphs = {cid: g for cid, g in glyphs.items() if cid in out.char_ids}

                page_offset = len(all_fnt_pages)
                for g in glyphs.values():
                    g.src_page += page_offset
                    g.yoffset += yoffset_delta

                all_fnt_pages.extend(pages)
                all_fnt_glyphs.update(glyphs)
                all_fnt_kernings.extend(kernings)

                if not all_fnt_info:
                    all_fnt_info = info

                if src.xadvance_adjust:
                    for g in glyphs.values():
                        g.xadvance += src.xadvance_adjust

            elif src.type == "ttf":
                needed = out.char_ids - set(all_fnt_glyphs.keys()) - set(ttf_glyphs_all.keys())
                if not needed:
                    continue

                src_base, src_line_height, yoffset_delta = _apply_vertical_adjustments(
                    src.size,
                    src.size,
                    src.y_adjust,
                    src.extra_line_height,
                )
                source_bases.append(src_base)
                source_line_heights.append(src_line_height)

                glyphs = ttf_extractor.extract(
                    src.path,
                    src.size,
                    needed,
                    color=src.color,
                    stroke_width=src.stroke_width,
                    stroke_color=src.stroke_color,
                    supersample=src.supersample,
                    hinting=src.hinting,
                    bold=src.bold,
                    starsector_xadvance_compat=src.starsector_xadvance_compat,
                )

                if not all_fnt_info:
                    all_fnt_info = {
                        "face": src.path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
                        "size": src.size,
                        "bold": 0,
                        "italic": 0,
                        "charset": "",
                        "unicode": 1,
                        "stretchH": 100,
                        "smooth": 1,
                        "aa": 1,
                        "padding": "0,0,0,0",
                        "spacing": "1,1",
                        "outline": 0,
                        "lineHeight": src.size,
                        "base": src.size,
                        "alphaChnl": 1,
                        "redChnl": 0,
                        "greenChnl": 0,
                        "blueChnl": 0,
                    }

                if yoffset_delta:
                    for g in glyphs.values():
                        g.yoffset += yoffset_delta

                if src.xadvance_adjust:
                    for g in glyphs.values():
                        g.xadvance += src.xadvance_adjust

                ttf_glyphs_all.update(glyphs)

        merged = glyph_merger.merge(
            out.char_ids,
            [all_fnt_glyphs, ttf_glyphs_all],
            on_missing=out.on_missing,
        )

        fnt_only = {cid: g for cid, g in merged.items() if g.src_image is None}
        ttf_only = {cid: g for cid, g in merged.items() if g.src_image is not None}
        print(f"  fnt chars: {len(fnt_only)}, ttf chars: {len(ttf_only)}")

        pages = atlas_packer.pack(
            fnt_only, all_fnt_pages, ttf_only, out.atlas_width, out.atlas_height, out.padding
        )

        _FIELD_MAP = {
            "x": "dst_x",
            "y": "dst_y",
            "xoffset": "xoffset",
            "yoffset": "yoffset",
            "xadvance": "xadvance",
            "width": "width",
            "height": "height",
        }
        for char_id, fields in (out.overrides or {}).items():
            if char_id not in merged:
                continue
            g = merged[char_id]
            for field, val in fields.items():
                attr = _FIELD_MAP.get(field) or field
                setattr(g, attr, val)

        char_set = set(merged.keys())
        filtered_kernings = [
            (f, s, a) for f, s, a in all_fnt_kernings if f in char_set and s in char_set
        ]

        if source_line_heights:
            all_fnt_info["lineHeight"] = max(source_line_heights)
        if source_bases:
            all_fnt_info["base"] = max(source_bases)
        all_fnt_info["face"] = out.face if out.face is not None else _auto_face(out.sources)
        if out.size is not None:
            all_fnt_info["size"] = out.size
        print(f"  face: {all_fnt_info['face']}")
        fnt_writer.write(out.out_dir, out.name, merged, pages, all_fnt_info, filtered_kernings)


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else "config.yml"
    run(config)
