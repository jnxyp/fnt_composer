from .glyph import Glyph


def merge(
    char_ids: set[int],
    sources: list[dict[int, Glyph]],
    on_missing: str = "skip",
) -> dict[int, Glyph]:
    """
    按优先级合并多个来源的字形。

    sources 列表顺序即优先级，靠前优先。
    on_missing="skip"  : 所有来源都没有时跳过并打印警告
    on_missing="error" : 所有来源都没有时抛出 KeyError
    """
    result: dict[int, Glyph] = {}
    missing = []

    for char_id in sorted(char_ids):
        for source in sources:
            if char_id in source:
                result[char_id] = source[char_id]
                break
        else:
            missing.append(char_id)

    if missing:
        msg = f"{len(missing)} characters not found in any source"
        if on_missing == "error":
            chars = ", ".join(f"U+{c:04X}" for c in missing[:10])
            raise KeyError(f"{msg}: {chars}{'...' if len(missing) > 10 else ''}")
        else:
            print(f"[warning] {msg} (skipped)")

    return result
