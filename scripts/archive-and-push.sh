#!/usr/bin/env bash
# ADR-0015: 커밋 아카이브 후 squash 배치 푸시
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=0

usage() {
    echo "Usage: $(basename "$0") [-n]" >&2
    echo "  -n  dry-run: 대상 커밋 수와 로그 파일명만 출력" >&2
    exit 1
}

while getopts "n" opt; do
    case "$opt" in
        n) DRY_RUN=1 ;;
        *) usage ;;
    esac
done

BRANCH=$(git rev-parse --abbrev-ref HEAD)

# 슬래시 포함 브랜치명을 파일명용 문자열로 변환
BRANCH_SAFE="${BRANCH//\//_}"

# 업스트림 SHA 결정 (@{u} 우선, 없으면 origin/<branch> 시도)
UPSTREAM=""
if git rev-parse "@{u}" &>/dev/null; then
    UPSTREAM=$(git rev-parse "@{u}")
elif git rev-parse "origin/$BRANCH" &>/dev/null; then
    UPSTREAM=$(git rev-parse "origin/$BRANCH")
fi

if [[ -z "$UPSTREAM" ]]; then
    echo "오류: 업스트림을 찾을 수 없습니다." >&2
    echo "       첫 번째 푸시는 직접 실행하세요: git push origin $BRANCH" >&2
    exit 1
fi

COMMIT_COUNT=$(git rev-list --count "$UPSTREAM..HEAD")

if [[ "$COMMIT_COUNT" -eq 0 ]]; then
    echo "푸시할 커밋 없음"
    exit 0
fi

TIMESTAMP=$(date +"%Y-%m-%d_%H%M")
LOG_DIR=".local/commit-history"
LOG_FILE="$LOG_DIR/${TIMESTAMP}_${BRANCH_SAFE}.log"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run]"
    echo "  대상 커밋 수 : $COMMIT_COUNT"
    echo "  로그 파일명  : $LOG_FILE"
    exit 0
fi

mkdir -p "$LOG_DIR"
git log --pretty=fuller "$UPSTREAM..HEAD" > "$LOG_FILE"
echo "커밋 히스토리 저장: $LOG_FILE"

if [[ "$COMMIT_COUNT" -eq 1 ]]; then
    echo "커밋 1개 → squash 생략, 타임스탬프만 갱신 후 push"
    git commit --amend --no-edit --date="$(date -R)"
    git push origin "$BRANCH"
else
    TODAY=$(date +"%Y-%m-%d")
    BATCH_SUBJECT="batch: $TODAY"
    COMMIT_MSGS=$(git log --pretty=format:"- %s" --reverse "$UPSTREAM..HEAD")

    git reset --soft "$UPSTREAM"
    git commit -m "$BATCH_SUBJECT" -m "$COMMIT_MSGS"
    echo "Squash 완료: ${COMMIT_COUNT}개 → 1개 (\"$BATCH_SUBJECT\")"

    git push origin "$BRANCH"
fi

echo "Push 완료 → origin/$BRANCH"
