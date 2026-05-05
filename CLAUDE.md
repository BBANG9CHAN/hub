# CLAUDE.md - hub

## Project Summary

개인 자동화 허브. Git/WordPress/Telegram 어댑터와 Claude API 서비스를 이벤트 버스로 묶어
블로그 발행, 알림, 원격 제어를 통합한다.

상세 설계: `docs/architecture.md`
설계 결정 근거: `docs/decisions.md`

## Architecture Rules

- `src/hub/adapters/`: 외부 I/O. 이벤트 pub/sub. 새 어댑터는 `adapters/base.py:Adapter` 상속.
- `src/hub/services/`: 내부 도구. 직접 호출. (Claude API, MD 변환, 이미지 처리 등)
- `src/hub/workflows/`: 어댑터+서비스 조합 시나리오. 워크플로우는 어댑터를 직접 호출하지 말고 이벤트로 트리거.
- `src/hub/core/`: config/bus/logger/registry. 비즈니스 로직 두지 말 것.
- `cli.py` (typer) = 로컬 진입점. `daemon.py` = 서버 상주 진입점.

## Coding Conventions

- Python 3.12+. **async 우선** (모든 어댑터/서비스는 async).
- 타입 힌트 필수. `from __future__ import annotations` 사용.
- 설정/DTO는 모두 **Pydantic v2**.
- HTTP 호출은 **httpx** (requests 금지).
- 재시도/백오프는 **tenacity**.
- 로깅은 **structlog**. `print` 금지.
- 비밀값은 절대 코드/Git에 두지 말 것. `.env` 또는 환경변수로만.
- 한국어 주석/문서 OK. 식별자는 영어.

## Event Naming Convention

`<domain>.<event>` 형태. 예시:

- `git.committed`, `git.pushed`
- `post.draft_created`, `post.published`
- `error.occurred`
- `telegram.command_received`

## Adapter/Service 추가 시 체크리스트

새 어댑터:
1. `adapters/base.py:Adapter` 상속
2. `name`, `healthcheck()`, `start()`, `stop()` 구현
3. `core/registry.py`에 등록
4. `tests/unit/adapters/test_<name>_adapter.py` 추가 (httpx는 respx로 모킹)
5. `docs/decisions.md`에 도입 이유 한 줄

새 서비스:
1. `services/` 아래 파일 생성
2. 단일 책임 유지 (LLM 호출, 변환, 외부 도구 실행 등 한 가지만)
3. 테스트 추가
4. 외부 API면 비용/레이트리밋 고려

새 워크플로우:
1. `workflows/` 아래 파일 생성
2. 어댑터/서비스를 조합만 하고 비즈니스 로직 직접 두지 말 것
3. 이벤트 발행으로 후속 동작 트리거
4. CLI 명령으로 노출 (`cli.py`에 등록)

## Testing

- `pytest`, `pytest-asyncio`, `respx`(httpx 모킹) 사용.
- 외부 API 호출은 항상 모킹. 통합 테스트는 별도 마커(`@pytest.mark.integration`).
- 새 기능에 테스트 같이 작성.
- `uv run pytest` 통과해야 커밋.

## Common Commands

```bash
# 의존성 설치
uv sync

# CLI 실행
uv run hub publish blog/posts/foo.md
uv run hub draft --from experiences/x.txt --topic "제목"

# 테스트
uv run pytest
uv run pytest -m "not integration"  # 단위 테스트만

# 린트/포맷
uv run ruff check .
uv run ruff format .

# 타입 체크
uv run mypy src/

# Docker (서버 모드)
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml logs -f
```

## Git Conventions

- 커밋 메시지에 `Co-Authored-By` 트레일러 추가하지 말 것.

## Session Conventions

푸시 완료 후 세션을 마칠 때:

1. 이번 세션에서 한 작업을 한두 줄로 요약.
2. 다음 세션 시작 방법 안내 — 아래 형식으로:

```
다음 세션 시작 시 이렇게 말해주세요:
"[다음에 할 작업 한 줄 설명]. CLAUDE.md와 docs/decisions.md 최신 ADR 참고해서 진행해줘."
```

## What NOT to do

- 어댑터 안에서 다른 어댑터 직접 호출 → 이벤트 버스 사용
- 워크플로우에 비즈니스 로직 → 서비스로 추출
- 새 추상화 미리 만들기 (YAGNI) → 두 번째 사례 생기면 그때 추출
- `print()` → `structlog` 사용
- 동기 HTTP → 비동기로 (`httpx.AsyncClient`)
- 비밀값 코드/Git에 → `.env` 또는 환경변수
- 한 PR/커밋에 여러 관심사 섞기 → 작게 끊기

## Reference Files

설계 문서가 충돌할 땐 다음 우선순위:
1. `docs/decisions.md` (가장 최근 ADR이 진실)
2. `docs/architecture.md`
3. 이 파일 (CLAUDE.md)
