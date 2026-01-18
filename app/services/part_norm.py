import re
from typing import Optional

_REV_BLANKS = {"", "n/a", "na", "none", "null", "nan", "0", "false"}


def clean_rev(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in _REV_BLANKS:
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    return text.strip()


def clean_rev_or_none(value: object | None) -> Optional[str]:
    if value is None:
        return None
    return clean_rev(value)


def clean_pn(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)


def clean_qty(value: object, default: float = 1.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except Exception:
        return default
