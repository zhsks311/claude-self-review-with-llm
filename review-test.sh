#!/bin/bash
# 테스트 검열 스크립트 - Bash 도구에서 테스트 실행 후 실행

# Plugin 모드 또는 직접 설치 모드 지원
HOOKS_DIR="${PLUGIN_DIR:-$HOME/.claude/hooks}"
PYTHON_PATH=$(which python3)

# stdin에서 Hook 입력 읽기
INPUT=$(cat)

# 테스트 관련 명령어인지 확인
COMMAND=$(echo "$INPUT" | "$PYTHON_PATH" -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)

# 테스트 명령어 패턴 (gradle, maven, npm, pytest 등)
TEST_PATTERNS="test|spec|jest|pytest|mvn test|gradle test|npm test|yarn test"

if ! echo "$COMMAND" | grep -qiE "$TEST_PATTERNS"; then
    # 테스트가 아닌 명령어 - 검열 스킵
    echo '{"continue": true}'
    exit 0
fi

# stage 정보 추가하여 오케스트레이터 호출
echo "{\"stage\": \"test\", \"hook_input\": $INPUT}" | "$PYTHON_PATH" "$HOOKS_DIR/review_orchestrator.py"
