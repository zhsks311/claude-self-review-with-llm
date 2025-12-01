#!/bin/bash
# Claude Code 자기검열 시스템 설치 스크립트

set -e

HOOKS_DIR="$HOME/.claude/hooks"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🔧 Claude Code 자기검열 시스템 설치 중..."

# 1. 디렉토리 생성
echo "📁 디렉토리 생성..."
mkdir -p "$HOOKS_DIR"/{state,logs,adapters,prompts}

# 2. Python 파일 복사
echo "🐍 Python 모듈 복사..."
cp "$SCRIPT_DIR/review_orchestrator.py" "$HOOKS_DIR/"
cp "$SCRIPT_DIR/state_manager.py" "$HOOKS_DIR/"
cp "$SCRIPT_DIR/security.py" "$HOOKS_DIR/"
cp "$SCRIPT_DIR/adapters/"*.py "$HOOKS_DIR/adapters/"

# 3. Shell 스크립트 복사 및 실행 권한
echo "📜 Shell 스크립트 복사..."
cp "$SCRIPT_DIR/review-"*.sh "$HOOKS_DIR/"
cp "$SCRIPT_DIR/collect-project-context.sh" "$HOOKS_DIR/"
chmod +x "$HOOKS_DIR/"*.sh

# 4. 프롬프트 템플릿 복사
echo "📝 프롬프트 템플릿 복사..."
cp "$SCRIPT_DIR/prompts/"*.txt "$HOOKS_DIR/prompts/"

# 5. 설정 파일 복사 (기존 설정 백업)
echo "⚙️ 설정 파일 복사..."
if [ -f "$HOOKS_DIR/config.json" ]; then
    cp "$HOOKS_DIR/config.json" "$HOOKS_DIR/config.json.backup"
    echo "   기존 config.json을 config.json.backup으로 백업"
fi
cp "$SCRIPT_DIR/config.json" "$HOOKS_DIR/"

# 6. settings.json에 hooks 추가
SETTINGS_FILE="$HOME/.claude/settings.json"
echo "🔗 settings.json에 hooks 설정 추가..."

if [ -f "$SETTINGS_FILE" ]; then
    # 기존 설정 백업
    cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup"

    # hooks가 이미 있는지 확인
    if grep -q '"hooks"' "$SETTINGS_FILE"; then
        echo "   ⚠️ hooks 설정이 이미 존재합니다. 수동으로 확인해주세요."
    else
        # jq가 있으면 사용, 없으면 안내
        if command -v jq &> /dev/null; then
            HOOKS_CONFIG='{
                "SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": "~/.claude/hooks/collect-project-context.sh \"$CWD\""}]}],
                "PostToolUse": [
                    {"matcher": "TodoWrite", "hooks": [{"type": "command", "command": "~/.claude/hooks/review-plan.sh"}]},
                    {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "~/.claude/hooks/review-code.sh"}]},
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "~/.claude/hooks/review-test.sh"}]}
                ],
                "Stop": [{"hooks": [{"type": "command", "command": "~/.claude/hooks/review-final.sh"}]}]
            }'
            jq --argjson hooks "$HOOKS_CONFIG" '. + {hooks: $hooks}' "$SETTINGS_FILE" > "$SETTINGS_FILE.tmp"
            mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"
            echo "   ✅ hooks 설정 추가 완료"
        else
            echo "   ⚠️ jq가 설치되어 있지 않습니다."
            echo "   아래 내용을 ~/.claude/settings.json에 수동으로 추가해주세요:"
            cat << 'HOOKS_JSON'
  "hooks": {
    "SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": "~/.claude/hooks/collect-project-context.sh \"$CWD\""}]}],
    "PostToolUse": [
      {"matcher": "TodoWrite", "hooks": [{"type": "command", "command": "~/.claude/hooks/review-plan.sh"}]},
      {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "~/.claude/hooks/review-code.sh"}]},
      {"matcher": "Bash", "hooks": [{"type": "command", "command": "~/.claude/hooks/review-test.sh"}]}
    ],
    "Stop": [{"hooks": [{"type": "command", "command": "~/.claude/hooks/review-final.sh"}]}]
  }
HOOKS_JSON
        fi
    fi
else
    echo "   ⚠️ settings.json이 없습니다. Claude Code를 먼저 실행해주세요."
fi

# 7. 의존성 확인
echo ""
echo "🔍 의존성 확인..."
if command -v gemini &> /dev/null; then
    echo "   ✅ Gemini CLI 설치됨"
else
    echo "   ⚠️ Gemini CLI 미설치 - https://github.com/google-gemini/gemini-cli"
fi

if command -v copilot &> /dev/null; then
    echo "   ✅ Copilot CLI 설치됨"
else
    echo "   ⚠️ Copilot CLI 미설치 - npm install -g @anthropic/copilot-cli"
fi

if python3 -c "import filelock" 2>/dev/null; then
    echo "   ✅ filelock 설치됨"
else
    echo "   ℹ️ filelock 미설치 (선택사항) - pip install filelock"
fi

echo ""
echo "✅ 설치 완료!"
echo ""
echo "📖 사용법:"
echo "   - 새 Claude Code 세션 시작 시 자동으로 자기검열이 활성화됩니다"
echo "   - 검열 스킵: /review-skip 입력"
echo "   - 설정 변경: ~/.claude/hooks/config.json 편집"
echo ""
