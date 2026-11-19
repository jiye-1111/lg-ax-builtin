"""내부 표준 데이터 모델 (기획 §8). 모든 길이는 room.json에서 m, 카탈로그에서 mm."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Point2 = tuple[float, float]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- room.json (§8.2) ----------
class ScannedDims(_Strict):
    length_m: float
    height_m: float


class MeasuredDims(_Strict):
    """기사 실측값. null인 항목은 스캔값을 쓴다.

    depth_m: 확장 필드 — 벽 앞쪽 가용 깊이(벽면 ~ 맞은편 장애물)를 줄자로 잰 값.
    """

    length_m: Optional[float] = None
    height_m: Optional[float] = None
    depth_m: Optional[float] = None
    by: Optional[str] = None
    at: Optional[str] = None


class Wall(_Strict):
    wall_id: str
    start: Point2
    end: Point2
    thickness_m: Optional[float] = None
    scanned: ScannedDims
    measured: Optional[MeasuredDims] = None


class Opening(_Strict):
    opening_id: str
    type: Literal["door", "window", "opening"]
    wall_id: Optional[str]
    offset_m: float  # 벽 start에서 개구부 시작까지
    width_m: float
    height_m: float
    sill_m: float = 0.0  # 바닥에서 개구부 하단까지 (창문)


class BBox(_Strict):
    w: float
    h: float
    d: float


class RoomObject(_Strict):
    object_id: str
    category: str
    bbox_m: BBox
    position: tuple[float, float, float]  # (x, y=높이 중심, z) — 평면 좌표는 (x, z)
    yaw_rad: float = 0.0


class Room(_Strict):
    units: Literal["m"] = "m"
    source: str = "ugscan_roomplan_usdz"
    walls: list[Wall]
    openings: list[Opening] = Field(default_factory=list)
    objects: list[RoomObject] = Field(default_factory=list)

    def wall(self, wall_id: str) -> Wall:
        for w in self.walls:
            if w.wall_id == wall_id:
                return w
        raise KeyError(wall_id)


# ---------- zone (§8.3) ----------
class StyleTags(_Strict):
    palette: list[str] = Field(default_factory=list)  # "#RRGGBB"
    materials: list[str] = Field(default_factory=list)


class Zone(_Strict):
    zone_id: str
    purpose: str  # kitchen | living | ...
    polygon_m: list[Point2]
    wall_ids: list[str] = Field(default_factory=list)
    style_tags: StyleTags = Field(default_factory=StyleTags)


# ---------- catalog (§8.4) ----------
class Dims(_Strict):
    w: Optional[float] = None
    h: Optional[float] = None
    d: Optional[float] = None


class Clearance(_Strict):
    side: Optional[float] = None
    top: Optional[float] = None
    back: Optional[float] = None


class CmfOption(_Strict):
    color: str
    material: Optional[str] = None
    finish: Optional[str] = None
    hex_approx: Optional[str] = None


class Product(_Strict):
    sku: str
    name: str
    category: str
    zone_fit: list[str]
    install_type: Literal["built_in", "built_in_look", "freestanding"]
    product_dims_mm: Dims = Field(default_factory=Dims)
    required_space_mm: Dims = Field(default_factory=Dims)
    clearance_mm: Clearance = Field(default_factory=Clearance)
    door_swing_mm: Optional[float] = None
    cutout_mm: Dims = Field(default_factory=Dims)  # 상판 타공 치수 (쿡탑 등)
    spec_notes: list[str] = Field(default_factory=list)  # 출처 문구 요약 (어떤 값을 어디서 가져왔는지)
    cmf_options: list[CmfOption] = Field(default_factory=list)
    source_url: Optional[str]
    source_checked_at: Optional[str]
    model_3d: Optional[str] = None
    demo_only: bool = False  # True면 LGE.COM 값이 아닌 시연·테스트용 가상 데이터
