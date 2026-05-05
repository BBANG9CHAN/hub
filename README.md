# hub

개인 자동화 허브. Git/WordPress/Telegram 어댑터와 Claude API 서비스를
이벤트 버스로 묶어 블로그 발행, 알림, 원격 제어를 통합한다.

## 문서

- 설계 개요: [`docs/architecture.md`](docs/architecture.md)
- 설계 결정 (ADR): [`docs/decisions.md`](docs/decisions.md)
- Claude Code 작업 지침: [`CLAUDE.md`](CLAUDE.md)
- 프롬프트 템플릿: [`prompts/`](prompts/)

## 상태

초기 설계 단계. `core/`, 어댑터, 서비스 구현 진행 중.
실행 가능한 명령은 구현 진행에 따라 추가 예정.

## 관련 리포

- [bbang9chan/blog](https://github.com/bbang9chan/blog) — 블로그 원고 저장소.
  hub로 발행하는 대상이자, 시리즈 "나만의 자동화 허브 만들기"의 원재료가 모이는 곳.
