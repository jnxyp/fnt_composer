import os
import yaml
from dataclasses import dataclass


@dataclass
class SourceConfig:
    type: str
    path: str
    size: int = 16
    color: tuple = (255, 255, 255)
    stroke_width: int = 0
    stroke_color: tuple = (0, 0, 0)
    y_adjust: int = 0
    xadvance_adjust: int = 0
    extra_line_height: int = 0
    supersample: int = 1
    hinting: str = "normal"
    bold: float = 0
    starsector_xadvance_compat: bool = False


@dataclass
class OutputConfig:
    name: str
    sources: list[SourceConfig]
    char_ids: set[int]
    out_dir: str = "output"
    dir: str = ""
    atlas_width: int = 512
    atlas_height: int = 512
    padding: int = 2
    on_missing: str = "skip"
    overrides: dict | None = None
    face: str | None = None
    size: int | None = None


@dataclass
class RunConfig:
    clean_output: bool
    outputs: list[OutputConfig]


def load(config_path: str) -> RunConfig:
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    defaults = raw.get("defaults", {})
    base_dir = os.path.dirname(os.path.abspath(config_path))
    clean_output = defaults.get("clean_output", True)
    outputs = []

    for out in raw["outputs"]:
        sources = _parse_sources(out["sources"], base_dir, defaults)
        _validate_source_order(sources, out["name"])

        char_ids = _expand_chars(out.get("chars", []), base_dir)

        sub = out.get("dir", "")
        out_dir = os.path.join(base_dir, "output", sub) if sub else os.path.join(base_dir, "output")

        merged_overrides = {**defaults.get("overrides", {}), **out.get("overrides", {})}
        outputs.append(
            OutputConfig(
                name=out["name"],
                sources=sources,
                char_ids=char_ids,
                out_dir=out_dir,
                dir=sub,
                atlas_width=out.get("atlas_width", defaults.get("atlas_width", 512)),
                atlas_height=out.get("atlas_height", defaults.get("atlas_height", 512)),
                padding=out.get("padding", defaults.get("padding", 2)),
                on_missing=out.get("on_missing", defaults.get("on_missing", "skip")),
                overrides=_parse_overrides(merged_overrides),
                face=out.get("face", defaults.get("face")),
                size=out.get("size", defaults.get("size")),
            )
        )

    return RunConfig(clean_output=clean_output, outputs=outputs)


def _parse_overrides(raw: dict) -> dict:
    result = {}
    for key, fields in raw.items():
        char_id = ord(key) if len(key) == 1 else int(key)
        result[char_id] = fields
    return result


def _parse_sources(raw_sources: list, base_dir: str, defaults: dict | None = None) -> list[SourceConfig]:
    if defaults is None:
        defaults = {}
    result = []
    for s in raw_sources:
        color = tuple(s["color"]) if "color" in s else (255, 255, 255)
        stroke_color = tuple(s["stroke_color"]) if "stroke_color" in s else (0, 0, 0)
        result.append(
            SourceConfig(
                type=s["type"],
                path=os.path.join(base_dir, s["path"]),
                size=s.get("size", 16),
                color=color,
                stroke_width=s.get("stroke_width", 0),
                stroke_color=stroke_color,
                y_adjust=s.get("y_adjust", 0),
                xadvance_adjust=s.get("xadvance_adjust", 0),
                extra_line_height=s.get("extra_line_height", 0),
                supersample=s.get("supersample", 1),
                hinting=s.get("hinting", "normal"),
                bold=s.get("bold", 0),
                starsector_xadvance_compat=s.get(
                    "starsector_xadvance_compat",
                    defaults.get("starsector_xadvance_compat", False),
                ),
            )
        )
    return result


def _validate_source_order(sources: list[SourceConfig], output_name: str):
    seen_ttf = False
    for s in sources:
        if s.type == "ttf":
            seen_ttf = True
        elif s.type == "fnt" and seen_ttf:
            raise ValueError(f"output '{output_name}': fnt source must come before all ttf sources")


def _expand_chars(chars_list: list, base_dir: str) -> set[int]:
    result = set()
    for item in chars_list:
        if isinstance(item, str):
            for ch in item:
                result.add(ord(ch))
        elif isinstance(item, dict):
            if "range" in item:
                start, end = item["range"]
                result.update(range(start, end + 1))
            elif "file" in item:
                file_path = os.path.join(base_dir, item["file"])
                with open(file_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.rstrip("\n")
                        if line.startswith("#"):
                            continue
                        for ch in line:
                            result.add(ord(ch))
    return result
