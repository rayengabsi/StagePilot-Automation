from __future__ import annotations

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"

_FONT_CACHE: dict[str, str] = {}


def resolve_font_path(family: str) -> str:
    """Resolve a font family name to a TTF file path."""
    if family in _FONT_CACHE:
        return _FONT_CACHE[family]
    ttf_name = _family_to_filename(family)
    ttf_path = FONT_DIR / ttf_name
    if ttf_path.exists():
        _FONT_CACHE[family] = str(ttf_path)
        return str(ttf_path)
    _FONT_CACHE[family] = family
    return family


def _family_to_filename(family: str) -> str:
    mapping = {
        "Helvetica": "Helvetica.ttf",
        "Times-Roman": "Times_New_Roman.ttf",
        "Courier": "Courier_New.ttf",
        "Arial": "Arial.ttf",
        "Calibri": "Calibri.ttf",
        "Georgia": "Georgia.ttf",
        "Verdana": "Verdana.ttf",
    }
    return mapping.get(family, f"{family}.ttf")
