import os
from PIL import Image
from .glyph import Glyph


def write(
    out_dir: str,
    name: str,
    glyphs: dict[int, Glyph],
    pages: list[Image.Image],
    info: dict,
    kernings: list[tuple],
):
    """
    将装箱结果写成 BMFont 文本格式（.fnt + .png）。

    info 字段来自 fnt 来源或 ttf 配置的合并结果。
    kernings 来自 fnt 来源。
    """
    os.makedirs(out_dir, exist_ok=True)

    # 保存纹理图
    page_filenames = []
    for i, img in enumerate(pages):
        filename = f"{name}_{i}.png"
        img.save(os.path.join(out_dir, filename), compress_level=9, optimize=True)
        page_filenames.append(filename)

    # 写 .fnt
    fnt_path = os.path.join(out_dir, f"{name}.fnt")
    with open(fnt_path, "w", encoding="utf-8") as f:
        # info 行
        f.write(
            f'info face="{info.get("face", name)}" '
            f'size={info.get("size", 0)} '
            f'bold={info.get("bold", 0)} '
            f'italic={info.get("italic", 0)} '
            f'charset="{info.get("charset", "")}" '
            f'unicode={info.get("unicode", 1)} '
            f'stretchH={info.get("stretchH", 100)} '
            f'smooth={info.get("smooth", 1)} '
            f'aa={info.get("aa", 1)} '
            f'padding={info.get("padding", "0,0,0,0")} '
            f'spacing={info.get("spacing", "1,1")} '
            f'outline={info.get("outline", 0)}\n'
        )

        # common 行
        f.write(
            f'common '
            f'lineHeight={info.get("lineHeight", 0)} '
            f'base={info.get("base", 0)} '
            f'scaleW={pages[0].width} '
            f'scaleH={pages[0].height} '
            f'pages={len(pages)} '
            f'packed=0 '
            f'alphaChnl={info.get("alphaChnl", 1)} '
            f'redChnl={info.get("redChnl", 0)} '
            f'greenChnl={info.get("greenChnl", 0)} '
            f'blueChnl={info.get("blueChnl", 0)}\n'
        )

        # page 行
        for i, filename in enumerate(page_filenames):
            f.write(f'page id={i} file="{filename}"\n')

        # chars
        f.write(f'chars count={len(glyphs)}\n')
        for char_id, g in sorted(glyphs.items()):
            f.write(
                f'char id={char_id:<5} '
                f'x={g.dst_x:<5} '
                f'y={g.dst_y:<5} '
                f'width={g.width:<5} '
                f'height={g.height:<5} '
                f'xoffset={g.xoffset:<6} '
                f'yoffset={g.yoffset:<6} '
                f'xadvance={g.xadvance:<6} '
                f'page={g.dst_page}  '
                f'chnl=15\n'
            )

        # kernings
        if kernings:
            f.write(f'kernings count={len(kernings)}\n')
            for first, second, amount in kernings:
                f.write(f'kerning first={first} second={second} amount={amount}\n')

    print(f"[done] {fnt_path}  ({len(glyphs)} chars, {len(pages)} page(s))")
