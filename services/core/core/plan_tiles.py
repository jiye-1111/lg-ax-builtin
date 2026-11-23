"""도면을 네 조각으로 나눠 크게 키워 다시 읽는다. 한 장으로 볼 때 놓치는 창·문·꺾인 벽을 찾으려고.

조각 좌표를 집 좌표로 바꾸려면 그림에서 집 테두리가 어디인지 알아야 한다. 이것은 AI가 아니라
그림에서 두껍고 긴 선(벽)을 찾아 코드가 정한다. 읽은 것을 합치는 규칙은 worker/plan_merge.py.
"""
from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from worker.plan_merge import TileRead, merge_tiles
from worker.plan_room import PlanRead

from .plan_read import _ask, _image_parts

log = logging.getLogger(__name__)
DARK = 128             # 이보다 어두운 픽셀이 선
LONG_RUN = 0.12        # 그림 폭(높이)의 이만큼 넘게 이어진 선만 벽으로 본다 (글자·가구 제외)
THICK_PX = 3           # 이만큼 넘게 겹쳐 있어야 벽 (얇은 치수선 제외)
SHAPE_DRIFT = 0.15     # 그림 테두리와 읽은 집의 가로세로 비가 이만큼 넘게 다르면 조각 읽기를 하지 않는다
TILE_SIZE, TILE_STEP, MARGIN = 0.6, 0.4, 0.05  # 집 테두리 기준 조각 크기·간격·여백
MIN_SIDE = 768

TILE_SYSTEM = """집 평면도의 한 부분을 잘라 크게 키운 그림을 보고, 그 안에 보이는 창, 문, 벽을 픽셀 좌표로 옮겨 적는다.

좌표
- 단위는 이 조각 그림의 픽셀. 왼쪽 위가 (0, 0), x는 오른쪽, y는 아래쪽으로 커진다.

적을 것
- window: 벽 위에 가는 겹줄이나 끊긴 칸으로 그려진 창. 창마다 벽을 따라 양 끝점.
- door: 문짝과 열리는 호가 있는 문. 문이 달린 벽 위에서 문틀의 양 끝점.
- sliding_door: 바닥까지 내려오는 큰 유리문.
- walls: 두꺼운 선(속이 빗금이거나 칠해진 것 포함)의 가운데 선 양 끝점. 꺾이는 곳마다 나누고, 비스듬한 벽도 적는다. 집 바깥을 두르는 벽은 exterior=true.

적지 않을 것
- 가구, 글자, 치수선, 점 격자, 계단.
- 조각 가장자리에 걸려 반 넘게 잘린 것."""


def _thicken(mask: np.ndarray, r: int) -> np.ndarray:
    """선을 r px씩 두껍게: 빗금으로 채운 벽이 꽉 찬 띠가 된다"""
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def _bands(mask: np.ndarray, min_run: float, min_thick: int) -> list[tuple[int, int]]:
    """행마다 가장 길게 이어진 선이 min_run 넘는 행들을, 붙어 있는 띠로 묶는다"""
    rows = []
    for r in mask:
        d = np.diff(np.concatenate(([0], r.astype(np.int8), [0])))
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        rows.append(bool(len(starts)) and (ends - starts).max() >= min_run)
    out, start = [], None
    for i, on in enumerate([*rows, False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            if i - start >= min_thick:
                out.append((start, i - 1))
            start = None
    return out


def house_box(im: Image.Image) -> tuple[int, int, int, int] | None:
    """그림에서 두껍고 긴 가로·세로 선(벽)이 차지하는 테두리 (x0, y0, x1, y1) px. 없으면 None"""
    g = np.asarray(im.convert("L")) < DARK
    h, w = g.shape
    r = max(2, round(min(w, h) / 400))  # 그림이 크면 빗금 사이도 넓다
    g = _thicken(g, r)
    thick = 2 * r + THICK_PX  # 두껍게 한 만큼 빼고도 THICK_PX 넘는 띠만 (치수선은 두껍게 해도 2r+1)
    rows, cols = _bands(g, LONG_RUN * w, thick), _bands(g.T, LONG_RUN * h, thick)
    if len(rows) < 2 or len(cols) < 2:
        return None
    return cols[0][0] + r, rows[0][0] + r, cols[-1][1] - r, rows[-1][1] - r


def tiles_for(im: Image.Image, box) -> list[tuple[bytes, tuple[float, float, float]]]:
    """2×2로 겹치게 자른 조각들: [(PNG, (그림 속 원점 x, y, 배율)), ...]"""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    x0, y0, bw, bh = x0 - bw * MARGIN, y0 - bh * MARGIN, bw * (1 + 2 * MARGIN), bh * (1 + 2 * MARGIN)
    out = []
    for fy in (0.0, TILE_STEP):
        for fx in (0.0, TILE_STEP):
            l, t = max(0, int(x0 + bw * fx)), max(0, int(y0 + bh * fy))
            r, b = min(im.width, int(x0 + bw * (fx + TILE_SIZE))), min(im.height, int(y0 + bh * (fy + TILE_SIZE)))
            crop = im.crop((l, t, r, b)).convert("RGB")
            k = max(1.0, MIN_SIDE / min(crop.size))
            crop = crop.resize((round(crop.width * k), round(crop.height * k)), Image.LANCZOS)
            buf = io.BytesIO()
            crop.save(buf, "PNG")
            out.append((buf.getvalue(), (l, t, k)))
    return out


def _same_shape(plan: PlanRead, box) -> bool:
    xs = [v for w in plan.walls for v in (w.x1, w.x2)]
    ys = [v for w in plan.walls for v in (w.y1, w.y2)]
    mw, mh, pw, ph = max(xs) - min(xs), max(ys) - min(ys), box[2] - box[0], box[3] - box[1]
    return min(mw, mh, pw, ph) > 0 and abs((pw / ph) / (mw / mh) - 1) <= SHAPE_DRIFT


def _read_tile(client, provider: str, png: bytes, size) -> TileRead | None:
    parts = _image_parts(png, "image/png", "tile.png", provider)
    parts[-1] = {"type": "text", "text": f"이 조각 그림은 가로 {size[0]} px, 세로 {size[1]} px 이다. 보이는 창, 문, 벽을 옮겨 적어 주세요."}
    try:
        return _ask(client, provider, TILE_SYSTEM, parts, TileRead)
    except Exception as e:  # noqa: BLE001 - 조각 읽기는 덤이다: 실패한 조각은 빼고 합친다
        log.warning("도면 조각 읽기 실패 (%s): %s", provider, e)
        return None


def read_tiles(data: bytes, plan: PlanRead, client, provider: str) -> PlanRead:
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001 - 그림이 아니면 처음 읽은 것 그대로
        return plan
    box = house_box(im)
    if box is None or not _same_shape(plan, box):
        log.info("도면 조각 읽기 건너뜀: 그림에서 집 테두리를 못 찾았거나 읽은 집과 모양이 달라요 (%s)", box)
        return plan
    tiles = tiles_for(im, box)
    with ThreadPoolExecutor(len(tiles)) as pool:
        reads = list(pool.map(lambda t: _read_tile(client, provider, t[0], Image.open(io.BytesIO(t[0])).size), tiles))
    merged = merge_tiles(plan, [(r, o) for r, (_, o) in zip(reads, tiles)], box)
    log.info("도면 조각 읽기: 벽 %d→%d, 창·문 %d→%d", len(plan.walls), len(merged.walls), len(plan.openings), len(merged.openings))
    return merged
