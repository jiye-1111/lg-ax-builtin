"""실사로 보기: 지금 해(채광)와 놓은 LG 제품을 이미지 AI에 줄 영어 문장으로 바꾼다.

해가 화면의 어느 쪽에서 드는지, 얼마나 낮은지, 빛 색이 어떤지는 여기서 계산해서 글로 준다
(AI에게 각도 계산을 맡기지 않는다). 제품 이름·색·재질은 카탈로그(LGE.COM) 글자 그대로.
"""
from __future__ import annotations

import math

_DIR = {"남": "south", "북": "north", "동": "east", "서": "west"}

# core.surface 의 겉면 종류 → 사진에서 보이는 모습
MATERIAL = {
    "stainless": "brushed stainless steel doors with a fine linear grain and crisp reflections",
    "stone": "matte stone-textured stainless steel doors with a soft, low sheen",
    "brushed": "metal door panels with a subtle brushed grain and soft metallic reflections",
    "coated": "smooth powder-coated steel doors with a soft satin sheen",
    "glass": "glass door panels with a smooth satin finish and clean, soft reflections of the room",
    "mist": "matte frosted 'mist' glass doors with a soft diffuse sheen and no mirror reflections",
}


def facing_words(label: str | None) -> str:
    """'남서향' → 'south-west-facing'"""
    if not label:
        return ""
    parts = [_DIR[ch] for ch in label.replace("향", "") if ch in _DIR]
    return "-".join(parts) + "-facing" if parts else ""


def material_words(kind: str | None) -> str:
    return MATERIAL.get(kind or "", "")


def sun_words(sun: dict | None, camera: dict | None, time: str | None, facing: str | None) -> str:
    """해 빛(sim.daylight.sun_light)과 카메라 → 한두 문장. 해 방향은 카메라 기준 앞·뒤·왼쪽·오른쪽으로 바꾼다."""
    if not sun:
        return ""
    face = facing_words(facing)
    where = f"This is a {face} home" if face else "This home"
    when = f" photographed at {time}" if time else ""
    head = f"{where}{when}."
    if not sun.get("up") or float(sun.get("intensity") or 0) <= 0.02:
        sky = "dusky blue sky light from the windows" if float(sun.get("sky") or 0) > 0.05 else "dark windows"
        return (f"{head} The sun is below the horizon: no direct sunlight and no sun patches. Light the room with "
                f"{sky} and warm ceiling lights, like a real evening photo.")
    side = ""
    if camera:
        fx, fz = camera["target"][0] - camera["pos"][0], camera["target"][2] - camera["pos"][2]
        n = math.hypot(fx, fz) or 1.0
        fx, fz = fx / n, fz / n
        rx, rz = -fz, fx  # 화면 오른쪽 (Y-up, three.js)
        dx, dz = sun["direction"][0], sun["direction"][2]
        m = math.hypot(dx, dz) or 1.0
        front, right = (dx * fx + dz * fz) / m, (dx * rx + dz * rz) / m
        if front > 0.6:
            side = "from beyond the room, shining toward the camera (soft backlight, shadows fall toward the viewer)"
        elif front < -0.6:
            side = "from behind the camera (shadows fall away from the viewer)"
        else:
            side = "from the right" if right > 0 else "from the left"
            side += " side of the picture" + (", slightly from behind the camera" if front < -0.2 else
                                              ", slightly from the far side" if front > 0.2 else "")
    alt = float(sun.get("altitude_deg") or 0)
    height = ("low, raking sunlight with long stretched shadows" if alt < 15 else
              "mid-height sunlight with medium-length shadows" if alt < 40 else
              "high sunlight with short shadows close to objects")
    k = float(sun.get("kelvin") or 6500)
    tone = ("warm golden-orange" if k < 3200 else "warm afternoon" if k < 5000 else "neutral white daylight")
    strength = "bright, crisp" if float(sun["intensity"]) > 0.6 else "gentle"
    return (f"{head} Sunlight enters through the windows {side}: {height}, {tone} colour, {strength} light. "
            "Draw the real sun patches on the floor and walls under the windows and matching soft shadows for "
            "every object, including the appliances.").replace("  ", " ")


def product_words(no: int, product, box, ref_no: int | None) -> str:
    """제품 한 줄. box = 화면에서 차지하는 자리 (0~1, x0 y0 x1 y1)."""
    cmf = product.cmf_options[0] if getattr(product, "cmf_options", None) else None
    color = getattr(cmf, "color", None)
    hexv = getattr(cmf, "hex_approx", None)
    from .surface import material_label, surface_kind

    kind = surface_kind(material_label(product), color)
    x0, y0, x1, y1 = (round(v * 100) for v in box)
    bits = [f"Appliance {no} (occupies x {x0}-{x1}% and y {y0}-{y1}% of the first image) is the real {product.name}"]
    if color:
        bits.append(f"in the colour '{color}'" + (f" (about {hexv})" if hexv else ""))
    look = material_words(kind)
    line = " ".join(bits) + "."
    if look:
        line += f" It has {look}."
    if ref_no:
        line += (f" Reference image {ref_no} is the official LG product photo of exactly this model: copy its real design onto it "
                 "(door and drawer split lines, handle or handle-less recess, control panel or display, LG logo position, "
                 "trim and gaps), keeping the same outline, size and position as in the first image.")
    else:
        line += " Keep its outline, size and position exactly as in the first image."
    return line
