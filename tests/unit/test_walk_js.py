"""웹 1인칭 둘러보기 순수 로직(apps/web/js/walk.js)을 node 내장 테스트로 돌린다. node가 없으면 건너뛴다."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_walk_logic():
    r = subprocess.run([NODE, "--test", str(ROOT / "tests" / "web" / "walk.test.mjs")],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
