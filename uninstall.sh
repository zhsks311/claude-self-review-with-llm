#!/bin/bash
# Claude Code 자기검열 시스템 제거 스크립트

set -e

HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo "🗑️ Claude Code 자기검열 시스템 제거 중..."

# 1. hooks 디렉토리 제거
if [ -d "$HOOKS_DIR" ]; then
    read -p "⚠️ $HOOKS_DIR 디렉토리를 삭제하시겠습니까? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$HOOKS_DIR"
        echo "   ✅ hooks 디렉토리 삭제됨"
    else
        echo "   ⏭️ 건너뜀"
    fi
fi

# 2. settings.json에서 hooks 제거
if [ -f "$SETTINGS_FILE" ]; then
    if grep -q '"hooks"' "$SETTINGS_FILE"; then
        if command -v jq &> /dev/null; then
            jq 'del(.hooks)' "$SETTINGS_FILE" > "$SETTINGS_FILE.tmp"
            mv "$SETTINGS_FILE.tmp" "$SETTINGS_FILE"
            echo "   ✅ settings.json에서 hooks 설정 제거됨"
        else
            echo "   ⚠️ jq가 없어 수동으로 settings.json에서 'hooks' 섹션을 제거해주세요"
        fi
    fi
fi

echo ""
echo "✅ 제거 완료!"
