#!/bin/bash
#
# Claude Code Self-Review Hook 제거 스크립트
#
# 사용법:
#   ./uninstall.sh           # 훅 파일만 제거 (설정 유지)
#   ./uninstall.sh --all     # 모든 파일 제거 (설정 포함)
#

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CLAUDE_DIR="$HOME/.claude"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

REMOVE_ALL=false

for arg in "$@"; do
    case $arg in
        --all)
            REMOVE_ALL=true
            shift
            ;;
        --help|-h)
            echo "사용법: $0 [옵션]"
            echo ""
            echo "옵션:"
            echo "  --all     모든 파일 제거 (설정 포함)"
            echo "  --help    도움말 표시"
            exit 0
            ;;
    esac
done

echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║     Claude Code Self-Review Hook 제거 스크립트            ║${NC}"
echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 확인
read -p "정말 제거하시겠습니까? (y/N): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "취소되었습니다."
    exit 0
fi

echo ""
echo -e "${YELLOW}[1/3]${NC} 훅 파일 제거 중..."

# 제거할 파일 목록
FILES_TO_REMOVE=(
    "completion_orchestrator.py"
    "intent_extractor.py"
    "todo_state_detector.py"
    "review-completion.sh"
)

for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$HOOKS_DIR/$file" ]; then
        rm "$HOOKS_DIR/$file"
        echo -e "  ${GREEN}✓${NC} $file 제거됨"
    fi
done

# adapters/claude_self.py 제거
if [ -f "$HOOKS_DIR/adapters/claude_self.py" ]; then
    rm "$HOOKS_DIR/adapters/claude_self.py"
    echo -e "  ${GREEN}✓${NC} adapters/claude_self.py 제거됨"
fi

# 프롬프트 제거
if [ -f "$HOOKS_DIR/prompts/completion_self.txt" ]; then
    rm "$HOOKS_DIR/prompts/completion_self.txt"
    echo -e "  ${GREEN}✓${NC} prompts/completion_self.txt 제거됨"
fi

if [ -f "$HOOKS_DIR/prompts/completion_external.txt" ]; then
    rm "$HOOKS_DIR/prompts/completion_external.txt"
    echo -e "  ${GREEN}✓${NC} prompts/completion_external.txt 제거됨"
fi

echo -e "${YELLOW}[2/3]${NC} settings.json에서 훅 설정 제거 중..."

if [ -f "$SETTINGS_FILE" ] && command -v python3 &> /dev/null; then
    python3 << 'EOF'
import json
from pathlib import Path

settings_path = Path.home() / ".claude" / "settings.json"
settings = json.loads(settings_path.read_text())

# hooks 섹션 제거
if "hooks" in settings:
    del settings["hooks"]

settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
print("  ✓ settings.json에서 hooks 설정 제거됨")
EOF
fi

if [ "$REMOVE_ALL" = true ]; then
    echo -e "${YELLOW}[3/3]${NC} 전체 hooks 디렉토리 제거 중..."
    rm -rf "$HOOKS_DIR"
    echo -e "  ${GREEN}✓${NC} $HOOKS_DIR 제거됨"
else
    echo -e "${YELLOW}[3/3]${NC} 기본 파일 유지..."
    echo -e "  ${BLUE}ℹ${NC} state_manager.py, security.py 등 기본 파일 유지"
    echo -e "  ${BLUE}ℹ${NC} 전체 제거: ./uninstall.sh --all"
fi

echo ""
echo -e "${GREEN}제거 완료!${NC}"
echo ""
echo "Claude Code를 재시작하세요."
