"""진행 단계는 직접 해야 하나씩 넘어간다 (지예: 들어오자마자 다 체크돼 있으면 의미가 없다)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

GUIDE = Path(__file__).resolve().parents[2] / "apps/web/js/guide.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")


def states(placements, flow):
    code = f"""
globalThis.document = {{ getElementById: () => null }}; globalThis.window = {{}};
const {{ stepState }} = await import({json.dumps(GUIDE.as_uri())});
const project = {{ scene_state: {{ placements: {json.dumps(placements)} }} }};
console.log(JSON.stringify(stepState(project, null, {json.dumps(flow)}).map((s) => s.state)));
"""
    r = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


FIT = [{"verdict": "fit"}]


def test_first_visit_starts_at_step_one_even_with_products_placed():
    assert states([], {}) == ["current", "todo", "todo"]
    assert states(FIT, {}) == ["current", "todo", "todo"]  # 공간 확인을 안 했으면 1단계부터


def test_each_step_needs_its_own_action():
    assert states([], {"space": True}) == ["done", "current", "todo"]
    assert states(FIT, {"space": True}) == ["done", "done", "current"]
    assert states(FIT, {"space": True, "order": True}) == ["done", "done", "done"]


def test_order_without_earlier_steps_does_not_skip_ahead():
    assert states([], {"order": True}) == ["current", "todo", "todo"]
    assert states([{"verdict": "no_fit"}], {"space": True}) == ["done", "done", "warn"]


def test_screen_shows_what_to_do_now_and_animates_each_step():
    web = GUIDE.parents[1]
    js = (web / "js" / "remodel.js").read_text(encoding="utf-8")
    css = (web / "studio.css").read_text(encoding="utf-8")
    assert 'id="stepCard"' in js and "setFlow({ space: true })" in js and "setFlow({ order: true })" in js
    assert "just-done" in js and "@keyframes step-pop" in css
