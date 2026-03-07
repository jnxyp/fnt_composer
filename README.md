# fnt_composer

> 重要提示：本项目由 LLM vibe coding 生成，代码未经严格审查，请在使用时仔细检查和测试。

fnt_composer 是一个 BMFont 字库合成工具，用于从 TTF 字体和已有 `.fnt` 文件中提取指定字形，合成新的 BMFont 格式（`.fnt` + `.png`）字库文件。

本工具目前被用于[远行星号远星汉化组](https://github.com/TruthOriginem/Starsector-Localization-CN)为游戏《远行星号》（Starsector）制作中文字库。

通过 `config.yml` 驱动，支持多套输出、多来源混合、优先级覆盖。

## 目录结构

```
fnt_composer/
├── config.yml
├── main.py
├── core/
│   ├── config_loader.py   # 读取和验证配置
│   ├── glyph.py           # Glyph 数据模型
│   ├── fnt_parser.py      # 解析 .fnt + .png，提取字形
│   ├── ttf_extractor.py   # 从 TTF 渲染字形
│   ├── glyph_merger.py    # 多来源合并、优先级
│   ├── atlas_packer.py    # 矩形装箱，生成纹理图集
│   └── fnt_writer.py      # 输出 .fnt + .png
├── source/                # 输入字体文件（.fnt / .ttf）
├── charset/               # 字符集文件
└── output/                # 生成结果
```

## 依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py              # 使用默认 config.yml
python main.py my.yml       # 使用指定配置文件
```

输出写入 `output/`，每个 output 生成 `{name}.fnt` 和 `{name}_0.png`（字形过多时自动分多张）。

---

## 最小示例

从一个 TTF 文件渲染指定字符集：

```yaml
outputs:
  - name: my_font
    atlas_width: 2048
    atlas_height: -1
    sources:
      - type: ttf
        path: source/MyFont.ttf
        size: 21
        supersample: 4
        hinting: light
    chars:
      - "你好世界ABCabc123"
```

---

## 配置参考（config.yml）

### 顶层结构

```yaml
defaults:   # 全局默认值，各字段可被 output 或 source 级别覆盖
  ...

outputs:    # 输出列表，每项生成一套 .fnt + .png
  - ...
```

---

### defaults

```yaml
defaults:
  clean_output: true              # 运行前清空各输出目录
  atlas_width: 512                # 图集宽度（px）
  atlas_height: 512               # 图集高度（px，-1 表示高度自动扩展）
  padding: 2                      # 字形间距（px）
  on_missing: skip                # 缺失字符处理：skip（跳过并警告）| error（报错）
  starsector_xadvance_compat: false  # ttf 来源默认值：xoffset>0 时 xadvance -= xoffset
  overrides:                      # 对所有 output 生效的字符属性覆盖
    "{": { xadvance: 0, width: 0, height: 0 }
    # key 可以是单个字符，或十进制码位（如 33258）
    # 可覆盖字段：x, y, xoffset, yoffset, xadvance, width, height
```

---

### outputs 条目

```yaml
outputs:
  - name: my_font               # [必填] 输出文件名（不含扩展名）
    dir: subfolder              # 输出子目录，结果写入 output/<dir>/（默认直接写 output/）
    atlas_width: 2048           # 覆盖 defaults.atlas_width
    atlas_height: -1            # 覆盖 defaults.atlas_height
    padding: 2                  # 覆盖 defaults.padding
    on_missing: skip            # 覆盖 defaults.on_missing
    chars:                      # [必填] 字符集，可混合以下三种写法
      - "ABC123"                      # 直接内联字符串
      - { file: charset/chars.txt }   # 文件（UTF-8，每行每字，# 开头行为注释）
      - { range: [0x4E00, 0x9FFF] }   # Unicode 码位范围（含首尾）
    overrides:                  # 覆盖特定字符属性（合并自 defaults.overrides）
      "字": { xadvance: 10 }
    sources:                    # [必填] 字形来源列表，fnt 必须在 ttf 之前
      - ...
```

---

### sources — fnt 来源

从已有 `.fnt` 文件复制字形，像素完全保真，不做重采样。

```yaml
- type: fnt
  path: source/font.fnt       # [必填] .fnt 文件路径（相对项目根目录）
  yoffset_adjust: 0           # 整体 yoffset 调整量（正数下移，负数上移）
```

---

### sources — ttf 来源

从 TTF 文件渲染字形，填补 fnt 来源未覆盖的字符。

```yaml
- type: ttf
  path: source/font.ttf       # [必填] TTF 文件路径
  size: 16                    # [必填] 渲染字号（px）
  color: [255, 255, 255]      # 字形颜色 RGB（默认白色）
  stroke_width: 0             # 描边宽度（px，0=不描边）
  stroke_color: [0, 0, 0]     # 描边颜色 RGB
  yoffset_adjust: 0           # 整体 yoffset 调整量
  supersample: 1              # 超采样倍数（1/2/4/8），越大质量越高但越慢
  hinting: normal             # hinting 模式：normal | light（推荐）| none
  bold: 0                     # alpha 膨胀加粗（目标尺寸像素数，0=不加粗，支持小数）
  starsector_xadvance_compat: false  # xoffset>0 时 xadvance -= xoffset（兼容 Starsector 推进宽度计算）
```

#### starsector_xadvance_compat 说明

Starsector 等游戏引擎在计算字符位置时，实际推进量为 `xadvance - xoffset`（而非标准 BMFont 的 `xadvance`）。启用此选项后，脚本会在写出前自动补偿：当 `xoffset > 0` 时，将 `xadvance` 减去 `xoffset`，使渲染结果符合该引擎的预期。

---

## 完整示例

```yaml
defaults:
  atlas_width: 512
  atlas_height: 512
  padding: 2
  on_missing: skip
  clean_output: true
  starsector_xadvance_compat: true
  overrides:
    "{": { xadvance: 0, width: 0, height: 0 }
    "}": { xadvance: 0, width: 0, height: 0 }

outputs:
  # 用 TTF 补全 fnt 缺失的汉字，高质量超采样
  - name: my_font_21
    dir: output_set
    atlas_width: 2048
    atlas_height: -1
    sources:
      - type: fnt
        path: source/my_font_21.fnt
      - type: ttf
        path: source/MyFont.ttf
        size: 21
        color: [255, 255, 255]
        yoffset_adjust: -1
        supersample: 4
        hinting: light
        bold: 0.3
    chars:
      - { file: charset/chars.txt }

  # 纯 TTF 渲染，带描边
  - name: my_font_outlined
    atlas_width: 1024
    atlas_height: -1
    sources:
      - type: ttf
        path: source/MyFont.ttf
        size: 24
        color: [255, 255, 255]
        stroke_width: 2
        stroke_color: [0, 0, 0]
        supersample: 4
        hinting: light
    chars:
      - "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
      - { file: charset/chars.txt }
    overrides:
      " ": { xadvance: 8, width: 0, height: 0 }
```

---

## 处理流程

```
读取 config.yml
  └─ 对每个 output：
       1. 展开 chars → char_id 集合
       2. 按 sources 顺序：
            fnt 来源 → 解析 .fnt，整张 page 复制到图集
            ttf 来源 → 渲染缺失字符
       3. 合并字形（fnt 优先，先列出的来源优先）
       4. 装箱：fnt page 整块保留，ttf 字形用 Shelf 算法填入剩余空间
       5. 应用 overrides
       6. 写出 .fnt + .png
```

### 来源优先级

`sources` 列表中靠前的来源优先级更高。同一字符出现在多个来源时，取第一个。fnt 来源必须全部列在 ttf 来源之前。
