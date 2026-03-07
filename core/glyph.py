from dataclasses import dataclass
from PIL import Image


@dataclass
class Glyph:
    char_id: int
    xoffset: int
    yoffset: int
    xadvance: int

    # fnt 来源：保留原始纹理坐标，image 为 None
    src_image: Image.Image | None = None   # ttf 来源的渲染位图
    src_page: int = 0                      # fnt 来源的原始 page 索引
    src_x: int = 0                         # fnt 来源在原始 page 中的 x
    src_y: int = 0                         # fnt 来源在原始 page 中的 y
    src_w: int = 0                         # 字形宽度
    src_h: int = 0                         # 字形高度

    # 装箱后填入的输出坐标
    dst_page: int = 0
    dst_x: int = 0
    dst_y: int = 0

    _width_override: int | None = None
    _height_override: int | None = None

    @property
    def width(self) -> int:
        if self._width_override is not None:
            return self._width_override
        if self.src_image is not None:
            return self.src_image.width
        return self.src_w

    @width.setter
    def width(self, v: int):
        self._width_override = v

    @property
    def height(self) -> int:
        if self._height_override is not None:
            return self._height_override
        if self.src_image is not None:
            return self.src_image.height
        return self.src_h

    @height.setter
    def height(self, v: int):
        self._height_override = v
