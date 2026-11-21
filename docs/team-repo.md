# 팀 저장소 동기화

팀 프로젝트 저장소: https://github.com/2Jaegon/LG_P3_digitaltwin

팀 저장소는 사람마다 브랜치를 하나씩 쓰는 방식이다 (`jaegon`, `jiyeonson`, `taeboshim`, `yumin`, ...).
HouseTwin 작업은 **`jiye` 브랜치**에 올린다. 팀 저장소 `main`에는 직접 올리지 않는다.

- 기준은 이 저장소(jiye-1111/lg-ax-builtin)의 `main`이다. 여기서 PR을 머지한 뒤 팀 브랜치를 맞춘다.
- `jiye` 브랜치는 이 저장소 `main`과 커밋 이력이 그대로 같다. 팀 브랜치에서 따로 커밋하지 않는다(다음 동기화 때 밀리지 않게).
- 팀 저장소 main과는 이력이 이어져 있지 않아서, 나중에 팀 main으로 합칠 때는 팀원들과 정한 방식(폴더로 넣기 등)으로 따로 PR을 만든다.

## 올리는 방법

```bash
# 리눅스/맥, 클라우드
scripts/sync-team.sh
```

Windows(C:\lg-ax-builtin)에서는 `scripts\sync-team.bat`를 더블클릭한다.

처음 한 번만 `team` 원격이 추가되고, 이후에는 `git push team origin/main:refs/heads/jiye`와 같다.
팀 저장소에 쓰기 권한(collaborator)이 있는 GitHub 계정으로 로그인돼 있어야 한다.
