# 인계: Fusion으로 LG 가전 3D 모델 다시 만들기 (2026-11-20)

카탈로그 53종을 LGE.COM 치수도 기준으로 Fusion에서 다시 모델링해 웹 모델(`apps/web/models/products/<SKU>.glb`)을 바꿔 끼우는 작업이다. 빌트인 주방부터 했고, 이어서 나머지 가전으로 넓힌다.

- 브랜치: `claude/project-thread-nqfl5j` (main 81c233d까지 합쳐 둠. main으로 직접 푸시는 권한이 막혀 있어 PR로 합쳐야 한다). 커밋은 제품군마다 하나씩.
- 커밋 작성자: 이 PC에는 git 전역 이름이 없어서 `git -c user.name="jiye-1111" -c user.email=<지예 이메일> commit ...`으로 커밋했다.

## 진행 상황: 45 / 53

끝남 (`data/fusion/<SKU>/drawing.json` 있음):

| 제품군 | SKU |
|---|---|
| 냉장고 Fit & Max | G646GBB031, G646MEE021, G646SVV031, M616GBB0M1, D646GBB041 |
| 김치냉장고 Fit & Max | Z386GBB281, Z386MEE221, Z386SLL281, Z484GBB172 |
| 식기세척기 | DUE6BGE, DUE6EWL2E |
| 인덕션 | BEI3QKBLOE, BEF3AMB4E, BEF3ASMLE |
| 정수기 (+파우셋) | WU523AWB, WU523ACB |
| 컨버터블 패키지 | X323MEF, Y323MEF, Z323MEF, X324GB7, Y324GB7 |
| 와인셀러 | W1213GG, W1212GB, W0492GG, W0082GLE |
| 오븐·전자레인지 | MLJ32ERS, MLJ39ER, MW23FDI |
| 세탁·건조 | WL21WDU, WL21EGZU(투톤 색은 아직 한 색), FH25KA, FX24KNTR, FX24ENER, RD20KNTR, RD21ESER |
| 스타일러·슈케어 | SC5GMR80S, SC5MBR80S, SC5MSR82A, SS4RHS60E, SS4RWS60E (SC5MBR80S·SS4RWS60E 치수도는 직접 못 봄) |
| TV·스탠바이미 | OLED65C5ENA, 65QNED65BBA, OLED77B6BNA, 27LX6TPGA, 32LX6BPGA (스탠바이미는 최대 높이 상태) |

남음 (8):

- 에어컨·공기 관련: FQ18GV3EK2, FQ17GU1ED2, AS305DWWL, AS356NSMA, AS186HWWL, HY706RWUAB, DQ235MWGA
- 청소기: AX920BWE

53종 다음은 전 모델로 넓힌다 (카탈로그 스레드가 LGE.COM 전체를 넣는 중).

## 모델 하나 만드는 절차

1. **레퍼런스 확인 (ECC 검색·리서치 스킬)**
   - 카탈로그에서 `source_url`, `product_dims_mm`, `cmf_options` 확인.
   - LGE.COM 제품 페이지에서 치수도 이미지 주소를 찾는다: `static.lge.co.kr/kr/images/spec/<모델>.akor_2p.jpg`. SKU와 파일 이름이 다를 수 있다 (Z386GBB281 페이지는 z386sll281 치수도, BEI3QKBLOE는 bei3qkblo). 페이지를 끝까지 스크롤한 뒤 `img` 중 `images/spec`을 찾으면 된다.
   - 브라우저에서 이미지를 열고 canvas 픽셀로 문 나눔·홈·서랍 위치를 잰다. 이미지 가로·세로 비율이 정확히 같지 않을 수 있어서 높이는 높이 치수로, 폭은 폭 치수로 따로 비율을 잡는다. 측면 색(대부분 검정)과 문 색도 픽셀로 확인.
2. **도면**: 원칙은 Figma "LG 빌트인 제품 도면" 파일. 2026-11-20에 Figma MCP 월 한도가 차서 `data/fusion/<SKU>/drawing.json`에 같은 규칙(1px = 1mm, 정면/측면/윗면 parts)으로 저장했다. **한도가 풀리면 Figma로 옮겨야 한다** (아직 하나도 안 옮김).
3. **Fusion (Fusion MCP `fusion360`, 애드인 Shift+S → Fusion360MCP 실행 상태여야 함)**
   - 단위 cm, Z-up, 정면 = -Y, 바닥 가운데가 원점.
   - `create_box`: center_x/center_y는 가운데, **center_z는 바닥**. 만든 바디 이름이 '본체N'이라 `get_scene_info`로 보고 `rename_body`.
   - 바디 이름 앞부분이 역할(재질)이다: `body`(본체), `door_*`(문·겉판, 웹에서 색 바뀌는 finish), `top_*`(상판 finish), `handle_*`, `trim_*`(어두운 띠·홈·핸들·다리), `vent_*`(아래 받침), `display_*`(검정 유광), `print_*`(상판 인쇄), `panel_*`(drawing.json `colors.panel` 색), `chrome_*`.
   - 필렛: 문 0.3cm 정도. 둥근 몸체는 `fillet edge_selection=vertical`.
   - `export`로 바디마다 STL을 `data/fusion/<SKU>/<바디이름>.stl`에, 디자인 전체를 `<SKU>.f3d`로. 한꺼번에 많이 부르면 가끔 타임아웃이나 NOT_FOUND가 나니 그럴 땐 하나씩.
4. **Blender → glb + 썸네일 + 테스트**: `.\services\blender-worker\ship_fusion_models.ps1 -Skus <SKU>[,<SKU>...]`
   - `services/blender-worker/worker/bpy_scripts/fusion_to_glb.py` → `apps/web/models/products/<SKU>.glb` (덮어쓰기만, `index.json`은 손대지 않음. 규칙 `docs/specs/drawings.md`)
   - `render_thumbs.py` → `apps/web/img/products/<SKU>.webp`
   - `uv run pytest tests/integration/test_product_models.py` (치수 ±3mm, 원점, finish 재질)
   - 색·재질만 다른 모델은 `drawing.json`에 `"geometry_from": "<다른 SKU>"`만 두면 STL을 같이 쓴다.
   - 본체 색은 `drawing.json`의 `colors.body.hex_approx` (Fit & Max 측면 검정 `#2B2B2D` 등).
5. 썸네일을 눈으로 확인하고 제품군 단위로 커밋·푸시. 진행 개수는 스레드에 짧게 보고.

## 정수기 파우셋

LGE.COM 정수기 색 옵션(크림 화이트/베이지)은 실제로는 **파우셋 색**이고, 싱크대 아래 본체는 두 모델 모두 밝은 회색이다. 그래서

- 본체(`WU523AWB.glb`, `WU523ACB.glb`)는 회색 고정 (finish 없음)
- 파우셋(Ø48, 높이 264, 돌출 188)을 `data/fusion/WU523_faucet`에서 만들어 `<SKU>_faucet.glb`로 내보내고 finish를 줬다
- 놓을 위치는 `apps/web/models/products/companions.json` (본체 바닥 가운데 기준 [x, 위, 앞] m). 지금은 조리대 높이 850mm, 본체 가운데에서 100mm 뒤로 **가정**한 값
- `apps/web/js/viewer.js`의 `loadModel`이 companions.json을 읽어 본체 모델에 파우셋을 붙인다. 테스트는 통과했지만 **웹 화면에서 정수기를 실제로 놓아 보는 확인은 아직 못 했다**

## 알아 둘 것

- 전체 `uv run pytest`에서 `tests/integration/test_deploy.py::test_pages_build_writes_api_base`는 이 PC에 WSL bash가 없어서 실패하고, `tests/unit/test_ai_style.py::test_without_api_key_uses_rules`는 전체로 돌릴 때만 가끔 실패한다(단독으로는 통과). 둘 다 이 작업과 상관없다.
- `data/drawings/<SKU>.json`(Figma 도면, Blender `build_products.py`용)은 그대로 두었다. `index.json`의 layout은 여전히 "drawing"이지만 실제 glb는 Fusion 모델이다.
- `C:\apps\web\img\products\G646GBB031.webp`는 처음에 상대경로로 렌더하다 잘못 생긴 파일이다. 지워도 된다 (도구로는 시스템 경로라 못 지웠다).
- Blender 쪽 마감 강화(문 유리 코팅 반사, 홈 안쪽 그림자, 웹 압축)는 아직 안 했다.

## 남은 제품 치수도 주소 (2026-11-20 제품 페이지에서 확인)

앞에 `https://static.lge.co.kr/kr/` 를 붙인다. 제품 페이지 HTML을 fetch해서 `images/spec/...` 를 찾으면 한 번에 나온다.

| SKU | 치수도 |
|---|---|
| W1213GG | images/spec/w1213gg_size_2p.jpg |
| W1212GB | images/spec/W1212GB_size_2p.jpg |
| W0492GG | images/spec/W0492GG_size_2p.jpg |
| W0082GLE | images/spec/W0082GLE_size_2p.jpg |
| MLJ32ERS | images/spec/mlj32ers.akor_2p.jpg |
| MLJ39ER | images/spec/mlj39er.akor_2p.jpg |
| MW23FDI | images/spec/mw23fd.akor_2p.jpg |
| WL21WDU | images/spec/wl21wdu.akor_2p.jpg |
| WL21EGZU | images/spec/wl21egzu.akor_2p.jpg |
| FH25KA | images/spec/fh25ka.akor_2p.jpg |
| FX24KNTR | images/spec/fx24knt.akor_2p.jpg |
| FX24ENER | images/spec/fx24ene.akor_2p.jpg |
| RD20KNTR | images/spec/rd20kntr.akor_2p.jpg |
| RD21ESER | images/spec/rd21eser.akor_2p.jpg |
| SC5GMR80S | images/spec/sc5gmr80s_2p.jpg |
| SC5MBR80S | images/spec/sc5mbr80s_2p.jpg |
| SC5MSR82A | images/spec/sc5msr82a.akor_2p.jpg |
| SS4RHS60E | images/spec/ss4rhs60e.akor_2p.jpg |
| SS4RWS60E | images/spec/ss4rws60e.akor_2p.jpg |
| OLED65C5ENA | images/spec/OLED65C5SNA_wa_2p.jpg |
| 65QNED65BBA | images/spec/65QNED70BKS.AKRG_2p.jpg |
| OLED77B6BNA | images/spec/OLED77B6SS.AKRG_2p.jpg |
| 27LX6TPGA | images/spec/27LX6TPGA.AKR_2p.jpg |
| 32LX6BPGA | images/spec/32LX6BPGA.AKR_1_2p.jpg |
| FQ18GV3EK2 | images/spec/FQ17EV3ED1.akor_2p.jpg |
| FQ17GU1ED2 | images/spec/fq18gu1ea1.akor_2p.jpg |
| AS305DWWL | images/spec/as305dwwa.akor_2p.jpg |
| AS356NSMA | images/spec/as356nsma.akor_2p.jpg |
| AS186HWWL | images/spec/as186hwwl.akor_2p.jpg |
| HY706RWUAB | images/spec/HY706RWUA_2p.jpg |
| DQ235MWGA | images/spec/dq235mwgas.akor_2p.jpg |
| AX920BWE | images/spec/ax920bwe.akor_2p.jpg |
