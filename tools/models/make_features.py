"""제품 특징표(data/models/features.json)를 만든다.  uv run python tools/models/make_features.py

같은 모양으로 묶인 제품 한 줄마다 대표 모델명을 열쇠로 "어떤 틀로, 어떤 값으로 만들지"를 적는다.
값은 LGE.COM 제품 사진(정면)과 치수도를 보고 정한 것이다. 문 나눔 위치와 TV 받침 위치·높이는
제품 사진에서 잰 비율이다 (잰 날 2026-11-24).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

F = {}


def add(sku: str, arch: str, **params):
    F[sku] = {"arch": arch, "params": params}


# ---- 스탠드·벽걸이 에어컨
for s in ("FQ17GC1ED2", "FQ20GC2EA2", "FW16FC1EA2"):
    add(s, "ac_stand", kind="cool")
add("FQ17GW1HD2", "ac_stand", kind="winner")
add("FQ25GN9BE2", "ac_stand", kind="tower")
for s in ("SQ06FA1WDS", "SQ06GZ1WCS", "SQ06EZ1WBS", "SQ07GJ1WES", "SW16FK1WBS"):
    add(s, "ac_wall")
for s in ("SQ07GS9EES", "SW09GS1EES"):
    add(s, "ac_wall", strip=True)
# ---- 공기청정기
add("AS195DWWA", "purifier_round", booster=True)
add("AS206NSHA", "purifier_round", body="slats", cap=0.2, body_mat="#6F6659/s")
add("AS186LSAA", "purifier_panel")
add("AS356LSAA", "purifier_panel")
add("AS105GWJC", "purifier_round", top="grille", cap=0.1)
add("AS155GWDL", "aero_ring")
add("AS076MWHC", "purifier_round", top="grille", taper=0.1, cap=0.3)
add("FS065PSKA", "aero_tower")
add("AS065PWHA", "aero_table")
add("AS065CWHA", "aero_table", cat=True)
# ---- 주방
add("BEY3SRBLE", "cooktop")
add("DFE5BGE", "dishwasher_free")
add("MW20GDN", "microwave")
add("MW23FDI", "microwave", dials=1, door="same", panel=0.22, window=0.7)
add("MWE25HD", "microwave", panel=0.2)
add("MW25B", "microwave", dials=1)
add("MW22CA", "microwave", dials=1)
add("MW30EDN", "microwave")
add("MLJ28ERN", "microwave", dials=2, door="same", panel=0.22, window=0.7)
add("L023E1P42", "plant_tray")
# ---- 제습·가습
add("DQ205PSVA", "dehumidifier")
add("HW300BBB", "pot", kind="hw300")
add("HW500DAS", "pot", kind="hw500")
add("HY505RWLAH", "glow_tower")
# ---- 세탁·건조
add("RH10WTA", "drum", panel_mat="white", ring="black", door=0.76)
add("RG20WN", "drum", ring="black")
add("W1310EGN", "wash_tower")
add("F9WTB", "drum", panel_mat="white", ring="black", door=0.76, bulge=40)
add("F12WVAR", "drum", panel_mat="white", ring="chrome", door=0.78, bulge=45)
add("FY9WT", "drum", panel_mat="white", ring="black", door=0.76, bulge=40)
add("F17CTPR", "drum", panel_mat="white", ring="black", door=0.74)
add("FG21ENR", "drum", ring="black")
add("F8WVR", "drum", panel_mat="white", ring="chrome", door=0.74, bulge=40)
add("FX4WC", "mini_wash")
for s in ("TR13MV4", "TR15WV5", "T17DX3A", "T19MX8A", "T19OZ0", "TA25GZ9", "T21MX9A"):
    add(s, "top_loader")
add("FH11EA", "drum", ring="black", door=0.76, bulge=45)
add("FC2521KX6C", "drum", ring="black")
add("FH25LMTH", "drum_pedestal", ring="black")
# ---- 냉동고·김치냉장고·컨버터블 (문 한 장)
for s in ("Y321GB3S", "Z321GC3CS", "Z326GB7"):
    add(s, "fridge")
add("R321S", "fridge", style="classic", handles="bar", side="grey", display=[0, 0.5, 0.86])
add("DF165ME", "fridge", style="classic", handles="pocket", side="same")
add("A202S", "fridge", style="classic", side="grey", top_strip=0.05)
add("Z135MEE123", "chest_kimchi", seam=0.19, lids=1)
add("K225MB131", "chest_kimchi", seam=0.281, lids=2)
add("Z330MRRF21", "fridge", rows=[0.533, 0.732])
add("Z334SGS171", "fridge", rows=[0.56, 0.741])
add("Z403MEEF53", "fridge", rows=[0.515, 0.753], cols=[[0.5]])
add("Z509MPSF13", "fridge", rows=[0.533, 0.76], cols=[[0.5]])
add("Z490MPSF11", "fridge", rows=[0.535, 0.768], cols=[[0.5]])
add("Z495GBB271", "fridge", rows=[0.554, 0.779], cols=[[0.5]])
# ---- 냉장고
add("M516GBB012S", "fridge", rows=[0.55], cols=[[0.5], [0.5]])
add("F904ND79E", "fridge", rows=[0.557], cols=[[0.5], [0.5]], gap=0.014, glass=[1, 0.08], side="grey")
add("T873MEE111", "fridge", rows=[0.536], cols=[[0.5], [0.5]], gap=0.03)
add("M876GBB231", "fridge", rows=[0.552], cols=[[0.5], [0.5]])
for s in ("S834MEE111", "S656P003", "S836MQQ152"):
    add(s, "fridge", rows=[0.537], cols=[[0.432], [0.432]], gap=0.031)
add("B103S14", "fridge", style="classic", side="grey", handles="pocket")
add("B124S14", "fridge", rows=[0.307], gap=0.036, style="classic", side="grey")
add("DL195ME", "fridge", style="classic", handles="pocket", side="same")
add("B182W13", "fridge", rows=[0.339], gap=0.033, style="classic", side="same")
add("D215MHH13", "fridge", rows=[0.344], gap=0.034)
add("B245W22", "fridge", rows=[0.326], gap=0.029, style="classic", side="same")
add("D265MEE22", "fridge", rows=[0.304], gap=0.03)
add("M301S31", "fridge", rows=[0.552], gap=0.028, style="classic", side="grey")
add("Q342GBB133", "fridge", rows=[0.58], gap=0.026)
add("M344MB14", "fridge", rows=[0.582], gap=0.026, style="classic", side="grey")
add("M336DS123", "fridge", rows=[0.578], gap=0.025, style="classic", side="grey")
add("B312W31", "fridge", rows=[0.343], gap=0.03, style="classic", side="same")
add("B332S34", "fridge", rows=[0.325], gap=0.028, style="classic", side="grey")
add("Q405MEE133", "fridge", rows=[0.578], gap=0.026)
add("M402ND", "glass_cabinet", drawers=[0.565, 0.75], side="grey")
add("D463MRR33", "fridge", rows=[0.302], gap=0.026)
add("M451PS53", "fridge", rows=[0.615], gap=0.012, style="classic", handles="bar", side="grey", display=[0, 0.5, 0.8])
add("B502S53", "fridge", rows=[0.301], gap=0.037, style="classic", side="grey")
add("D604MPS52", "fridge", rows=[0.371], gap=0.027)
# ---- 스타일러·와인셀러
add("IY15CT80", "ironing")
add("SC3GBE52", "single_door_tall")
add("S3BOF", "single_door_tall")
add("W0772GB", "glass_cabinet")
add("W0082GLE", "glass_cabinet", shelves=3, frame=16)
add("W400ND", "glass_cabinet", drawers=[0.566, 0.751], side="grey")
# ---- 안마의자
add("MH20BR", "lounge_chair")
for s in ("MH65CC", "MH81CC", "MX91WR"):
    add(s, "massage_chair")
# ---- 청소기
add("MO972WA", "robot_vac", lidar=False)
add("B72WW", "robot_vac", square=True, lidar=False)
add("R585WKA1", "robot_vac")
add("N95TWU", "robot_vac", lidar=False)
add("B94AHB", "robot_vac")
add("A720TC", "stick_vac", style="a7")
add("AS520WA", "stick_vac", style="a5")
for s in ("C40SFHT", "C40SGY", "K83IGY", "C40WGY", "C33FNT"):
    add(s, "canister_vac")
# ---- 정수기
add("WD723RH", "purifier_ice")
add("WD520MH", "purifier_slim", head=0.36)
add("WD522MH", "purifier_slim", head=0.36)
add("WD523AWB", "purifier_slim", head=0.3)
add("WD525ACB", "purifier_slim", head=0.3)
add("WS511SH", "purifier_stand")
add("WS513SH", "purifier_stand")
add("WD121MCB", "purifier_slim", head=0.45)

# ---- TV: 제품 사진에서 잰 받침 (종류, 받침 높이 비율, 발 위치 또는 받침 폭)
TV = """75MRGB96BKA P .096 .24|86MRGB96BKA P .084 .21|100MRGB96BK P .046 .17|55MRGB86BKA P .055 .41|65MRGB83BEA F .076 .072
65MRGB86BKA P .061 .31|75MRGB83BEA F .071 .06|75MRGB86BKA P .053 .24|75MRGB85BMC F .055 .061|86MRGB83BEA F .063 .066
86MRGB85BMC F .048 .066|86MRGB86BKA P .057 .19|43NU850BENA F .094 .10|50NU850BXNA F .093 .105|55NU850BXNA W 0 0
55NU850BENA F .085 .107|98NU850BENB F .036 .097|55QNED70ABA F .075 .053|55QNED80BEA F .083 .07|65QNED91BKA P .084 .27
65QNED65BBA F .071 .10|65QNED70AEA F .069 .09|65QNED80BEA F .069 .09|65QNED75AEA W 0 0|65QNED86BKA P .061 .23
75QNED90KQA F .079 .09|75QNED80BEA F .068 .072|75QNED92AGA F .109 .071|75QNED81BMA P .066 .24|75QNED8MBEA F .068 .119
75QNED85AKA W 0 0|75QNED86BKA P .061 .23|75QNED70ABA W 0 0|85QNED80BEA F .057 .093|85QNED81BMA P .059 .21
85QNED91BKA P .068 .31|85QNED65BBA F .057 .093|85QNED92AGA F .109 .071|86QNED70AEA F .059 .11|86QNED65ABA W 0 0
86QNED75AEA F .063 .097|86QNED86BKA P .05 .20|98QNED89TKA W 0 0|43NANO80ANA F .094 .095|43NA1C90AKA F .112 .077
55NANO90AKA W 0 0|65NANO80AEA F .073 .11|75NANO80AEA F .071 .108|65QNED85AKS F .072 .108|65LX7BKNA F .077 .136
OLED42C5ENA F .072 .119|OLED48B5NNA F .101 .075|OLED48C5ENA P .093 .44|OLED55G6KNA P .071 .41|OLED55C6ENA P .087 .39
OLED55B5NNA F .088 .077|OLED55B6ENA F .093 .072|OLED65C5ENA W 0 0|OLED65M4KNA W 0 0|OLED65G6KNA P .063 .35
OLED65C6SNA P .075 .33|OLED65B2QNA P .055 .32|OLED65B5NNA F .075 .142|OLED65B6ENA F .079 .135|OLED77C6QNA P .066 .30
OLED77G6KNA P .077 .29|OLED77W6KNA W 0 0|OLED77B6NNA W 0 0|OLED77B6BNA F .068 .099|OLED77B5XNA F .066 .10
OLED83C6QNA P .053 .25|OLED83W6KNA W 0 0|OLED83G6KNA P .072 .27|OLED97G2KNA W 0 0|OLED97G6KNA L .272 .12
43UA7500ENA F .071 .09|43UR931C0NA F .093 .077|50UT8350KNA W 0 0|50UA7500KNA F .071 .09|50UT93RC0NA F .094 .095
55UT93RC0NA F .094 .078|65UQ931C0NA F .074 .11|86UT9300KNA W 0 0|86UT93RC0NA F .065 .11|86UQ9300KNA F .074 .11
32LB650BGNA W 0 0|32LB650BENA F .09 .11|43LB6500KNB F .09 .1"""
KIND = {"F": "feet", "P": "pedestal", "W": "wall", "L": "floor"}
for item in TV.replace("\n", "|").split("|"):
    sku, k, sf, v = item.split()
    if k == "F":
        add(sku, "tv", stand="feet", sf=float(sf), pos=float(v))
    elif k == "P":
        add(sku, "tv", stand="pedestal", sf=float(sf), sw=float(v))
    elif k == "L":
        add(sku, "tv", stand="floor", sf=float(sf), pos=float(v))
    else:
        add(sku, "tv", stand="wall")
F["65LX7BKNA"]["params"]["frame"] = "#B79C7A/s"       # 갤러리 TV: 나무색 액자 테두리
add("OLED77T6KNA", "tv_cabinet")

out = {
    "_note": "제품 한 줄(같은 모양)마다 대표 모델명 → 만드는 틀과 값. tools/models/make_features.py로 만든다. "
             "문 나눔·받침 위치는 LGE.COM 제품 사진에서 잰 비율 (2026-11-24).",
    "models": F,
}
p = ROOT / "data" / "models" / "features.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(F), "개 →", p)
