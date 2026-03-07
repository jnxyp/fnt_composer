# fnt_composer 开发计划

## 项目目标

从 TTF 文件和已有 .fnt 文件中提取指定字形，合成新的 BMFont 格式（.fnt + .png）。
通过 `config.json` 驱动，支持多套输出、多来源混合、优先级覆盖。

---

## 目录结构

```
fnt_composer/
├── config.json
├── main.py
├── core/
│   ├── config_loader.py     # 读取和验证 config.json
│   ├── glyph.py             # Glyph 数据模型
│   ├── fnt_parser.py        # 解析 .fnt + .png，提取字形
│   ├── ttf_extractor.py     # 从 TTF 渲染字形
│   ├── glyph_merger.py      # 多来源合并、去重、优先级
│   ├── atlas_packer.py      # 矩形装箱，生成纹理图集
│   └── fnt_writer.py        # 输出 .fnt + .png
└── source/                  # 输入字体文件
```

---

## 数据模型

```python
@dataclass
class Glyph:
    char_id: int        # Unicode 码位
    image: Image        # RGBA 位图（裁剪好的字形）
    xoffset: int        # 绘制水平偏移
    yoffset: int        # 绘制垂直偏移
    xadvance: int       # 光标推进量
```

---

## 模块规格

### config_loader.py

- 读取 `config.json`
- 将 `defaults` 合并到每个 output（output 字段优先）
- **校验 sources 顺序**：所有 `type: fnt` 必须出现在 `type: ttf` 之前，否则报错
- 展开 `chars`：
  - 字符串 → 逐字符收集 char_id
  - `{"range": [start, end]}` → 闭区间 char_id 列表
  - `{"file": "path"}` → 读文件，每行视为字符串，`#` 开头忽略
  - 去重，输出 `set[int]`
- 返回结构化的 output 列表，供后续模块消费

### fnt_parser.py

输入：`.fnt` 文件路径
输出：`dict[int, Glyph]`（包含该 fnt 所有字形）、原始 page 图像列表

- 解析 `info` / `common` / `page` / `char` 行
- 支持多 page（多张纹理）
- **不裁剪字形**：保留每个字形在原 page 中的坐标（x/y/width/height/page），供 atlas_packer 直接整块复制
- kerning 数据单独保存，供 fnt_writer 使用

### ttf_extractor.py

输入：TTF 路径、渲染 size、颜色、可选描边参数、char_id 集合
输出：`dict[int, Glyph]`（成功渲染的字形）

- 使用 `Pillow` + `freetype-py` 渲染字形
- 通过 freetype metrics 计算 xoffset / yoffset / xadvance
- 对 char_id 集合中 TTF 不包含的字符跳过并警告
- 描边：先渲染轮廓层（stroke_color），再叠加字形层（color）

### glyph_merger.py

输入：按优先级排列的 `list[dict[int, Glyph]]`
输出：`dict[int, Glyph]`

- 遍历 char_id 集合，取第一个有该字符的来源
- 来源顺序即 config `sources` 列表顺序
- 缺字处理：`on_missing=skip` 则跳过并打印警告；`error` 则抛出异常

### atlas_packer.py

输入：
- `fnt_glyphs: dict[int, Glyph]`（来自 fnt 来源，含原始 page 坐标）
- `fnt_pages: list[Image]`（fnt 的原始纹理图）
- `ttf_glyphs: dict[int, Glyph]`（来自 ttf 来源，含渲染好的位图）
- atlas 宽高、padding

输出：
- 更新所有 Glyph 的 `x, y`（在新图集中的坐标）
- 合成好的 `list[Image]`（可能多张）

**两阶段装箱：**

1. **fnt 阶段**：将 fnt 的所有原始 page 整张复制到输出图集开头，字形坐标按 page 偏移量平移，像素 100% 保真，不做任何重采样
2. **ttf 阶段**：对 ttf 渲染的字形用 Shelf 算法继续装箱，填入 fnt 占用后的剩余空间；放不下时新开一张图

其他规则：
- fnt page 尺寸若超过 atlas 宽高则报错（要求 atlas 不小于 fnt 原始纹理）
- ttf 字形四周留 `padding` 像素（fnt 字形使用原始 padding，不额外处理）

### fnt_writer.py

输入：output 配置、`dict[int, Glyph]`（含坐标）、图集列表、kerning 数据
输出：`{name}.fnt` + `{name}_0.png`（可能多张）

- 按 BMFont 文本格式写 `info / common / page / chars / kernings`
- `info` 行的 face、size 从第一个有效来源继承（fnt 来源用原始值，ttf 来源用配置值）
- `common` 的 lineHeight / base 从来源继承或自动计算
- 保存 .png 到 `dir` 目录

---

## 主流程（main.py）

```
读取 config.json
  └─ 对每个 output：
       1. config_loader  → 展开 char_id 集合
       2. 对每个 source：
            fnt_parser / ttf_extractor → dict[int, Glyph]
       3. glyph_merger   → 合并字形
       4. atlas_packer   → 装箱 + 生成图集
       5. fnt_writer     → 写 .fnt + .png
       6. 打印统计（成功 N 字符，跳过 M 字符，生成 K 张纹理）
```

---

## 依赖

| 库 | 用途 |
|---|---|
| `Pillow` | 图像处理、TTF 渲染（ImageFont） |
| `freetype-py` | TTF 精确 metrics（xoffset/yoffset/advance） |

---

## 开发顺序

1. `glyph.py` — 定义数据结构
2. `config_loader.py` — 读取配置，展开字符集
3. `fnt_parser.py` — 解析现有 .fnt，可独立测试
4. `ttf_extractor.py` — TTF 渲染，可独立测试
5. `glyph_merger.py` — 合并逻辑
6. `atlas_packer.py` — 装箱算法
7. `fnt_writer.py` — 输出
8. `main.py` — 串联主流程

---

## 已知边界情况

- TTF 中某字符不存在（字形缺失）→ on_missing 策略处理
- 单张 512×512 放不下所有字形 → 自动多 page
- fnt 来源中 .png 与 .fnt 不同目录 → 按 .fnt 文件路径推断 .png 路径
- 字符在多来源均有 → 取第一个（优先级靠前）
- CJK 字形尺寸远大于 Latin → 装箱时混排，Shelf 算法自动处理
