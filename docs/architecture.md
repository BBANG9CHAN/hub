# hub Architecture

## 한 줄 요약

이벤트 버스를 중심에 둔 어댑터/서비스 분리 구조. 같은 코드를 로컬(CLI)과 서버(Daemon) 양쪽에서 실행할 수 있도록 진입점만 분리.

## 구성 요소 다이어그램

```
                    ┌─────────────────────────┐
                    │         Core            │
                    │  ┌──────┐  ┌────────┐   │
                    │  │ Bus  │  │ Config │   │
                    │  └──────┘  └────────┘   │
                    │  ┌──────┐  ┌────────┐   │
                    │  │Logger│  │Registry│   │
                    │  └──────┘  └────────┘   │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌────────────┐  ┌──────────┐  ┌────────────┐
       │  Adapters  │  │ Services │  │ Workflows  │
       │  (외부 I/O) │  │ (내부 도구) │  │  (시나리오) │
       ├────────────┤  ├──────────┤  ├────────────┤
       │ Git        │  │ Claude   │  │ DraftPost  │
       │ WordPress  │  │ Markdown │  │ PublishPost│
       │ Telegram   │  │ Image    │  │ ErrorNotify│
       └────────────┘  └──────────┘  └────────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
              ┌──────────┐      ┌──────────┐
              │   CLI    │      │  Daemon  │
              │ (로컬용)  │      │ (서버용)  │
              └──────────┘      └──────────┘
```

## 디렉토리 구조

```
hub/
├── pyproject.toml              # uv 권장
├── .env.example                # 비밀값 템플릿
├── .gitignore
├── README.md
├── CLAUDE.md                   # Claude Code 작업 지침
├── docs/
│   ├── architecture.md         # 이 파일
│   └── decisions.md            # ADR
├── config/
│   ├── config.yaml             # 메인 설정 (Git 추적)
│   └── config.local.yaml       # 환경별 오버라이드 (.gitignore)
├── prompts/                    # ClaudeService용 프롬프트 (Git 추적)
│   ├── blog_post_generation.md
│   └── ...
├── src/hub/
│   ├── __init__.py
│   ├── core/
│   │   ├── config.py           # Pydantic 설정 로더
│   │   ├── bus.py              # 이벤트 버스
│   │   ├── logger.py           # 구조화 로깅
│   │   └── registry.py         # 어댑터/서비스 등록
│   ├── adapters/
│   │   ├── base.py             # Adapter 추상 클래스
│   │   ├── git_adapter.py
│   │   ├── wordpress_adapter.py
│   │   └── telegram_adapter.py
│   ├── services/
│   │   ├── claude_service.py
│   │   ├── markdown_service.py
│   │   └── image_service.py
│   ├── workflows/
│   │   ├── draft_post.py
│   │   ├── publish_post.py
│   │   └── error_notify.py
│   ├── cli.py                  # typer 기반 CLI
│   └── daemon.py               # 서버 상주 진입점
├── tests/
│   ├── unit/
│   └── integration/
├── docker/
│   ├── Dockerfile              # multi-stage
│   └── docker-compose.yml      # daemon 모드
├── scripts/                    # Python 외 보조 스크립트
└── .github/workflows/
    ├── ci.yml                  # test + lint
    └── release.yml             # 이미지 빌드 → GHCR
```

## 핵심 개념

### Adapter vs Service

| 구분 | Adapter | Service |
|------|---------|---------|
| 역할 | 외부 시스템과의 I/O | 내부 처리 도구 |
| 예시 | Git, WordPress, Telegram | Claude API, Markdown 변환 |
| 호출 | 이벤트 pub/sub | 직접 함수 호출 |
| 추상 클래스 | `adapters/base.py:Adapter` | `services/base.py` (필요 시) |

### 이벤트 버스

어댑터는 다른 어댑터를 직접 호출하지 않는다. `bus.publish("post.published", payload)` 식으로 이벤트를 발행하고, 관심 있는 구독자가 처리한다.

**이벤트 명명 규칙**: `<domain>.<event>` (예: `git.committed`, `post.published`, `error.occurred`)

### 설정 3단 계층

1. `config/config.yaml` — 공통 기본값 (Git 추적)
2. `config/config.local.yaml` — 환경별 오버라이드 (Git 무시)
3. `.env` — 비밀값 (Git 무시)

Pydantic이 셋을 병합해 단일 객체로 제공. 폐쇄망/하이브리드 환경 모두 같은 코드.

### CLI vs Daemon

- **CLI** (`cli.py`): 일회성 명령. `hub publish posts/foo.md` 같은 식
- **Daemon** (`daemon.py`): 서버 상주. Telegram 웹훅 수신 + 스케줄러 + 어댑터 healthcheck

같은 어댑터/워크플로우 코드를 공유. 환경 차이는 config로만 흡수.

## 발행 플로우 예시

```
$ hub publish blog/posts/2026-04-24-my-post.md

┌─ 1. PublishPost 워크플로우 시작
│
├─ 2. Git Adapter
│     → blog 리포에 git add/commit/push
│     → bus.publish("git.committed", {sha, files})
│
├─ 3. Markdown Service
│     → MD를 WP 블록 JSON으로 변환
│
├─ 4. WordPress Adapter
│     → REST API POST /wp/v2/posts
│     → bus.publish("post.published", {post_id, url})
│
└─ 5. Telegram Adapter (post.published 구독)
      → "✅ 발행 완료: {title}\n{url}"
```

## 초안 생성 플로우 예시

```
$ hub draft --from experiences/my-experience.txt --topic "문제 상황 제목"

┌─ 1. DraftPost 워크플로우 시작
│
├─ 2. Claude Service
│     → 경험 덤프 + topic + 시스템 프롬프트(prompts/blog_post_generation.md)
│     → 초안 텍스트 반환
│
├─ 3. 파일 저장
│     → blog/posts/YYYY-MM-DD-slug.md
│     → bus.publish("draft.created", {path, title})
│
└─ 4. Telegram Adapter (draft.created 구독)
      → "✍️ 초안 준비됨: 문제 상황 제목"
```

## Docker 전략

### Multi-stage Dockerfile

```
[builder stage]
  - python:3.12-slim 기반
  - uv 설치
  - pyproject.toml만 먼저 COPY → 의존성 설치 (레이어 캐싱)
  - 소스 COPY → 패키지 설치

[runtime stage]
  - python:3.12-slim 기반
  - non-root user 생성
  - builder에서 site-packages만 복사
  - ENTRYPOINT는 hub 명령
```

### 실행 모드별 명령

| 상황 | 명령 |
|------|------|
| 로컬 개발 | `uv run hub publish posts/x.md` |
| 로컬 일회성 (검증) | `docker run --rm hub publish posts/x.md` |
| 서버 상주 | `docker compose up -d` |
| CI 발행 | GitHub Actions가 이미지 pull 후 publish 명령 |

## 의존성 (초기 추정)

- `pydantic>=2.0` — 설정/DTO
- `httpx` — 비동기 HTTP (WP, Telegram, Claude)
- `anthropic` — Claude SDK (선택, httpx 직접 호출도 가능)
- `python-telegram-bot` 또는 직접 httpx
- `gitpython` — Git 조작
- `typer` — CLI
- `pyyaml` — config
- `tenacity` — 재시도
- `structlog` — 구조화 로깅
- `pytest`, `pytest-asyncio`, `respx` — 테스트
