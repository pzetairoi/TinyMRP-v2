from datetime import datetime

from app.services.filenames import build_output_name


def test_build_output_name_windows_safe_and_short():
    now = datetime(2025, 1, 2, 3, 4)
    base = 'PN:123<>?* / REV "A" ' + ("X" * 120)
    name = build_output_name(base, "pdf", max_len=80, include_time=False, now=now)

    assert name.endswith(".pdf")
    assert "20250102" in name
    assert len(name) <= 80
    for ch in '<>:"/\\|?*':
        assert ch not in name
