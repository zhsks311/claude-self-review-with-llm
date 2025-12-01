#!/bin/bash
# 최종 검열 스크립트 - Stop 이벤트 시 실행

# Plugin 모드 또는 직접 설치 모드 지원
HOOKS_DIR="${PLUGIN_DIR:-$HOME/.claude/hooks}"
PYTHON_PATH=$(which python3)

# stdin에서 Hook 입력 읽기
INPUT=$(cat)

# stage 정보 추가하여 오케스트레이터 호출
echo "{\"stage\": \"final\", \"hook_input\": $INPUT}" | "$PYTHON_PATH" "$HOOKS_DIR/review_orchestrator.py"
