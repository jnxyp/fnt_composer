import os
import re
from PIL import Image
from .glyph import Glyph


def _parse_fields(line: str) -> dict[str, str]:
    """把 'key=value key2=value2' 解析成字典（value 可能带引号）"""
    result = {}
    for m in re.finditer(r'(\w+)=(".*?"|[^\s]+)', line):
        result[m.group(1)] = m.group(2).strip('"')
    return result


def parse(fnt_path: str) -> tuple[dict[int, Glyph], list[Image.Image], dict, list[tuple]]:
    """
    解析 .fnt 文件。

    返回：
        glyphs   : dict[char_id -> Glyph]，坐标为原始 page 坐标，image=None
        pages    : list[PIL.Image]，原始纹理图列表
        info     : dict，原始 info/common 字段
        kernings : list[(first, second, amount)]
    """
    fnt_dir = os.path.dirname(os.path.abspath(fnt_path))
    pages: list[Image.Image] = []
    glyphs: dict[int, Glyph] = {}
    kernings: list[tuple] = []
    info: dict = {}

    with open(fnt_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            tag = line.split()[0]
            fields = _parse_fields(line)

            if tag == "info":
                info["face"] = fields.get("face", "")
                info["size"] = int(fields.get("size", 0))
                info["bold"] = int(fields.get("bold", 0))
                info["italic"] = int(fields.get("italic", 0))
                info["charset"] = fields.get("charset", "")
                info["unicode"] = int(fields.get("unicode", 1))
                info["stretchH"] = int(fields.get("stretchH", 100))
                info["smooth"] = int(fields.get("smooth", 1))
                info["aa"] = int(fields.get("aa", 1))
                info["padding"] = fields.get("padding", "0,0,0,0")
                info["spacing"] = fields.get("spacing", "1,1")
                info["outline"] = int(fields.get("outline", 0))

            elif tag == "common":
                info["lineHeight"] = int(fields.get("lineHeight", 0))
                info["base"] = int(fields.get("base", 0))
                info["scaleW"] = int(fields.get("scaleW", 512))
                info["scaleH"] = int(fields.get("scaleH", 512))
                info["alphaChnl"] = int(fields.get("alphaChnl", 1))
                info["redChnl"] = int(fields.get("redChnl", 0))
                info["greenChnl"] = int(fields.get("greenChnl", 0))
                info["blueChnl"] = int(fields.get("blueChnl", 0))

            elif tag == "page":
                page_id = int(fields["id"])
                img_file = fields["file"]
                img_path = os.path.join(fnt_dir, img_file)
                img = Image.open(img_path).convert("RGBA")
                # 确保列表够长
                while len(pages) <= page_id:
                    pages.append(None)
                pages[page_id] = img

            elif tag == "char":
                char_id = int(fields["id"])
                g = Glyph(
                    char_id=char_id,
                    xoffset=int(fields.get("xoffset", 0)),
                    yoffset=int(fields.get("yoffset", 0)),
                    xadvance=int(fields.get("xadvance", 0)),
                    src_page=int(fields.get("page", 0)),
                    src_x=int(fields.get("x", 0)),
                    src_y=int(fields.get("y", 0)),
                    src_w=int(fields.get("width", 0)),
                    src_h=int(fields.get("height", 0)),
                )
                glyphs[char_id] = g

            elif tag == "kerning":
                kernings.append((
                    int(fields["first"]),
                    int(fields["second"]),
                    int(fields["amount"]),
                ))

    return glyphs, pages, info, kernings
