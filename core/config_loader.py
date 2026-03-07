import json
import os
from dataclasses import dataclass, field


@dataclass
class SourceConfig:
    type: str           # "fnt" | "ttf"
    path: str
    size: int = 16
    color: tuple = (255, 255, 255)
    stroke_width: int = 0
    stroke_color: tuple = (0, 0, 0)


@dataclass
class OutputConfig:
    name: str
    dir: str
    sources: list[SourceConfig]
    char_ids: set[int]
    atlas_width: int = 512
    atlas_height: int = 512
    padding: int = 2
    on_missing: str = "skip"


def load(config_path: str) -> list[OutputConfig]:
    with open(config_path, encoding="utf-8") as f:
        raw = json.load(f)

    defaults = raw.get("defaults", {})
    base_dir = os.path.dirname(os.path.abspath(config_path))
    outputs = []

    for out in raw["outputs"]:
        sources = _parse_sources(out["sources"], base_dir)
        _validate_source_order(sources, out["name"])

        char_ids = _expand_chars(out.get("chars", []), base_dir)

        outputs.append(OutputConfig(
            name=out["name"],
            dir=os.path.join(base_dir, out.get("dir", "output")),
            sources=sources,
            char_ids=char_ids,
            atlas_width=out.get("atlas_width", defaults.get("atlas_width", 512)),
            atlas_height=out.get("atlas_height", defaults.get("atlas_height", 512)),
            padding=out.get("padding", defaults.get("padding", 2)),
            on_missing=out.get("on_missing", defaults.get("on_missing", "skip")),
        ))

    return outputs


def _parse_sources(raw_sources: list, base_dir: str) -> list[SourceConfig]:
    result = []
    for s in raw_sources:
        color = tuple(s["color"]) if "color" in s else (255, 255, 255)
        stroke_color = tuple(s["stroke_color"]) if "stroke_color" in s else (0, 0, 0)
        result.append(SourceConfig(
            type=s["type"],
            path=os.path.join(base_dir, s["path"]),
            size=s.get("size", 16),
            color=color,
            stroke_width=s.get("stroke_width", 0),
            stroke_color=stroke_color,
        ))
    return result


def _validate_source_order(sources: list[SourceConfig], output_name: str):
    seen_ttf = False
    for s in sources:
        if s.type == "ttf":
            seen_ttf = True
        elif s.type == "fnt" and seen_ttf:
            raise ValueError(
                f"output '{output_name}': fnt source must come before all ttf sources"
            )


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
