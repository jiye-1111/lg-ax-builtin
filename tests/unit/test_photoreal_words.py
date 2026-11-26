"""실사로 보기: 해·제품을 이미지 AI에 줄 글로 바꾸는 규칙 (계산은 코드가 한다)."""
from types import SimpleNamespace as NS

from core import photoreal_words as pw

# 카메라가 -z 쪽(앞)을 본다: 오른쪽은 +x
CAM = {"pos": [0, 1.6, 5], "target": [0, 1.4, 0], "fov": 50}


def sun(direction, alt, kelvin=6500, intensity=0.8, up=True):
    return {"direction": direction, "altitude_deg": alt, "kelvin": kelvin, "intensity": intensity, "up": up, "sky": 1}


def test_sun_behind_camera_low_and_warm():
    t = pw.sun_words(sun([0, 0.17, 0.98], 10, kelvin=2600, intensity=0.4), CAM, "18:10", "서향")
    assert "behind the camera" in t and "low" in t and "warm" in t and "18:10" in t and "west-facing" in t


def test_sun_from_the_right_high_noon():
    t = pw.sun_words(sun([0.6, 0.8, 0], 55), CAM, "12:30", "남향")
    assert "from the right" in t and "high" in t and "neutral" in t and "south-facing" in t


def test_sun_ahead_is_backlight_and_left_side():
    assert "toward the camera" in pw.sun_words(sun([0, 0.5, -0.86], 30), CAM, "09:00", None)
    assert "from the left" in pw.sun_words(sun([-0.9, 0.4, 0], 25), CAM, "08:00", None)


def test_sun_down_means_no_direct_sunlight():
    t = pw.sun_words(sun([0, -0.1, 1], -4, kelvin=2000, intensity=0, up=False), CAM, "18:40", "남향")
    assert "no direct sunlight" in t and "behind the camera" not in t


def product(name="LG 디오스 AI 오브제컬렉션 냉장고 Fit & Max (650L)", color="오브제컬렉션 베이지", material="글라스",
            hexv="#F1EEE9", category="refrigerator"):
    return NS(name=name, category=category, options={"door_material": material},
              cmf_options=[NS(color=color, material=material, hex_approx=hexv)])


def test_product_line_names_colour_material_and_reference():
    t = pw.product_words(1, product(), (0.40, 0.20, 0.55, 0.80), ref_no=2)
    assert "LG 디오스 AI 오브제컬렉션 냉장고" in t and "오브제컬렉션 베이지" in t and "#F1EEE9" in t
    assert "glass" in t and "image 2" in t and "40" in t and "55" in t


def test_product_line_without_photo_or_material_still_reads():
    t = pw.product_words(3, product(material=None, hexv=None), (0.1, 0.1, 0.2, 0.3), ref_no=None)
    assert "product photo" not in t and "None" not in t


def test_material_words_follow_surface_kinds():
    assert "stainless" in pw.material_words("stainless")
    assert "matte" in pw.material_words("mist")
    assert pw.material_words(None) == ""
