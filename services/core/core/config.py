"""환경변수 설정 (.env). 모든 주소·포트·토큰은 여기서만 읽는다 (기획 §6.3)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def storage_dir() -> Path:
    return Path(os.getenv("STORAGE_DIR", ROOT / "storage")).resolve()


def catalog_paths() -> list[Path]:
    paths = [ROOT / "data" / "catalog" / "products.json"]
    if os.getenv("CATALOG_INCLUDE_DEMO", "1") == "1":
        paths.append(ROOT / "data" / "catalog" / "demo_fixture.json")
    return paths


def public_base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", f"http://localhost:{os.getenv('API_PORT', '8000')}").rstrip("/")
