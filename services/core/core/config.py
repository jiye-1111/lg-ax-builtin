"""환경변수 설정 (.env). 모든 주소·포트·토큰은 여기서만 읽는다 (기획 §6.3)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


# .env.ai = AI 키만 따로 두는 파일 (메모장으로 붙여 넣기 쉽게). 둘 다 git에 올리지 않는다.
ENV_FILES = (".env", ".env.ai")


def _load_dotenv() -> None:
    for name in ENV_FILES:
        p = ROOT / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():  # 메모장이 붙이는 BOM도 처리
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def storage_dir() -> Path:
    return Path(os.getenv("STORAGE_DIR", ROOT / "storage")).resolve()


def catalog_paths() -> list[Path]:
    paths = [ROOT / "data" / "catalog" / "products.json"]
    if os.getenv("CATALOG_INCLUDE_DEMO", "0") == "1":
        paths.append(ROOT / "data" / "catalog" / "demo_fixture.json")
    return paths


def catalog_lineup() -> Path | None:
    """화면에 내놓을 모델 목록 파일. CATALOG_LINEUP을 all로 두면 카탈로그 전체를 내놓는다."""
    v = os.getenv("CATALOG_LINEUP", "data/catalog/lineup.json").strip()
    if v in ("", "all"):
        return None
    p = Path(v)
    return p if p.is_absolute() else ROOT / p


def public_base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", f"http://localhost:{os.getenv('API_PORT', '8000')}").rstrip("/")
