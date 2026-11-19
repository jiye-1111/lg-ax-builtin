import os

# 테스트는 가상 카탈로그(demo_fixture.json)의 고정 SKU를 쓴다
os.environ["CATALOG_INCLUDE_DEMO"] = "1"
