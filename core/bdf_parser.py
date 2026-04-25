import math
from PIL import Image
from .glyph import Glyph


def parse(bdf_path: str, color: tuple = (255, 255, 255)) -> tuple[dict[int, Glyph], dict]:
    """
    Parse a BDF bitmap font into Glyph objects with RGBA source images.

    Only encoded glyphs are returned. ENCODING is treated as the output char id.
    """
    glyphs: dict[int, Glyph] = {}
    props: dict[str, str] = {}
    info: dict = {}

    current: dict | None = None
    bitmap_rows: list[str] = []
    in_props = False
    in_bitmap = False

    with open(bdf_path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if in_bitmap:
                if line == "ENDCHAR":
                    if current is not None:
                        _finish_glyph(current, bitmap_rows, color, glyphs, info)
                    current = None
                    bitmap_rows = []
                    in_bitmap = False
                else:
                    bitmap_rows.append(line)
                continue

            parts = line.split()
            tag = parts[0]

            if tag == "STARTPROPERTIES":
                in_props = True
                continue
            if tag == "ENDPROPERTIES":
                in_props = False
                continue
            if in_props and len(parts) >= 2:
                props[tag] = _unquote(line[len(tag):].strip())
                continue

            if tag == "FONT":
                info["face"] = line[len("FONT"):].strip()
            elif tag == "SIZE" and len(parts) >= 2:
                info["size"] = int(parts[1])
            elif tag == "FONTBOUNDINGBOX" and len(parts) >= 5:
                info["font_bbx"] = tuple(int(v) for v in parts[1:5])
            elif tag == "STARTCHAR":
                current = {
                    "name": line[len("STARTCHAR"):].strip(),
                    "encoding": -1,
                    "dwidth": 0,
                    "bbx": (0, 0, 0, 0),
                }
            elif current is not None:
                if tag == "ENCODING" and len(parts) >= 2:
                    current["encoding"] = int(parts[1])
                elif tag == "DWIDTH" and len(parts) >= 2:
                    current["dwidth"] = int(parts[1])
                elif tag == "BBX" and len(parts) >= 5:
                    current["bbx"] = tuple(int(v) for v in parts[1:5])
                elif tag == "BITMAP":
                    bitmap_rows = []
                    in_bitmap = True

    _fill_info_defaults(info, props)
    return glyphs, info


def _finish_glyph(
    current: dict,
    bitmap_rows: list[str],
    color: tuple,
    glyphs: dict[int, Glyph],
    info: dict,
):
    char_id = current["encoding"]
    if char_id < 0:
        return

    width, height, xoff, yoff = current["bbx"]
    xadvance = current["dwidth"]
    base = _get_base(info)
    yoffset = base - yoff - height

    img = _bitmap_to_image(bitmap_rows, width, height, color)
    glyphs[char_id] = Glyph(
        char_id=char_id,
        xoffset=xoff,
        yoffset=yoffset,
        xadvance=xadvance,
        src_image=img,
    )


def _bitmap_to_image(rows: list[str], width: int, height: int, color: tuple) -> Image.Image:
    if width <= 0 or height <= 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    r, g, b = color[:3]
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = img.load()
    bytes_per_row = math.ceil(width / 8)

    for y in range(min(height, len(rows))):
        row = rows[y]
        bits = bin(int(row, 16))[2:].zfill(bytes_per_row * 8)
        for x in range(width):
            if bits[x] == "1":
                px[x, y] = (r, g, b, 255)
    return img


def _fill_info_defaults(info: dict, props: dict[str, str]):
    ascent = _int_prop(props, "FONT_ASCENT")
    descent = _int_prop(props, "FONT_DESCENT")
    if ascent is None or descent is None:
        font_bbx = info.get("font_bbx", (0, info.get("size", 16), 0, 0))
        _, bbx_h, _, bbx_yoff = font_bbx
        descent = abs(min(0, bbx_yoff)) if descent is None else descent
        ascent = bbx_h - descent if ascent is None else ascent

    line_height = ascent + descent
    info.update({
        "face": props.get("FACE_NAME") or props.get("FONT_NAME") or info.get("face", ""),
        "size": int(props.get("PIXEL_SIZE", info.get("size", line_height))),
        "bold": 1 if props.get("WEIGHT_NAME", "").lower() == "bold" else 0,
        "italic": 0,
        "charset": "",
        "unicode": 1,
        "stretchH": 100,
        "smooth": 0,
        "aa": 1,
        "padding": "0,0,0,0",
        "spacing": "1,1",
        "outline": 0,
        "lineHeight": line_height,
        "base": ascent,
        "alphaChnl": 1,
        "redChnl": 0,
        "greenChnl": 0,
        "blueChnl": 0,
    })


def _get_base(info: dict) -> int:
    if "base" in info:
        return int(info["base"])
    font_bbx = info.get("font_bbx", (0, info.get("size", 16), 0, 0))
    _, bbx_h, _, bbx_yoff = font_bbx
    return bbx_h - abs(min(0, bbx_yoff))


def _int_prop(props: dict[str, str], name: str) -> int | None:
    value = props.get(name)
    if value is None:
        return None
    return int(value)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value
