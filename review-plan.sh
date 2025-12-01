#!/bin/bash
# 계획 검열 스크립트 - TodoWrite 도구 호출 후 실행

# Plugin 모드 또는 직접 설치 모드 지원
HOOKS_DIR="${PLUGIN_DIR:-$HOME/.claude/hooks}"
PYTHON_PATH=$(which python3)
LOG_FILE="$HOOKS_DIR/logs/hook-debug.log"

# 디버그 로그
echo "[$(date '+%Y-%m-%d %H:%M:%S')] review-plan.sh 실행됨" >> "$LOG_FILE"

# stdin에서 Hook 입력 읽기
INPUT=$(cat)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] INPUT: $INPUT" >> "$LOG_FILE"

# stage 정보 추가하여 오케스트레이터 호출
echo "{\"stage\": \"plan\", \"hook_input\": $INPUT}" | "$PYTHON_PATH" "$HOOKS_DIR/review_orchestrator.py"
