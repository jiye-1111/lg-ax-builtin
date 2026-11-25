import os

# 테스트는 가상 카탈로그(demo_fixture.json)의 고정 SKU를 쓴다
os.environ["CATALOG_INCLUDE_DEMO"] = "1"
# 판정·추천 규칙 테스트는 카탈로그 전체로 본다. 내놓는 모델만 거르는 것은 test_lineup_only.py에서 따로 확인한다
os.environ["CATALOG_LINEUP"] = "all"
