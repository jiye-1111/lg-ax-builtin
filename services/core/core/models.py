"""내부 표준 데이터 모델 (기획 §8). 모든 길이는 room.json에서 m, 카탈로그에서 mm."""
from __future__ import annotations

from typing import Literal, Optional, Union

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
    side: Optional[float] = None        # 양옆 각각
    side_total: Optional[float] = None  # 한쪽에만 두어도 되는 옆 여유 (정수기: "옆 쪽으로 100mm"). 폭에 한 번만 더한다
    top: Optional[float] = None
    back: Optional[float] = None


class CmfOption(_Strict):
    color: Optional[str] = None  # LGE.COM 스펙 표에 색상 표기가 없으면 null
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
    # LGE.COM 스펙 표의 옵션 값 (종류·도어 수·용량·화면 크기 등). 단계별 필터에 쓴다. 표에 없으면 키를 넣지 않는다.
    options: dict[str, Union[str, float]] = Field(default_factory=dict)
    cmf_options: list[CmfOption] = Field(default_factory=list)
    source_url: Optional[str]
    source_checked_at: Optional[str]
    # LGE.COM 제품 페이지의 판매 상태: ACTIVE(판매중) · SOLD_OUT(일시품절) · NOT_FOR_SALE(비매품) · DISCONTINUED(단종). 확인 못 했으면 null
    sale_status: Optional[Literal["ACTIVE", "SOLD_OUT", "NOT_FOR_SALE", "DISCONTINUED"]] = None
    sale_checked_at: Optional[str] = None
    # LGE.COM 제품 페이지의 판매가(원, 회원 로그인 전 화면에 보이는 값). 못 읽었으면 null. 자주 바뀌니 확인한 날을 같이 적는다
    price_krw: Optional[int] = None
    price_checked_at: Optional[str] = None
    # LGE.COM 스펙 표의 에너지 소비효율등급(1~5). 등급이 없는 제품(해당없음·등급 외)이거나 확인 못 했으면 null
    energy_grade: Optional[Literal[1, 2, 3, 4, 5]] = None
    energy_checked_at: Optional[str] = None
    # 정수기 설치 형태(데스크·스탠드·빌트인)와 설치가이드의 현장 치수(mm). 키는 docs/specs/catalog.md
    install_form: Optional[str] = None
    install_mm: dict[str, float] = Field(default_factory=dict)
    needs_drain: Optional[bool] = None  # 배수 호스 연결이 꼭 필요한지. 가이드에 없으면 null
    model_3d: Optional[str] = None
    demo_only: bool = False  # True면 LGE.COM 값이 아닌 시연·테스트용 가상 데이터
    # 화면에 내놓는 모델인지. 카탈로그 파일에는 없고, 불러올 때 data/catalog/lineup.json을 보고 정한다 (core.service.Catalog)
    listed: bool = True
    lineup_family: Optional[str] = None  # 전달받은 묶음의 제품군. 같은 제품군은 목록에서 한 줄로 묶는다
    lineup_note: Optional[str] = None  # 색이 같은데 구성이 다른 모델을 가르는 말 (예: 상단 글라이드 레일 있음)

    @property
    def on_sale(self) -> bool:
        """목록·추천에 나와도 되는 제품: 내놓는 모델이고 LGE.COM에서 지금 파는 것 (가상 데이터는 늘 나온다)."""
        return self.demo_only or (self.listed and self.sale_status in ("ACTIVE", "SOLD_OUT"))
