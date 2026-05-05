# Architecture Decisions

## ADR-0001: 별도 리포 2개로 분리 (hub + blog)

**Status**: Accepted (2026-04-24)

**Context**: 도구 코드와 블로그 원고를 같이 관리할지 분리할지 결정 필요.

**Decision**: `hub`(도구)와 `blog`(원고)를 별도 GitHub 리포(`github.com/bbang9chan/hub`, `github.com/bbang9chan/blog`)로 분리.

**Reasons**:
- 관심사 분리 (도구 vs 데이터)
- hub의 재사용성 (다른 프로젝트에 가져다 쓸 수 있음)
- Git 히스토리 오염 방지
- 공개 범위 분리 가능 (예: blog public, hub private)
- 버전 관리 독립 (hub는 semver, blog는 발행 타임라인)

**Trade-offs**: 초기 세팅 약간 번거로움. blog가 hub의 존재만 알면 되도록 호출 방향 단방향 유지.

---

## ADR-0002: Python 메인 + 필요시 다른 언어 보조

**Status**: Accepted (2026-04-24)

**Context**: 단일 언어 vs 멀티 언어 결정.

**Decision**: Python 3.12+ 메인. 필요 시 Bash, Node.js 등 보조 스크립트는 `scripts/` 디렉토리에.

**Reasons**: 운영자 주력 언어, async 생태계 성숙, 관련 환경 경험 보유.

---

## ADR-0003: 하이브리드 실행 환경

**Status**: Accepted (2026-04-24)

**Context**: 로컬 PC, 서버, CI 중 어디서 실행할지 결정.

**Decision**: 하이브리드. 로컬 개발은 네이티브(`uv run`), 서버 상주는 Docker, CI는 GitHub Actions.

**Reasons**:
- 로컬 개발 시 디버깅 속도/핫리로드 우선
- 서버 배포 시 환경 재현성/관리 용이성 우선
- 같은 코드(어댑터/워크플로우)를 진입점만 바꿔서 양쪽에서 실행

**Implementation**: `cli.py`(로컬 일회성)와 `daemon.py`(서버 상주) 두 진입점 분리.

---

## ADR-0004: 어댑터 vs 서비스 구분

**Status**: Accepted (2026-04-24)

**Context**: 외부 시스템 연동 모듈을 어떻게 구조화할지 결정.

**Decision**: 두 개념으로 분리.
- **Adapter**: 외부 I/O (대부분 목적지 성격). Git, WordPress, Telegram. 이벤트 pub/sub.
- **Service**: 내부 처리 도구. Claude API, Markdown 변환, 이미지 처리. 직접 함수 호출.

**Reasons**:
- LLM이나 변환 도구는 "이벤트 목적지"가 아니라 "워크플로우 중간에 호출되는 도구"
- pub/sub와 직접 호출의 패턴을 섞으면 혼란

**Trade-offs**: 두 추상화를 둬야 하는 학습 비용. 다만 역할이 명확히 달라서 실용적.

---

## ADR-0005: 이벤트 버스 도입 (pub/sub)

**Status**: Accepted (2026-04-24)

**Context**: 어댑터 간 결합도 관리 방식 결정.

**Decision**: 어댑터가 다른 어댑터를 직접 호출하지 않고, 코어의 이벤트 버스에 publish하면 구독자가 처리.

**Reasons**:
- 새 구독자(예: Slack 어댑터) 추가 시 기존 코드 수정 불필요
- 테스트 용이 (이벤트 발행만 검증)
- 워크플로우와 어댑터의 책임 분리

**Trade-offs**: 디버깅 시 흐름 추적이 직접 호출보다 약간 복잡. 로깅으로 보완.

---

## ADR-0006: ClaudeService 추가 (LLM 통합)

**Status**: Accepted (2026-04-24)

**Context**: Claude API로 블로그 초안 생성 등 LLM 활용 필요.

**Decision**: `services/claude_service.py`로 추가. 어댑터가 아닌 서비스로 분류.

**Reasons**: ADR-0004의 분류 원칙에 따름. LLM 호출은 워크플로우 중간 단계.

**확장 가능성**: 나중에 두 번째 LLM(Ollama 등) 붙일 때 `LLMService` Protocol로 추상화. **지금은 추상화하지 않음 (YAGNI)**.

**프롬프트 관리**: `prompts/` 디렉토리에 파일로. Git 버전 관리.

---

## ADR-0007: Git 호스팅은 GitHub

**Status**: Accepted (2026-04-24)

**Context**: GitHub vs GitLab vs 자체 Gitea 결정.

**Decision**: GitHub. CI는 GitHub Actions, 컨테이너 레지스트리는 GHCR.

**Reasons**: 가장 익숙. 개인 프로젝트에 자체 호스팅 운영 부담은 과함.

---

## ADR-0008: WordPress는 셀프 호스팅 (시점: 시리즈 2편)

**Status**: Accepted (2026-04-24)

**Context**: 현재 WordPress 미설치. 어떻게 도입할지 결정.

**Decision**: Docker 기반 셀프 호스팅. 시리즈 2편 작업하면서 같이 구축. WP REST API 활성화 + 인증 플러그인(JWT 또는 Application Passwords).

**개발 순서**: hub의 WP 어댑터는 인터페이스만 먼저 두고 모킹. WP 구축 후 실제 연동.

---

## ADR-0009: Claude Project 2개로 분리 (hub + blog)

**Status**: Accepted (2026-04-24)

**Context**: 코딩과 블로그 글쓰기를 한 Claude Project에서 다룰지 분리할지.

**Decision**: `bbang9chan-hub`(코딩 두뇌)와 `bbang9chan-blog`(글쓰기 두뇌) 별도 Project.

**Reasons**:
- 페르소나 충돌 방지 (YAGNI vs 스토리텔링)
- Knowledge 오염 방지
- 시스템 프롬프트 명확화

**시너지**: hub의 decisions.md/log.md/struggles.md를 blog Knowledge에도 업로드 → 시리즈 글 원재료로 활용.

---

## ADR-0010: 실제 구현은 Claude Code

**Status**: Accepted (2026-04-24)

**Context**: 코드 생성 도구 선택.

**Decision**: 실제 파일 생성/수정은 Claude Code로. Claude Project는 설계 논의 전용.

**도구 분담**:
- Claude Project (hub) → 두뇌 (설계, 결정)
- Claude Code → 손 (실제 코드)
- Cowork (선택) → 잡일 (blog 리포 정리, 스크린샷 관리)

**중요**: hub 리포에 `CLAUDE.md` 두기. 매번 컨텍스트 설명 안 해도 되도록.

---

## ADR-0011: 휴대용 환경(USB 부트스트랩)은 보류

**Status**: Deferred (2026-04-24)

**Context**: 새 PC에서도 동일한 환경을 빠르게 복구할 수 있도록 USB에 부트스트랩 스크립트와 시크릿(.env, SSH 키 등)을 두는 방안 논의.

**Decision**: 보류. hub 코어/어댑터/서비스 구현이 우선. 실제로 다른 PC에서 환경을 구축해야 할 일이 생기는 시점에 만들기로.

**Reasons**:
- 지금 만들어도 검증할 실제 시나리오가 없음 (YAGNI)
- 실제 필요 시점에 만들어야 OS별 진짜 함정들을 발견할 수 있음 → 오히려 좋은 글감
- core가 안정되기 전에 운영 도구부터 만드는 건 우선순위 역전

**설계 메모 (재개 시 참고)**:
- 구조: Docker 엔진은 호스트 설치 전제. USB에는 `bootstrap/`, `secrets/`, `docs/recovery-runbook.md`만.
- USB 자체는 암호화 파티션(VeraCrypt/BitLocker To Go)에 두기.
- 부트스트랩은 OS별 분기 (Linux/Mac bash, Windows PowerShell).
- 목표: 새 PC에서 15분 안에 `docker compose up`까지.

**재개 트리거**: 새 PC 환경 구축이 실제로 필요해지는 순간, 또는 시리즈 5편 본편 마치고 보너스로 작성하고 싶어질 때.

---

## ADR-0012: 리포는 public, 시크릿은 다중 방어

**Status**: Accepted (2026-04-24)

**Context**: hub 리포를 private으로 둘지 public으로 둘지 결정.

**Decision**: `hub`와 `blog` 리포 모두 GitHub **public**. 단, blog의 개인 작업 공간(`drafts/`, `log.md`, `struggles.md` 등)은 `.gitignore` 또는 별도 private 리포로 분리.

**Reasons**:
- 블로그 시리즈 연계: "전체 코드는 여기" 링크 한 방으로 끝남
- GitHub Actions 무료 분량 무제한 (private은 월 2,000분 제한)
- GHCR 컨테이너 이미지 용량 제한 없음
- 포트폴리오 자료로 활용 가능
- 만들어가는 과정의 지저분함 자체가 시리즈 콘텐츠

**안전장치 (hub 초기 세팅 시 Claude Code로 구성)**:
- `.gitignore` 빡빡하게 (`.env`, `config.local.yaml`, `secrets/`, `data/` 등)
- `pre-commit` + `gitleaks` 훅으로 시크릿 스캔
- GitHub Settings → Security에서 Secret scanning + Push protection + Dependabot alerts 활성화

**Trade-offs**: 시크릿 실수 시 즉시 공개 리스크. 위 안전장치로 상쇄.

**향후 전환 조건**: 업무 관련 코드/구조가 혹시라도 섞일 일이 생기면 그 시점에 즉시 private 전환 검토.

---

## ADR-0013: public 문서는 탈개인화

**Status**: Accepted (2026-04-24)

**Context**: hub/blog 리포가 public이므로, 리포에 포함되는 문서(`docs/`, `prompts/`, `CLAUDE.md`, `series/` 등)에서 개인 특정 정보를 어느 수준까지 제거할지 결정 필요. 단, Claude Project 지침은 운영자 개인 공간이므로 별도 취급.

**Decision**: 두 영역으로 분리하여 관리.

**public 리포에 들어가는 문서**(`docs/decisions.md`, `docs/architecture.md`, `prompts/blog_post_generation.md`, `CLAUDE.md`, `series/my-hub/*.md` 등):
- 운영자 이름, 소속, 업계, 지역 등 특정 정보 제거
- 운영자의 호칭(이름 등) → "운영자" 또는 주어 생략
- 블로그 URL 본문에 노출 금지 (리포 이름 범위 내에서만)
- 과거 사이드 프로젝트 실제 이름(연금저축 리밸런싱, 뉴스 크롤러 등) → 일반화된 예시로
- 명령어 예시의 특정 파일명 → 일반 placeholder

**Claude Project 지침**(`bbang9chan-hub`, `bbang9chan-blog`의 시스템 프롬프트):
- 운영자 맥락, 호칭 규칙, 블로그 컨셉, 과거 프로젝트 이력 등 상세 유지
- Claude가 맥락을 정확히 잡아야 답변 품질이 나오므로 탈개인화하지 않음
- 이 지침은 Claude Project 소유자만 볼 수 있으므로 안전

**Reasons**:
- public 리포의 코드/문서는 블로그 시리즈 링크, 포트폴리오 자료로 활용됨. 거기에 운영자의 실제 소속·업계 정보가 박혀 있으면 회사-개인 경계가 흐려짐
- Claude Project는 개인 공간이고 Claude 응답 품질 직결. 탈개인화 시 "그냥 일반 Claude"로 품질 저하

**Trade-offs**: 같은 프로젝트의 문서에 두 가지 표현(public: 일반화된 주어 / Project 지침: 운영자 실명 호칭)이 공존. 혼란 가능성 있으나 파일 위치로 구분되므로 실용상 문제 없음.

**유지 규칙**: 새 문서 추가 시 반드시 "이 파일이 public 리포에 들어가는지"를 먼저 판단. 들어간다면 ADR-0013 수준으로 탈개인화 후 커밋.

---

## ADR-0014: 네이밍 규칙 — 리포는 짧게, Claude Project는 풀네임

**Status**: Accepted (2026-04-24)

**Context**: GitHub 사용자명이 `bbang9chan`이므로 리포 이름에 `bbang9chan-` 접두사를 붙이면 `bbang9chan/bbang9chan-hub`처럼 중복이 생김. 반면 Claude Project는 사용자 전체 Project 목록에서 구분되어야 하므로 접두사가 도움이 됨. 원고 저장소는 용도를 직관적으로 드러내는 `blog`로 명명.

**Decision**:

| 대상 | 이름 |
|------|------|
| GitHub 리포 | `bbang9chan/hub`, `bbang9chan/blog` |
| Claude Project | `bbang9chan-hub`, `bbang9chan-blog` |
| 문서 안에서 리포 언급 | `hub`, `blog` (짧게) |
| 문서 안에서 Claude Project 언급 | `bbang9chan-hub`, `bbang9chan-blog` (풀네임) |

**Reasons**:
- 리포: URL에 이미 `bbang9chan/`이 포함되어 중복 불필요. 짧을수록 명령어·경로에서 읽기 편함
- `blog`는 저장소 용도("블로그 원고")를 즉시 드러냄. 범용어인 `content`보다 의도가 분명함
- Claude Project: 운영자 계정에 다른 Project들도 쌓일 수 있음. 접두사로 식별 용이
- 문서 표현: 맥락에 따라 자동으로 "리포 얘기"와 "Project 얘기"가 구분됨

**Trade-offs**:
- 리포(`blog`)와 Project(`bbang9chan-blog`)가 같은 단어를 공유 → 대화에서 "blog 수정"이 어느 쪽인지 맥락 판단 필요. 실제론 맥락으로 거의 구분되며 이 ADR로 규칙이 명문화됨
- 리포와 Project 이름 길이가 다름 → 문서 표기 규칙을 위 표대로 통일

**적용 예시**:
- "`hub` 리포 루트에 `CLAUDE.md` 배치" (리포 얘기)
- "`bbang9chan-hub` Project Knowledge에 업로드" (Project 얘기)
- "`blog` 리포의 `series/my-hub/series-plan.md`" (리포 얘기)
- "`bbang9chan-blog` Project에서 글 작성" (Project 얘기)

---

## ADR-0015: 커밋은 수시, 푸시는 squash 배치, 원본 히스토리는 로컬 아카이브

**Status**: Accepted (2026-04-24)

**Context**: `hub`/`blog` 모두 public 리포이므로 커밋 타임스탬프와 히스토리가 그대로 외부에 노출된다. 반면 로컬의 의미 단위 커밋 히스토리는 시리즈 글 원재료로 가치가 있어 완전히 버리기는 아깝다. 공개 타임라인이 지나치게 잘게 쪼개지는 것을 피하면서 작업 맥락은 보존할 방법이 필요.

**Decision**: hub/blog 양쪽 리포에 동일 적용. 3단 구조로 운영.

1. **로컬 커밋**: 의미 단위로 수시 진행 (상세 메시지, 원본 타임스탬프 유지)
2. **푸시 직전 아카이브**: 원격 이후 누적된 커밋을 `.local/commit-history/`에 덤프. 이 디렉토리는 `.gitignore` 처리
3. **Squash 배치 푸시**: 누적 커밋을 하나로 합쳐 푸시 시점 타임스탬프로 원격에 반영

**Scope**:
- `hub`: 코드 작업 타임라인 정제
- `blog`: 예약 발행 중심이라 배치 푸시와 궁합 좋음. 수정사항 반영 지연 허용 가능

**Reasons**:
- Public 타임라인은 정제된 배치 단위로만 노출
- 원본 히스토리는 로컬 아카이브로 보존 → 시리즈 글 원재료 확보
- `struggles.md`/`log.md`와 상호보완 (공식 기록 + 기계적 기록)
- 스크립트 한 개로 자동화 가능

**Trade-offs**:
- `.local/` 디렉토리는 Git으로 백업되지 않음 → 별도 백업 경로 필요 (NAS 동기화, 또는 별도 private 리포)
- Squash로 원격 커밋이 의미 단위보다 크게 묶임 → 원격만 보면 세부 맥락 파악 어려움. 대신 로컬 아카이브와 `struggles.md`를 참조

**Implementation notes**:
- 아카이브+푸시는 `scripts/archive-and-push.sh`로 구현 예정 (hub 초기 세팅 시)
- 파일명 규칙: `.local/commit-history/YYYY-MM-DD_HHMM_<branch>.log`
- `.gitignore`에 `.local/` 반드시 포함
- 긴급 hotfix는 예외로 평소처럼 `git push`
- 자동 스케줄러 구현은 YAGNI — 수동 운영으로 시작

---

## ADR-0016: blog 리포의 개인 작업 공간은 .gitignore (A안)

**Status**: Accepted (2026-04-29)

**Context**: ADR-0012는 blog 리포의 개인 작업 공간(`drafts/`, `log.md`,
`struggles.md` 등)을 ".gitignore 또는 별도 private 리포로 분리"한다고만 명시.
한편 series-plan.md의 원재료 디렉토리 구조에는 `drafts/`가 "Git 추적"으로
표시되어 있어 두 문서가 모순. 초기 커밋 시점에 정확한 처리를 확정할 필요.

**Decision**: blog 리포의 다음 경로를 모두 `.gitignore` 처리한다.

- `series/*/log.md`        — 시간순 개발 일지
- `series/*/struggles.md`  — 삽질/실패/해결 기록
- `series/*/drafts/`       — Claude가 뽑은 초안 보관 디렉토리

공개되는 것은 `series-plan.md`(시리즈 메타)와 hub의 사본인 `decisions.md`,
그리고 발행이 결정되어 별도 위치(예: `posts/`)로 이동시킨 정제된 글뿐이다.

**Reasons**:
- ADR-0012(public 안전장치) 정신과 일치. 의도치 않은 노출 위험 최소화
- 처음에 빼두면 나중에 `git add -f`로 개별 파일을 끌어올릴 수 있음.
  반대 방향(공개했다가 빼기)은 Git 히스토리에 영원히 남아 회복 불가
- 초안에는 운영자의 톤/일정/특정 인물 등이 정제 전 상태로 남기 쉬움

**Trade-offs**:
- 시리즈 글 원재료가 로컬에만 존재 → 별도 백업 경로 필요 (NAS 동기화,
  또는 별도 private 리포). ADR-0015의 `.local/` 백업 정책과 동일한 부담
- 시리즈 글 작성 시 GitHub 링크로 원재료를 인용할 수 없음.
  대신 글 본문에 인용으로 녹여야 함

**Supersedes**: series-plan.md 원재료 디렉토리 구조의 "drafts/ Git 추적" 표기.
series-plan.md는 이 ADR에 맞춰 다음 갱신 시 표기 수정.

**향후 전환 조건**: drafts/ 중 정제된 일부를 공개로 전환하고 싶은 시점에는
별도 디렉토리(예: `series/*/drafts-public/`)를 만들어 그쪽만 추적하는 방식으로
점진적 공개. 전체 디렉토리를 한 번에 공개로 전환하지 않는다.

## ADR 추가 양식

새 결정이 생기면 아래 템플릿으로 추가:

```
## ADR-NNNN: 제목

**Status**: Accepted | Superseded by ADR-NNNN | Deprecated (날짜)

**Context**: 어떤 상황에서 결정이 필요했는지

**Decision**: 무엇을 결정했는지 (구체적으로)

**Reasons**: 왜 그렇게 결정했는지

**Trade-offs**: 포기한 것, 향후 부담 (있으면)
```
