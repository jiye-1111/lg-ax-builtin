# 아이폰 라이다 스캔 오차와 보정 방법

빌트인 가전은 3~6 mm 차이로 들어가고 안 들어가고가 갈리는데, 아이폰 라이다 스캔은 그보다 훨씬 큰 오차를 갖고 있다. 그래서 (1) 스캔이 실제로 얼마나 틀리는지, (2) 스캔할 때와 스캔한 뒤에 무엇으로 줄일 수 있는지, (3) 남는 오차를 판정에 어떻게 반영할지 정리했다. 끝에 실제 교실 스캔으로 돌려 본 결과를 붙였다.

## 1. 결론

- 스캔 한 번의 치수 오차는 작은 방 기준 **1~3 cm (1σ)**, 큰 방이나 여러 방을 이어 스캔하면 **수십 cm**까지 나온다. 이 오차는 길이에 따라 **약 1~1.5%씩** 커지는 경향이 있다.
- 지금 판정의 스캔 마진 30 mm는 짧은 자리에는 괜찮지만, 3 m가 넘는 자리에는 부족하다.
- 우리가 받는 UGScan(RoomPlan) 결과는 **벽이 이미 직각·평행으로 정리돼 나온다** (실제 교실 스캔에서 0.01° 이하). 직각 맞추기로 더 얻을 것은 없다.
- 가장 싸고 효과가 큰 방법은 **제품을 넣을 그 자리를 줄자로 한 번 재서 넣는 것**이다. 다른 벽 하나를 재서 전체 배율을 고치는 방법은, 오차가 방 전체에 고르게 퍼져 있을 때만 효과가 있다.
- 그래서 판정은 "스캔만으로 적합"을 쉽게 주지 않는다. 여유가 오차(2σ)보다 클 때만 적합으로 보고, 그 사이는 "실측 필요"로 보여 준다.

## 2. 오차가 얼마나 나오나 (문헌)

| 출처 | 조건 | 결과 |
|---|---|---|
| Apple RoomPlan 연구 글 [1] | RoomPlan 내부 | 벽·개구부를 **가로세로 3 cm 격자**로 예측. 최대 15×15 m 방. 길이 오차 수치는 공개하지 않음 |
| it-jim 실사용 [3] | RoomPlan | 6.45 m 벽을 6.82 m로 (+5.8%). 벽 두께는 약 16 cm 고정 |
| Teppati Losè 외 2023 [4] | 아이폰 13 Pro 앱 4종 vs 지상 레이저 스캐너 | 거리 오차 평균 5~10 cm, 95% 신뢰 기준 10~20 cm |
| Nuha 외 2026 [5] | 아이폰 12 Pro Max + Polycam vs Leica BLK360 | 치수 RMSE 18.2 cm (1.6~11.7 m 길이), 평균 절대 오차 약 1.4%, **길게 재는 쪽으로 치우침** |
| Díaz-Vilariño 외 2022 [6] | 아이패드 Pro, 방 2개 | 벽면 평면 오차 5.3 mm. 루프를 닫지 않으면 10 cm 벽이 40 cm로 (드리프트) |
| Dev. Built Env. 2023 [8] | 아이패드 Pro | 멈춰서 찍으면 평면에서 1 mm 이내, 움직이며 찍으면 약 1 cm. **1~1.5 m 거리**가 가장 좋음 |
| Costantino 외 2022 [9] | 아이폰 | 문제가 없을 때 1~3 cm. 3 m 거리에서 드리프트 시작 |
| Sheshtar 외 2025 [22] | 한 공간 | 5분 스캔 1.2 cm, 10분 스캔 2.9 cm (오래 찍을수록 나빠짐) |

찾지 못한 것: RoomPlan 자체의 벽·문 치수 오차를 mm 단위로 잰 논문, 벽 사이 각도 오차, 고정 배율 오차를 %로 잰 연구. 여러 번 스캔해 평균 낸 연구도 없었다.

정리하면 오차는 크게 세 가지다.
1. **격자·두께 가정**: RoomPlan은 3 cm 격자, 16 cm 고정 두께의 상자로 벽을 만든다.
2. **드리프트**: 움직이면서 위치 추정이 조금씩 밀린다. 오래, 멀리, 넓게 찍을수록 커진다.
3. **표면 문제**: 유리, 스테인리스, 광택 있는 짙은 색 문짝은 깊이 신뢰도가 떨어진다 [23]. 부엌에 특히 많다.

## 3. 스캔할 때 정확도를 높이는 방법

| 방법 | 근거 | 우리 앱에서 |
|---|---|---|
| 벽에서 **1~1.5 m** 거리 유지, 3 m 넘게 떨어지지 않기 | [8][9] | 스캔 안내 문구에 넣기 |
| 천천히, 멈췄다 움직이기 | 정지 1 mm vs 이동 1 cm [8] | 안내 문구 |
| 짧게 찍기 (부엌만 따로) | 5분 1.2 cm vs 10분 2.9 cm [22] | "부엌만 한 번 더 스캔" 단계 |
| 시작한 자리로 돌아와 **루프 닫기** | 루프 없으면 40 cm 오차 [6], 루프 닫는 앱이 더 정확 [10] | 안내 문구 |
| 밝기 50 lux 이상 | RoomPlan 조건 [19] | 안내 문구 |
| 유리·스테인리스 앞은 비스듬히, 가까이 | 반사면 신뢰도 낮음 [23] | 안내 문구 |

### 깊이 융합, 학습 기반 보정 (직접 만드는 앱일 때만)
UGScan은 RoomPlan 결과만 내보내서 우리가 원본 깊이를 받을 수 없다. 나중에 스캔 앱을 직접 만든다면:
- ARKit `sceneDepth`(256×192)와 픽셀별 신뢰도 맵을 받아 **신뢰도 높은 점만 TSDF로 합치기** [23][24]. 아이패드 실험에서 합친 형상 오차 약 13.8 mm, 위치 추정 오차 4.45 mm [25]. 즉 5~15 mm가 현실적인 바닥이다.
- **Prompt Depth Anything** [26]: 라이다 깊이를 힌트로 넣어 고해상도 깊이를 만든다. ARKitScenes에서 RMSE 4.23 → 3.15 cm. 빈 곳을 채우고 선명하게 만드는 데는 좋지만 **mm 단위까지 내려가지는 않는다**.
- 원본 점군에서 RANSAC으로 벽면을 다시 맞추면 [14][15] RoomPlan의 3 cm 격자와 고정 두께 문제는 줄일 수 있다. 드리프트는 못 없앤다.

결론: 학습·융합으로 cm 수준은 좋아지지만, 빌트인 판정에 필요한 mm 수준은 **실측이 아니면 못 맞춘다**.

## 4. 스캔한 뒤 보정하는 방법

| 방법 | 하는 일 | 효과 | 우리 스캔에서 |
|---|---|---|---|
| 직각·평행 맞추기 (맨해튼 가정) [12][13] | 주축에서 몇 도 안쪽으로 기운 벽을 0°/90°로 돌림 | 각도·모서리 정리 | RoomPlan이 이미 해 줌 (0.01°). 다른 스캔 앱이나 손으로 고친 도면에만 필요 |
| 기준 길이로 배율 보정 | 잰 길이 1개 이상으로 전체 배율 계산 | 오차가 고르게 퍼진 경우 크게 줄어듦 | 드리프트가 크면 효과 없음 (아래 실험) |
| 도면 맞추기 [18] | 도면 벽과 스캔 벽을 회전·배율·이동으로 맞춘 뒤 ICP로 다듬기 | 도면 치수를 그대로 쓰게 됨 | 도면이 있을 때 가장 좋은 기준. 도면 자체 오차(시공 오차)는 남음 |
| 여러 번 스캔 비교 | 같은 부엌을 2~3번 스캔 | 무작위 오차는 1/√N로 줄어듦. 치우침은 안 줄어듦 | 평균보다 **스캔 사이 차이를 σ로 보여 주는 용도**가 더 쓸모 있음 |
| 기준 물체 (마커, A4 용지, 문) | 크기를 아는 물체로 배율 | 마커 정확도 mm 수치는 확인 못 함. 문틀은 몇 cm씩 달라서 약한 기준 | 문 폭·싱크대 깊이 표준값(900/600 mm 등)은 1차 출처로 확인 못 해서 **쓰지 않는다** |

## 5. 우선순위 (작업량 대비 효과)

| 순위 | 방법 | 작업량 | 효과 |
|---|---|---|---|
| 1 | **넣을 자리 줄자 실측 1개** (이미 있는 `measured` 입력을 판정 화면에서 바로 받게) | 작음 | 그 자리 오차가 수 cm → 수 mm. 가장 확실 |
| 2 | **길이 따라 커지는 여유** + "실측 필요" 표시 | 작음 | 긴 자리를 잘못 "적합"으로 보는 일을 막음 |
| 3 | 스캔 안내 문구 (거리, 속도, 루프, 부엌만 짧게) | 작음 | 오차 자체를 줄임 (문헌상 2배 이상 차이) |
| 4 | 도면 업로드 시 도면 맞추기 | 중간 | 도면 치수 사용 |
| 5 | 잰 길이로 전체 배율 보정 | 작음 | 조건부. 기준이 판정 자리 가까이 있을 때만 |
| 6 | 같은 부엌 2~3번 스캔해 차이 표시 | 중간 | σ를 실제로 잴 수 있음 |
| 7 | 직각 맞추기 | 작음 | RoomPlan에는 효과 없음. 다른 입력 대비용 |
| 8 | 원본 깊이(Stray Scanner) 융합 + 평면 맞춤, AI 깊이 보정 | 중간 | 줄자 없이 벽 치수 오차를 줄이는 유일한 길. §8에 프로토타입 |

## 6. 판정에 오차 반영하기

설치 실무에서는 빌트인 냉장고 개구부를 제품 폭 + 3~6 mm로 잡고, 위·가운데·아래를 재서 가장 작은 값을 쓴다 [20]. 제품별 최종 기준은 LGE.COM 설치 설명서다.

스캔 오차를 이렇게 보자는 안이다.

```
σ(L) = √(σ_abs² + (σ_rel · L)²)      σ_abs = 10 mm, σ_rel = 1% (실측 배율 보정 뒤 0.3%)
여유 > 2σ          → 적합
-2σ ≤ 여유 ≤ 2σ    → 실측 필요 (지금의 "조건부")
여유 < -2σ         → 불가
실측값이 있으면     → 지금처럼 실측 마진 5 mm
```

| 자리 폭 | 지금 마진 | 제안 2σ (보정 전) | 제안 2σ (배율 보정 후) |
|---|---|---|---|
| 0.6 m | 30 mm | 23 mm | 20 mm |
| 1.0 m | 30 mm | 28 mm | 21 mm |
| 3.0 m | 30 mm | 63 mm | 27 mm |

σ 값은 문헌의 1~3 cm, 약 1.4%를 바탕으로 잡은 가정이다. 같은 부엌을 여러 번 스캔해 보면 우리 환경 값으로 바꿀 수 있다. 이 규칙은 `fit-rules.md`와 판정 코드에 반영했다 (애매한 구간은 화면에 "확인 필요").

## 7. 실제 교실 스캔으로 돌려 본 결과

코드: `services/recommender/recommender/scan_correction.py` (테스트 `tests/unit/test_scan_correction.py`)
실험: `uv run python docs/research/scan_correction_experiment.py`

### 실제 스캔 상태 (2026-11-18 교실, 7 × 10.9 m)
- 벽 8개가 모두 88.154° / -1.845° 두 방향뿐이다. 주축에서 벗어난 각도는 최대 **0.01° 이하**.
- 마주 보는 벽 사이 거리와 그 사이 벽 길이가 0.1 mm 안에서 같다 (w8–w1 6.7708 m = w3 6.7707 m). RoomPlan이 이미 직각·평행·모서리를 맞춰 내보낸다는 뜻이다.
- 모서리 끝점 사이가 모두 0.113 m 떨어져 있는데, 벽 두께 0.16 m의 절반을 대각선으로 본 값(0.08√2)이라 오차가 아니다.
- 줄자 실측이 없어서 이 스캔이 실제와 얼마나 다른지는 알 수 없다.

### 오차를 넣고 되돌려 본 실험
정답이 없어서, 실제 스캔을 정답으로 두고 문헌 수준의 오차를 넣은 가짜 스캔을 200번 만들었다. 가장 긴 벽(w8) 하나만 줄자로 쟀다고 보고 배율을 고친 뒤, 나머지 1 m 넘는 벽의 길이 오차를 봤다.

| 오차 모델 | 보정 전 평균 / 95% | 실측 1개로 배율 보정 후 | 직각 맞춤 (가장 기운 벽) |
|---|---|---|---|
| 방 전체 배율 1%, 벽 길이 10 mm, 각도 1° | 42.8 / 108.7 mm | **9.7 / 23.3 mm** | 1.74° → 0.000° |
| 방 전체 배율 1.4%, 벽 길이 15 mm, 각도 1° | 60.0 / 153.4 mm | **14.4 / 34.5 mm** | 1.74° → 0.000° |
| 위 + 벽마다 다른 1% (드리프트) | 62.2 / 168.9 mm | **69.6 / 176.4 mm** (오히려 나빠짐) | 1.74° → 0.000° |

- 오차가 방 전체에 고르게 퍼져 있으면 다른 벽 하나만 재도 오차가 약 4분의 1로 준다.
- 드리프트처럼 벽마다 다르게 틀리면 다른 벽을 잰 값으로는 못 고친다. 문헌은 이쪽(드리프트)에 가깝다고 본다 [6][9]. 그래서 1순위가 "넣을 자리를 직접 재기"다.
- 직각 맞춤은 넣은 각도 오차를 완전히 되돌리지만, 실제 RoomPlan 스캔에는 애초에 그런 오차가 없다.

## 8. 줄자 없이 정확도 올리기: 원본 깊이로 벽 치수 다시 재기

실측을 부탁하지 않고 오차를 줄이려면, RoomPlan이 정리해 준 상자(3 cm 격자) 대신 **원본 깊이를 직접 받아서 벽면을 다시 맞추는** 길밖에 없다. UGScan은 원본 깊이를 내보내지 않아서 캡처 앱을 하나 더 쓴다.

### 무엇으로 찍나
| 앱 | 원본 깊이 내보내기 | 비용 | 판단 |
|---|---|---|---|
| **Stray Scanner** [27][28] | 깊이 PNG(256×192, mm), 신뢰도(0·1·2), 프레임별 위치·카메라 값(`odometry.csv`) | 무료, MIT | **이걸로** |
| Record3D [29] | EXR 깊이 등 | 무료는 3번까지, 이후 유료 | 보류 |
| Polycam [30] | 개발자 모드를 켜고 찍어야 원본 데이터 | 요금제 확인 못 함 | 보류 |
| 3D Scanner App | 프레임별 사진·위치. 깊이 포함 여부 확인 못 함 | 무료 | 보류 |

### 어떻게 보정하나
코드: `services/blender-worker/worker/rawdepth.py` (테스트 `tests/unit/test_rawdepth.py`, 앱에는 아직 연결하지 않음)

1. 신뢰도가 높은(2) 픽셀만 3D 점으로 바꾼다. 유리·스테인리스처럼 틀리기 쉬운 곳이 여기서 빠진다.
2. 여러 프레임의 점을 1 cm 칸으로 평균한다 (간단한 깊이 융합). Open3D의 TSDF [31][32]로 바꿀 수 있지만 벽 치수만 재는 데는 numpy로 충분해서 의존성을 늘리지 않았다.
3. RANSAC으로 평면을 찾고 안쪽 점으로 최소제곱 다시 맞춘다. 벽면 하나에 점 10만 개가 들어가서 면 위치가 mm 단위로 잡힌다.
4. UGScan 스캔과 따로 찍어서 좌표계가 다르므로, 벽 방향과 위치를 스스로 맞춘 뒤 RoomPlan 벽 ↔ 평면을 짝짓는다. 4면 이상 안 맞으면(다른 방이면) 아무것도 고치지 않는다.
5. 마주 보는 벽 사이 거리를 평면 기준으로 다시 잰다.

### 합성 주방으로 돌려 본 결과
실제 원본 깊이 캡처가 아직 없어서 3.0 × 2.4 m 합성 주방으로 시험했다. RoomPlan 쪽에는 배율 +1.5%와 3 cm 격자 오차를 넣었다 (`uv run python docs/research/rawdepth_experiment.py`, 24프레임, 10회).

| 조건 | RoomPlan 벽 사이 거리 오차 | 원본 깊이로 다시 잰 뒤 (평균 / 최대) |
|---|---|---|
| 깊이 노이즈 1%, 위치 밀림 없음 | 50.0 mm | **1.2 / 12.8 mm** |
| 깊이 노이즈 1%, 프레임마다 1 mm 밀림 | 50.0 mm | **3.3 / 12.5 mm** |
| 깊이 노이즈 1%, 프레임마다 3 mm 밀림 | 50.0 mm | 10.5 / 44.5 mm |
| 깊이 노이즈 1%, 프레임마다 10 mm 밀림 | 50.0 mm | 25.4 / 48.0 mm |
| 깊이 노이즈 2%, 위치 밀림 없음 | 50.0 mm | 17.9 / 49.1 mm |

- 깊이 노이즈는 평균으로 사라진다. 남는 오차는 거의 다 **위치 밀림(드리프트)** 이다. 그래서 캡처는 **주방만, 30초 안쪽으로 짧게** 찍어야 한다. 아이패드 실험의 위치 오차 4.45 mm [25] 수준이면 표의 둘째~셋째 줄쯤이다.
- 합성 결과라서 실제 값은 아니다. 실제 캡처 하나로 확인해야 하고, 그때 확인할 것: Stray Scanner 위치값의 카메라 축 규칙(문서에 안 적혀 있음), 깊이 치우침(1.5 m 넘으면 짧게 읽힌다는 보고 [36]).

### AI 깊이 보정 (Prompt Depth Anything)
- 라이다 깊이(192×256)를 힌트로 넣어 고해상도 깊이를 만든다 [26][33]. 코드·가중치 Apache-2.0, `transformers`에 들어가 있고 [34] 작은 모델(vits, 2,510만 파라미터)과 ONNX 판 [35]이 있다.
- 논문 수치: 픽셀 깊이 오차 2.51 → 1.35 cm, 융합한 형상 정확도 8.11 → 6.99 cm (ScanNet++).
- 쓰임새: 벽처럼 넓은 면은 점이 이미 충분해서 이득이 작다. **가전 넣을 자리의 모서리·문틀처럼 좁은 경계**를 또렷하게 잡는 데 쓴다. 깊이 프레임을 넣는 자리(`Frame.depth_m`)에 보정된 깊이를 그대로 넣으면 된다.
- 이 작업 환경에서는 Hugging Face가 막혀 있어 모델을 받지 못했다. CPU 속도는 공개된 수치가 없다 (GPU A100에서 vits 80 FPS). 팀 PC에서 받아 실제 캡처로 켜고 끈 차이를 재는 게 다음 순서다.

### 다음 순서
1. 아이폰에 Stray Scanner를 깔고 주방(또는 교실 한 구석)을 30초쯤 찍어 폴더째 올린다. 레이저 거리계로 한두 군데만 재 두면 정답과 비교할 수 있다 (한 번이면 되고, 사용자에게 시키는 게 아니라 검증용).
2. 그 캡처로 축 규칙 확인 → `refine_room` 결과와 비교 → Prompt Depth Anything 켜고 끈 차이.
3. 괜찮으면 앱에 "정밀 스캔 올리기(선택)"로 붙여서, 보정된 벽은 좁은 마진으로 판정한다.

## 출처
1. Apple ML Research, 3D Parametric Room Representation with RoomPlan — https://machinelearning.apple.com/research/roomplan
2. Apple Developer Forums 712500 — https://developer.apple.com/forums/thread/712500
3. it-jim, RoomPlan is Awful and it's Great! — https://www.it-jim.com/blog/roomplan-framework-by-apple/
4. Teppati Losè 외, Digital 2023 3(4):30 — https://www.mdpi.com/2673-7418/3/4/30
5. Nuha 외, Geodesy & Cartography 2026 — https://journals.vilniustech.lt/index.php/GAC/article/download/25678/13527
6. Díaz-Vilariño 외, ISPRS 2022 — https://isprs-archives.copernicus.org/articles/XLIII-B4-2022/303/2022/isprs-archives-XLIII-B4-2022-303-2022.pdf
7. Chase 외, UNB 2022 — https://conferences.lib.unb.ca/index.php/tcrc/article/view/645
8. iPad Pro 내장 라이다 정확도 평가, Developments in the Built Environment 2023 — https://doaj.org/article/9cbab8e9cd04423aae61f174ca458b1e
9. Costantino 외, ASI 2022 5:63 — https://iris.poliba.it/retrieve/7da9a53f-82ec-4471-9402-88aec7532fe7/2022_Smartphone_LiDAR_Technologies_for_Surveying_pdfeditoriale.pdf
10. Treccani 외, ISPRS 2024 — https://isprs-archives.copernicus.org/articles/XLVIII-2-W8-2024/431/2024/
11. Abdel-Majeed 외, HBRC J. 2024 (유료라 읽지 못함) — https://www.tandfonline.com/doi/full/10.1080/16874048.2024.2408839
12. Lin 외, Floorplan-Jigsaw — https://arxiv.org/abs/1812.06677
13. Stekovic 외, MonteFloor — https://arxiv.org/abs/2103.11161
14. Ambruș, Claici, Wendt, room segmentation — https://people.csail.mit.edu/sclaici/pdf/ambrusclaici2017room.pdf
15. Schnabel 외, Efficient RANSAC 2007 — https://cg.cs.uni-bonn.de/backend/v1/files/publications/schnabel-2007-efficient.pdf
16. Adámek 외, Sensors 2023 23:5746 — https://www.mdpi.com/1424-8220/23/12/5746
17. KS F 3109 문세트 — https://standard.go.kr/KSCI/standardIntro/getStandardSearchView.do?ksNo=KSF3109
18. Sokolova 외, Floorplan-Aware Camera Poses Refinement — https://arxiv.org/abs/2210.04572
19. WWDC23 Explore enhancements to RoomPlan — https://developer.apple.com/wwdc23/10192
20. Jaspector, built-in refrigerator installation requirements (업계 글) — https://www.jaspector.com/articles/built-in-refrigerator-installation-requirements/
21. LG clearance dimensions 안내 — https://www.lg.com/ca_en/support/product-help/CT20098040-1397504443575-others
22. Sheshtar 외, Applied Sciences 2025 15:1085 — https://www.mdpi.com/2076-3417/15/3/1085
23. Apple ARKit confidenceMap — https://developer.apple.com/documentation/arkit/ardepthdata/confidencemap
24. Baruch 외, ARKitScenes — https://arxiv.org/abs/2111.08897
25. Li 외, MobileBrick CVPR 2023 — https://arxiv.org/abs/2303.01932
26. Lin 외, Prompt Depth Anything — https://arxiv.org/abs/2412.14015
27. Stray Scanner (MIT) — https://github.com/strayrobots/scanner
28. Stray Scanner 내보내기 형식 — https://github.com/strayrobots/scanner/blob/main/docs/format.md
29. Record3D — https://apps.apple.com/us/app/id1477716895
30. Polycam 원본 데이터 내보내기 — https://learn.poly.cam/hc/en-us/articles/38276871185044-How-to-Extract-Raw-Data-and-What-Is-Included
31. StrayVisualizer (Open3D TSDF 융합 예제) — https://github.com/kekeblom/StrayVisualizer
32. Open3D — https://pypi.org/project/open3d/
33. Prompt Depth Anything 저장소 — https://github.com/DepthAnything/PromptDA
34. transformers 문서 — https://huggingface.co/docs/transformers/en/model_doc/prompt_depth_anything
35. ONNX 판 — https://huggingface.co/onnx-community/promptda_vits_hf
36. Apple Developer Forums 773571 (깊이가 멀수록 짧게 읽힌다는 보고, Apple 확인 아님) — https://developer.apple.com/forums/thread/773571
