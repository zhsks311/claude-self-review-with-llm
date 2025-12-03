#!/bin/bash
# 완료 검토 스크립트 - TodoWrite에서 모든 todo가 완료될 때 실행
# Claude 셀프 리뷰 + 외부 LLM 검토 트리거

HOOKS_DIR="${PLUGIN_DIR:-$HOME/.claude/hooks}"
PYTHON_PATH=$(which python3)
LOG_FILE="$HOOKS_DIR/logs/hook-debug.log"

# 디버그 로그
echo "[$(date '+%Y-%m-%d %H:%M:%S')] review-completion.sh 실행됨" >> "$LOG_FILE"

# stdin에서 Hook 입력 읽기
INPUT=$(cat)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] INPUT 수신 (길이: ${#INPUT})" >> "$LOG_FILE"

# completion_orchestrator 호출
echo "$INPUT" | "$PYTHON_PATH" "$HOOKS_DIR/completion_orchestrator.py"
