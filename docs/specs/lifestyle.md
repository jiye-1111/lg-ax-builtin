# 생활 이야기로 가전 고르기

하우니에 "맞벌이 4인 가족, 장은 주말에 몰아서, 아기"처럼 생활을 말하면 가전마다 맞는 용량으로 하나씩 고른다.

- AI(`core/ai_life.py`)는 이야기에서 **사실만** 뽑는다: 가족 수, 아기, 장을 몰아 보는지, 김치·김장, 맞벌이. 키가 없으면 같은 사실을 규칙으로 읽는다.
- 용량 범위는 `recommender/lifestyle.py`가 아래 구매 가이드 숫자로 정한다. **가이드에 숫자가 없는 경우는 용량 조건을 두지 않는다.**
- 제품은 그 범위 안에서 이 집에 들어가고(판정 `no_fit` 아님) 판매 중인 것 중 추천 순서 첫 번째.
- 고른 가전으로 바로 배치 추천(조합)까지 이어 갈 수 있다 (`/assist`에 `categories`).

## 기준 (확인 2026-11-20)

| 가전 | 조건 | 범위 | 원문 | 출처 |
|---|---|---|---|---|
| 냉장고 | 1~2인 | 300~500L | "1~2인 실속 구성은 300~500L대부터 보면 돼요" | https://bestshop.lge.co.kr/story/insight/detail/IN10025001 |
| 냉장고 | 4인 + 식재료 많음 | 600L대 | "식재료가 많은 4인 가구라면 서랍처럼 여는 600L대" | https://bestshop.lge.co.kr/story/insight/detail/IN10037000 |
| 냉장고 | 식재료 많음 (5인 이상·인원 모름) | 800L 이상 | "보관하는 식재료가 많은 집은 800L대 대용량부터" | https://bestshop.lge.co.kr/story/insight/detail/IN10025001 |
| 냉장고 | 그 밖 (3인, 4인 보통 등) | 조건 없음 | 가이드에 숫자 없음 | |
| 김치냉장고 | 1~2인, 김치 조금 | 200L대 | "1~2인 / 김치 소량, 사 먹는 편 / 뚜껑형 / 200L대" (표) | https://bestshop.lge.co.kr/story/insight/detail/IN10038000 |
| 김치냉장고 | 3인, 김장 조금 | 300L대 | "김장 소량 + 식재료 보관" 스탠드형 3도어 300L대 (표) | 같은 곳 |
| 김치냉장고 | 4인 이상, 김장 조금 | 300~400L대 | "스탠드형 300~400L대" (FAQ) | 같은 곳 |
| 김치냉장고 | 김장 많이 | 480~499L | "4도어 490L 전후를 권장" (FAQ), 표 480L대·490L대 | 같은 곳 |
| 세탁기 | 아기 (어른 빨래와 함께) | 21~24kg | "어른과 아기의 빨랫감을 함께 관리할 수 있는 넉넉한 용량" | https://www.lge.co.kr/story/home-curation/washing-machine-guide-for-baby-laundry |
| 세탁기 | 3인 이상 | 25kg 이상 | "대용량의 세탁기가 필요한 4인 이상 가구" · 3~4인 가이드의 제품이 모두 25kg | https://www.lge.co.kr/story/useful-tip/lg-washing-machines-guide · https://www.lge.co.kr/story/home-curation/washer-dryer-capacity-guide |
| 워시콤보 | 맞벌이 3인 이상 | 세탁 25kg 이상 | "육아와 업무로 24시간이 모자란 맞벌이 부부에게는 워시콤보를 추천" | https://www.lge.co.kr/story/home-curation/washer-dryer-capacity-guide |

가이드끼리 어긋나는 곳: 김치냉장고 3~4인은 표(480L대)와 FAQ(300~400L대)가 다르다. 김장을 조금 하면 FAQ, 많이 하면 490L 전후를 따른다.
에어컨·공기청정기는 카탈로그에 냉방·청정 면적 값이 없어 아직 넣지 않았다.
