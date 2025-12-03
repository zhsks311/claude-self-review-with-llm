#!/bin/bash
#
# Claude Code Self-Review Hook 설치 스크립트
#
# 사용법:
#   ./install.sh              # 기본 설치
#   ./install.sh --backup     # 기존 설정 백업 후 설치
#   ./install.sh --force      # 기존 파일 덮어쓰기
#

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

# 옵션 파싱
BACKUP=false
FORCE=false

for arg in "$@"; do
    case $arg in
        --backup)
            BACKUP=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help|-h)
            echo "사용법: $0 [옵션]"
            echo ""
            echo "옵션:"
            echo "  --backup    기존 설정 백업 후 설치"
            echo "  --force     기존 파일 덮어쓰기"
            echo "  --help      도움말 표시"
            exit 0
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Claude Code Self-Review Hook 설치 스크립트            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. 디렉토리 생성
echo -e "${YELLOW}[1/5]${NC} 디렉토리 생성 중..."
mkdir -p "$HOOKS_DIR/adapters"
mkdir -p "$HOOKS_DIR/prompts"
mkdir -p "$HOOKS_DIR/logs"
mkdir -p "$HOOKS_DIR/state"
echo -e "  ${GREEN}✓${NC} $HOOKS_DIR 생성 완료"

# 2. 백업 (옵션)
if [ "$BACKUP" = true ] && [ -f "$SETTINGS_FILE" ]; then
    BACKUP_FILE="$SETTINGS_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$SETTINGS_FILE" "$BACKUP_FILE"
    echo -e "  ${GREEN}✓${NC} 기존 설정 백업: $BACKUP_FILE"
fi

# 3. 핵심 파일 복사
echo -e "${YELLOW}[2/5]${NC} 핵심 파일 복사 중..."

# Python 모듈
PYTHON_FILES=(
    "completion_orchestrator.py"
    "intent_extractor.py"
    "todo_state_detector.py"
    "state_manager.py"
    "security.py"
    "review_orchestrator.py"
)

for file in "${PYTHON_FILES[@]}"; do
    if [ -f "$SCRIPT_DIR/$file" ]; then
        cp "$SCRIPT_DIR/$file" "$HOOKS_DIR/"
        echo -e "  ${GREEN}✓${NC} $file"
    fi
done

# 4. 어댑터 복사
echo -e "${YELLOW}[3/5]${NC} 어댑터 복사 중..."
if [ -d "$SCRIPT_DIR/adapters" ]; then
    cp "$SCRIPT_DIR/adapters/"*.py "$HOOKS_DIR/adapters/"
    echo -e "  ${GREEN}✓${NC} adapters/*.py"
fi

# 5. 쉘 스크립트 복사 및 실행 권한 부여
echo -e "${YELLOW}[4/5]${NC} 스크립트 복사 중..."

SHELL_SCRIPTS=(
    "review-completion.sh"
    "review-test.sh"
    "collect-project-context.sh"
)

for script in "${SHELL_SCRIPTS[@]}"; do
    if [ -f "$SCRIPT_DIR/$script" ]; then
        cp "$SCRIPT_DIR/$script" "$HOOKS_DIR/"
        chmod +x "$HOOKS_DIR/$script"
        echo -e "  ${GREEN}✓${NC} $script"
    fi
done

# 6. 프롬프트 및 설정 파일 복사
echo -e "${YELLOW}[5/5]${NC} 설정 파일 복사 중..."

if [ -d "$SCRIPT_DIR/prompts" ]; then
    cp "$SCRIPT_DIR/prompts/"*.txt "$HOOKS_DIR/prompts/" 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} prompts/*.txt"
fi

if [ -f "$SCRIPT_DIR/config.json" ]; then
    if [ ! -f "$HOOKS_DIR/config.json" ] || [ "$FORCE" = true ]; then
        cp "$SCRIPT_DIR/config.json" "$HOOKS_DIR/"
        echo -e "  ${GREEN}✓${NC} config.json"
    else
        echo -e "  ${YELLOW}⚠${NC} config.json 이미 존재 (--force로 덮어쓰기)"
    fi
fi

# 7. settings.json 업데이트
echo ""
echo -e "${YELLOW}settings.json 설정...${NC}"

if [ -f "$SETTINGS_FILE" ]; then
    # 기존 설정이 있는 경우 - 훅 설정만 업데이트
    if command -v python3 &> /dev/null; then
        python3 << 'EOF'
import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"
settings = json.loads(settings_path.read_text())

# hooks 섹션 업데이트
settings["hooks"] = {
    "SessionStart": [
        {
            "matcher": "startup",
            "hooks": [
                {
                    "type": "command",
                    "command": "~/.claude/hooks/collect-project-context.sh \"$CWD\""
                }
            ]
        }
    ],
    "PostToolUse": [
        {
            "matcher": "TodoWrite",
            "hooks": [
                {
                    "type": "command",
                    "command": "~/.claude/hooks/review-completion.sh",
                    "timeout": 180
                }
            ]
        },
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": "~/.claude/hooks/review-test.sh"
                }
            ]
        }
    ]
}

settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
print("  ✓ settings.json 훅 설정 업데이트 완료")
EOF
    else
        echo -e "  ${YELLOW}⚠${NC} Python3가 없어 settings.json 자동 업데이트 불가"
        echo -e "  ${YELLOW}⚠${NC} settings.json.template을 참고하여 수동 설정 필요"
    fi
else
    # 새 설정 파일 생성
    if [ -f "$SCRIPT_DIR/settings.json.template" ]; then
        cp "$SCRIPT_DIR/settings.json.template" "$SETTINGS_FILE"
        echo -e "  ${GREEN}✓${NC} settings.json 생성 완료"
    fi
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    설치 완료!                              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "설치 위치: ${BLUE}$HOOKS_DIR${NC}"
echo ""
echo -e "${YELLOW}다음 단계:${NC}"
echo "1. Claude Code를 재시작하세요"
echo "2. TodoWrite로 작업 완료 시 셀프 리뷰가 자동 실행됩니다"
echo ""
echo -e "${YELLOW}외부 LLM 설정 (선택):${NC}"
echo "- Gemini: GEMINI_API_KEY 환경변수 설정"
echo "- GitHub Copilot: gh auth login 실행"
echo ""
