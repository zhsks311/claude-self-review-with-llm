# Claude Code 자기검열 시스템

Claude Code 작업 시 **계획 → 코드 → 테스트 → 완료** 모든 단계에서 Gemini, Copilot 등 다중 LLM이 자동으로 검토하고 피드백을 제공하는 시스템.

## 핵심 기능

- **다양한 시각**: 여러 LLM이 서로 다른 관점에서 코드 검토
- **상호 검증**: Claude 작성 코드를 외부 LLM이 검증하여 편향 감소
- **자동 재작업**: 심각한 문제(CRITICAL/HIGH) 발견 시 자동 수정 요청

## 설치

### 방법 1: Plugin으로 설치 (권장)

```bash
# GitHub에서 직접 설치
claude plugins add github:YOUR_USERNAME/claude-self-review

# 또는 로컬 디렉토리에서 설치
claude plugins add /path/to/claude-self-review
```

### 방법 2: 설치 스크립트

```bash
git clone https://github.com/YOUR_USERNAME/claude-self-review.git
cd claude-self-review
./install.sh
```

### 방법 3: 수동 설치

```bash
# 파일 복사
cp -r * ~/.claude/hooks/

# settings.json에 hooks 설정 추가 (README 하단 참조)
```

## 제거

```bash
# Plugin으로 설치한 경우
claude plugins remove self-review

# 스크립트로 설치한 경우
./uninstall.sh
```

## 파일 구조

```
~/.claude/hooks/
├── config.json              # 설정 파일
├── review_orchestrator.py   # 오케스트레이터 (핵심)
├── state_manager.py         # 상태 관리
├── security.py              # 보안 모듈
├── adapters/                # LLM 어댑터
│   ├── base.py
│   ├── gemini.py
│   └── copilot.py
├── prompts/                 # 단계별 프롬프트
│   ├── plan.txt
│   ├── code.txt
│   ├── test.txt
│   └── final.txt
├── review-*.sh              # Hook 엔트리 스크립트
├── state/                   # 상태 파일
└── logs/                    # 감사 로그
```

## 동작 방식

```
[계획] → TodoWrite → review-plan.sh → 검열
   ↓
[코드] → Edit/Write → review-code.sh → 검열 (Debounce 3초)
   ↓
[테스트] → Bash(test) → review-test.sh → 검열
   ↓
[완료] → Stop Event → review-final.sh → 종합 검열
```

## 심각도 레벨

| 레벨 | 설명 | 동작 |
|------|------|------|
| OK | 문제 없음 | 진행 |
| LOW | 사소한 개선 | 진행 + 메시지 |
| MEDIUM | 개선 권장 | 진행 + 메시지 |
| HIGH | 수정 필요 | **재작업 요청** |
| CRITICAL | 즉시 수정 | **재작업 요청** |

## 설정

`config.json` 주요 설정:

```json
{
  "enabled_adapters": ["gemini", "copilot"],
  "conflict_resolution": {
    "policy": "conservative"  // 하나라도 CRITICAL이면 CRITICAL
  },
  "debounce": {
    "enabled": true,
    "seconds": 3              // 연속 편집 시 3초 대기
  },
  "rework_settings": {
    "max_retries": 3          // 최대 재시도 횟수
  }
}
```

## 검열 스킵 (Override)

### 방법 1: 대화 내 키워드
```
/review-skip
```
또는
```
검열 스킵
```

### 방법 2: 환경 변수
```bash
export CLAUDE_SKIP_REVIEW=1
```

## 충돌 해결 정책

여러 LLM의 의견이 다를 때:

| 정책 | 설명 |
|------|------|
| **conservative** (기본) | 하나라도 CRITICAL이면 최종 CRITICAL |
| majority_vote | 다수결 (동률 시 높은 심각도) |
| weighted_vote | LLM별 가중치 적용 |

## 로그 확인

```bash
# 감사 로그
cat ~/.claude/hooks/logs/audit-$(date +%Y-%m-%d).jsonl

# 상태 확인
ls ~/.claude/hooks/state/
```

## 의존성

- Python 3.8+
- Gemini CLI (`gemini`)
- GitHub Copilot CLI (`copilot`)

### 선택적 의존성
```bash
pip install filelock  # Race condition 방지 (없어도 동작)
```

## 비활성화

`~/.claude/settings.json`에서 hooks 섹션 제거 또는 주석 처리.

## 확장

새 LLM 추가:

1. `adapters/` 디렉토리에 새 어댑터 생성
2. `LLMAdapter` 상속 및 `review()`, `is_available()` 구현
3. `config.json`의 `enabled_adapters`에 추가

```python
# adapters/new_llm.py
from .base import LLMAdapter, ReviewResult

class NewLLMAdapter(LLMAdapter):
    def __init__(self, config):
        super().__init__("new_llm", config)

    def is_available(self) -> bool:
        return shutil.which("new-llm-cli") is not None

    def review(self, prompt, context) -> ReviewResult:
        # 구현
        pass
```

## 문제 해결

### Hook이 실행되지 않음
```bash
# settings.json 확인
cat ~/.claude/settings.json | grep -A 30 hooks
```

### LLM CLI를 찾을 수 없음
```bash
which gemini
which copilot
```

### 로그에서 에러 확인
```bash
tail -20 ~/.claude/hooks/logs/audit-$(date +%Y-%m-%d).jsonl
```

## 라이선스

MIT
