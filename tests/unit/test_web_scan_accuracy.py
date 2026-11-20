"""웹: 스캔 오차를 화면에 반영 (docs/research/lidar-error-correction.md)."""
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "apps" / "web"


def test_scan_tips_on_home_and_technician_pages():
    s = (WEB / "js" / "pages.js").read_text(encoding="utf-8")
    assert s.count("${SCAN_TIPS}") == 2 and "1~1.5 m" in s


def test_inspector_has_optional_spot_measure_and_needs_check_label():
    s = (WEB / "js" / "remodel.js").read_text(encoding="utf-8")
    assert "/measured`" in s and 'data-spot="${k}"' in s
    assert "확인 필요" in s and "needsMeasure" in s
