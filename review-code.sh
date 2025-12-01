#!/bin/bash
# 코드 검열 스크립트 - Edit/Write 도구 호출 후 실행

# Plugin 모드 또는 직접 설치 모드 지원
HOOKS_DIR="${PLUGIN_DIR:-$HOME/.claude/hooks}"
PYTHON_PATH=$(which python3)

# stdin에서 Hook 입력 읽기
INPUT=$(cat)

# 파일 확장자 필터링 (허용된 확장자만 검열)
FILE_PATH=$(echo "$INPUT" | "$PYTHON_PATH" -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# 설정 파일에서 허용 확장자 확인
ALLOWED_EXTENSIONS=$("$PYTHON_PATH" -c "
import json
from pathlib import Path
config_path = Path('$HOOKS_DIR/config.json')
if config_path.exists():
    config = json.loads(config_path.read_text())
    print(' '.join(config.get('security', {}).get('allowed_file_extensions', [])))
" 2>/dev/null)

# 파일 확장자 체크
if [ -n "$FILE_PATH" ] && [ -n "$ALLOWED_EXTENSIONS" ]; then
    EXT=".${FILE_PATH##*.}"
    if ! echo "$ALLOWED_EXTENSIONS" | grep -q "$EXT"; then
        # 허용되지 않은 확장자 - 검열 스킵
        echo '{"continue": true}'
        exit 0
    fi
fi

# stage 정보 추가하여 오케스트레이터 호출
echo "{\"stage\": \"code\", \"hook_input\": $INPUT}" | "$PYTHON_PATH" "$HOOKS_DIR/review_orchestrator.py"
