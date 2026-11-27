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


def rest_words(on: int | str | None) -> str:
    """무엇 위에 있는지. on = 그 아래 물건 번호, 'wall'(벽에 건 것), 'below'(화면 밖 가구 위), None(바닥)"""
    if on == "wall":
        return "It hangs on the wall."
    if on == "below":
        return "It sits on top of the furniture under it, not in the air."
    if on:
        return f"It sits on top of object {on}, not in the air."
    return "It stands on the floor."


def product_words(no: int, product, box, ref_no: int | None, on: int | str | None = None) -> str:
    """제품 한 줄. box = 화면에서 차지하는 자리 (0~1, x0 y0 x1 y1)."""
    cmf = product.cmf_options[0] if getattr(product, "cmf_options", None) else None
    color = getattr(cmf, "color", None)
    hexv = getattr(cmf, "hex_approx", None)
    from .surface import material_label, surface_kind

    kind = surface_kind(material_label(product), color)
    x0, y0, x1, y1 = (round(v * 100) for v in box)
    bits = [f"Object {no} (x {x0}-{x1}%, y {y0}-{y1}% of the first image) is an LG appliance, the real {product.name}"]
    if color:
        bits.append(f"in the colour '{color}'" + (f" (about {hexv})" if hexv else ""))
    look = material_words(kind)
    line = " ".join(bits) + ". " + rest_words(on)
    if look:
        line += f" It has {look}."
    if ref_no:
        line += (f" Reference image {ref_no} is the official LG product photo of exactly this model: copy its real design onto it "
                 "(door and drawer split lines, handle or handle-less recess, control panel or display, LG logo position, "
                 "trim and gaps), keeping the same outline, size and position as in the first image.")
    else:
        line += " Keep its outline, size and position exactly as in the first image."
    return line


# ---- 장면 목록: 화면에 보이는 물건을 하나씩 (이름·화면 자리·무엇 위에 있는지). 목록 밖은 빈 바닥 ----
# 꾸미기 가구(decor:) → 사진에서 그 물건을 부르는 말
DECOR_WORDS = {
    "sofa": "a sofa", "table": "a dining table", "chair": "a chair", "islandtable": "a kitchen island table",
    "coffee": "a low coffee table", "bed": "a bed", "desk": "a desk", "wardrobe": "a tall wardrobe",
    "tallcab": "a tall kitchen cabinet", "storage": "a storage cabinet", "shelf": "an open shelf", "dresser": "a chest of drawers",
    "sink": "a kitchen sink cabinet", "basecab": "a kitchen base cabinet with a countertop", "island": "a kitchen island",
    "hood": "a wall-mounted cooker hood", "islandhood": "a ceiling-hung island cooker hood", "tvstand": "a low TV stand",
    "rug": "a flat rug", "lamp": "a floor lamp", "plant": "a potted plant", "partition": "a room partition",
    # 빌트인 주방 맞춤장 (안에 넣은 LG 가전은 따로 제품으로 들어간다)
    "cab_fridge": "a built-in tall housing cabinet with side panels and an upper cabinet around the refrigerator",
    "cab_dishwasher": "a countertop span with fixing side panels over a built-in dishwasher bay",
    "cab_sink": "a kitchen sink base cabinet with a sink bowl and faucet", "cab_drawer": "a kitchen drawer base cabinet with a countertop",
    "cab_wall": "a wall-hung kitchen upper cabinet", "cab_glass_wall": "a wall-hung glass-door kitchen upper cabinet with visible shelves",
    "cab_pantry": "a tall kitchen pantry cabinet", "cab_counter": "a continuous kitchen countertop",
    "cab_filler": "a narrow filler panel", "cab_end_panel": "a cabinet end panel",
}
# 벽·문·창은 방 모양이라 목록에 넣지 않는다 (그대로 두라고 따로 말한다)
STRUCTURE = frozenset({"wall", "door", "window", "glassdoor"})
# 스캔한 가구 (RoomPlan 종류) → 사진에서 부르는 말
SCAN_WORDS = {
    "storage": "a storage cabinet", "chair": "a chair", "table": "a table", "sofa": "a sofa", "bed": "a bed",
    "television": "a TV", "refrigerator": "a refrigerator", "stove": "a stove", "oven": "an oven", "sink": "a sink",
    "dishwasher": "a dishwasher", "washerDryer": "a washing machine", "toilet": "a toilet", "bathtub": "a bathtub",
    "fireplace": "a fireplace", "stairs": "stairs",
}


def thing_words(no: int, what: str, box, on: int | str | None = None) -> str:
    """물건 한 줄. on = 그 아래 물건 번호, 'wall'(벽에 건 것), None(바닥)"""
    x0, y0, x1, y1 = (round(v * 100) for v in box)
    return f"Object {no} (x {x0}-{x1}%, y {y0}-{y1}% of the first image): {what}. {rest_words(on)}"


def scene_words(count: int) -> str:
    return (f"OBJECTS: the room holds exactly {count} objects, listed below. Nothing else exists in the room. "
            "Every part of the floor that is empty in the first image stays empty: draw only bare floor there "
            "(the same goes for empty walls and countertops). Each object keeps its own type and stays where it is.")


_FIX = {
    "added": "Remove {what} ({where}): it is not in the room. Draw bare floor or wall there.",
    "missing": "Put back {what} ({where}) exactly as it is in the first image.",
    "duplicated": "Draw {what} ({where}) only once, in its place from the first image. Remove the extra copy.",
    "changed": "{what} ({where}) must keep the same type and shape as in the first image.",
    "moved": "{what} ({where}) must stay exactly where it is in the first image.",
    "floating": "{what} ({where}) must rest on the floor or on the object under it, as in the first image, never in the air.",
    "overlap": "{what} ({where}) must not overlap or merge with other objects: keep them apart as in the first image.",
}


def fix_words(problems: list[dict]) -> str:
    """앞서 그린 그림에서 틀린 것 → 고치라는 문장 (다시 그릴 때 프롬프트 끝에)"""
    lines = [_FIX[p["kind"]].format(what=p["what"], where=p["where"]) for p in problems if p.get("kind") in _FIX]
    if not lines:
        return ""
    lines = [s[0].upper() + s[1:] for s in lines]
    return "The previous attempt got these wrong. Fix them:\n- " + "\n- ".join(lines)
