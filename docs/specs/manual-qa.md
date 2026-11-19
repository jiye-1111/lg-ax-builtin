# 시연 전 수동 점검표

## 1. 설치
- [ ] `uv sync --extra dev` → `uv run pytest` 전부 통과
- [ ] `.env` 작성 (`MCP_HTTP_TOKEN`은 HTTP 쓸 때만)

## 2. 웹 흐름 (합성 샘플)
- [ ] `uv run lgb-api` → `http://localhost:8000/#/t` → 합성 샘플로 등록 → 벽 4·문창 2·가구 3
- [ ] w1 실측 5.195 / 2.395 / 1.6 저장 → 평면도 w1 초록
- [ ] 고객 화면: 주방(왼쪽 위 3.0×1.6m), 거실(아래쪽) 그리기 → 추천 카드 표시
- [ ] 실측 전에는 최고 "조건부", 실측 후 "적합" 나오는지

## 3. Blender (설치 PC)
- [ ] `.env`에 `BLENDER_BIN` 지정 → 새 프로젝트 등록 → `/api/health`에 경로 표시
- [ ] 3D HUD가 "Blender"인지, "렌더 이미지"가 Cycles 결과(가구 모델·창 구멍·마루 무늬)인지
- [ ] 가구를 옮겨도 3D가 바로 바뀌는지 (Blender는 렌더 때만 돈다)
- [ ] 실패하면 `storage/projects/<pid>/scene/blender.log` 확인 (폴백으로 계속 동작해야 함)

## 4. Claude Code (stdio)
- [ ] 저장소 폴더에서 `claude` 실행 → `/mcp`에 `lg-builtin` 연결됨
- [ ] "가장 최근 프로젝트 방 구조 알려 줘" → `get_room`
- [ ] "주방을 화이트 우드 톤 미니멀로 해 줘" → `set_style` → 웹 스타일 칸 2초 안에 갱신
- [ ] "주방에 들어가는 냉장고 추천해 줘" → `recommend` 결과와 웹 카드 판정이 같은지
- [ ] "벽은 따뜻한 화이트, 바닥은 밝은 오크로" → `apply_material` → 웹 3D 갱신
- [ ] "1도어 냉장고 배치하고 렌더해 줘" → `place_product`, `render` 이미지

## 5. Codex (stdio)
- [ ] 저장소 폴더에서 `codex` 실행 (프로젝트 `.codex/config.toml` 신뢰) → `/mcp`에 `lg-builtin`
- [ ] 4번과 같은 프롬프트 5개 → 같은 결과

## 6. HTTP (Claude 앱 커넥터 / Codex URL)
- [ ] `uv run python -m mcp_server --http` → 토큰 없이 호출하면 401
- [ ] 공개 주소(Q8 결정 후) + `MCP_ALLOWED_HOSTS` 설정 → Claude 앱 커스텀 커넥터, 요청 헤더 `Authorization: Bearer <토큰>`
- [ ] Codex `lg-builtin-http` 주석 해제 후 연결 (실패하면 stdio로 시연)

## 7. 시연 당일
- [ ] 사전 렌더·백업 영상, 발표자 계정 사용량 확인, 예비 계정 커넥터 등록
