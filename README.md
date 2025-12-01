# Claude Code Self-Review Hook

Claude Code에서 작업 완료 시 자동으로 셀프 리뷰를 수행하는 훅 시스템입니다.

## 주요 기능

- **작업 완료 시점 검토**: 모든 TODO가 완료되면 자동으로 리뷰 실행
- **이중 검증**: Claude 셀프 리뷰 + 외부 LLM(Gemini, Copilot) 검토
- **LLM Council**: 의견 불일치 시 토론을 통한 합의 도출
- **의도 비교**: 사용자의 원래 요청과 구현 결과 비교
- **품질 체크**: 누락/과잉 구현 자동 탐지
- **크로스 플랫폼**: Windows, macOS, Linux 지원

## 설치

### 요구사항

- Python 3.8+
- Claude Code

### 설치 방법

```bash
# 저장소 클론
git clone https://github.com/your-repo/claude-self-review-with-llm.git
cd claude-self-review-with-llm

# 설치 (대화형)
python install.py

# 백업 후 설치
python install.py --backup

# 강제 설치 (기존 파일 덮어쓰기)
python install.py --force

# API 키 설정 건너뛰기
python install.py --skip-api
```

### 제거

```bash
# 기본 제거 (로그/상태 유지)
python install.py --uninstall

# 전체 제거 (로그 포함)
python install.py --uninstall --all
```

## 동작 방식

```
TodoWrite 호출
    │
    ▼
모든 todo가 completed?
    │
    ├─ NO → 스킵 (검토 안함)
    │
    └─ YES → 완료 검토 실행
              │
              ├─ Claude 셀프 리뷰 (systemMessage)
              │
              └─ 외부 LLM 검토 (Gemini/Copilot)
                      │
                      ▼
              의견 불일치? → LLM Council 토론
                      │
                      ▼
              결과 취합 → Claude에게 전달
                      │
                      ▼
              문제 발견 시 수정 작업 진행
```

## 파일 구조

```
claude-self-review-with-llm/
├── install.py                    # 크로스플랫폼 설치/제거 스크립트
├── api_key_loader.py             # API 키 통합 로더
├── completion_orchestrator.py    # 완료 검토 오케스트레이션
├── review_orchestrator.py        # 리뷰 오케스트레이션
├── debate_orchestrator.py        # LLM Council 토론 관리
├── intent_extractor.py           # 사용자 의도 추출
├── todo_state_detector.py        # TODO 완료 감지
├── state_manager.py              # 상태 관리
├── security.py                   # 보안 검증
├── quota_monitor.py              # API 쿼터 모니터링
├── config.json                   # 설정 파일
├── adapters/                     # LLM 어댑터
│   ├── __init__.py
│   ├── base.py                   # 기본 인터페이스
│   ├── claude_self.py            # Claude 셀프 리뷰
│   ├── gemini.py                 # Gemini 어댑터
│   └── copilot.py                # GitHub Copilot 어댑터
└── prompts/                      # 프롬프트 템플릿
    ├── completion_self.txt
    ├── completion_external.txt
    └── ...
```

### 설치 후 생성되는 디렉토리

```
~/.claude/
├── settings.json                 # Claude Code 설정 (hooks 추가됨)
└── hooks/
    ├── *.py                      # Python 모듈들
    ├── adapters/                 # LLM 어댑터
    ├── prompts/                  # 프롬프트
    ├── config.json               # 설정
    ├── api_keys.json             # API 키 (선택)
    ├── logs/                     # 감사 로그
    └── state/                    # 상태 파일
```

## 설정

### API 키 설정

설치 시 대화형으로 API 키를 설정하거나, 수동으로 설정할 수 있습니다.

#### 방법 1: 환경 변수 (권장)

```bash
# Windows (PowerShell)
setx GEMINI_API_KEY "your-api-key"

# macOS/Linux
export GEMINI_API_KEY="your-api-key"
# .bashrc 또는 .zshrc에 추가
```

#### 방법 2: API 키 파일

`~/.claude/hooks/api_keys.json`:
```json
{
  "GEMINI_API_KEY": "your-gemini-key",
  "OPENAI_API_KEY": "your-openai-key",
  "ANTHROPIC_API_KEY": "your-anthropic-key"
}
```

#### API 키 우선순위

```
환경 변수 > api_keys.json > config.json
```

#### GitHub Copilot

```bash
gh auth login
```

### config.json

```json
{
  "enabled_adapters": ["gemini"],
  "timeout_seconds": 60,
  "parallel_execution": true,

  "gemini": {
    "use_api": true,
    "model": "gemini-2.5-flash-lite",
    "api_key": "${GEMINI_API_KEY}"
  },

  "debate": {
    "enabled": true,
    "trigger_on_disagreement": true,
    "max_rounds": 2,
    "participants": ["gemini", "claude_self"]
  },

  "completion_review": {
    "enabled": true,
    "include_self_review": true,
    "include_external_review": true,
    "max_reviews": 3
  }
}
```

## 검토 기준

1. **의도 충족도**: 사용자 요청이 모두 구현되었는가?
2. **누락 분석**: 빠진 기능/요구사항이 있는가?
3. **과잉 구현**: 요청하지 않은 불필요한 기능이 추가되었는가?
4. **품질 확인**: 코드 품질, 테스트, 에러 처리가 적절한가?

## 출력 예시

```
## 셀프 리뷰 결과

| 검토 기준 | 결과 | 상세 |
|-----------|------|------|
| 의도 충족도 | ✅ | 모든 요구사항 구현 완료 |
| 누락 분석 | ✅ | 누락 없음 |
| 과잉 구현 | ✅ | 불필요한 추가 기능 없음 |
| 품질 확인 | ✅ | 코드 품질 양호 |

**최종 판정: 작업 완료** ✅
```

## 심각도 레벨

| 레벨 | 설명 | 동작 |
|------|------|------|
| OK | 문제 없음 | 진행 |
| LOW | 사소한 개선 | 진행 + 메시지 |
| MEDIUM | 개선 권장 | 진행 + 메시지 |
| HIGH | 수정 필요 | 경고 + 메시지 |
| CRITICAL | 즉시 수정 | 경고 + 메시지 |

## 리뷰 스킵

### 방법 1: 환경 변수
```bash
export CLAUDE_SKIP_REVIEW=1
```

### 방법 2: 대화 내 키워드
```
/review-skip
```
또는
```
검열 스킵
```

## 트러블슈팅

### 훅이 실행되지 않는 경우
1. Claude Code 재시작
2. `~/.claude/settings.json`에 hooks 설정 확인
3. Python 경로 확인: `which python` 또는 `where python`

### 외부 LLM이 작동하지 않는 경우
1. API 키 확인: `python -c "from api_key_loader import get_api_key; print(get_api_key('GEMINI_API_KEY'))"`
2. `config.json`에서 `include_external_review: false`로 비활성화 가능

### 로그 확인
```bash
# 훅 디버그 로그
cat ~/.claude/hooks/logs/hook-debug.log

# 완료 검토 감사 로그 (날짜별)
cat ~/.claude/hooks/logs/completion-audit-$(date +%Y-%m-%d).jsonl

# 상태 확인
ls ~/.claude/hooks/state/
```

### Windows 특이사항
- PowerShell에서 `python` 명령이 Microsoft Store로 리다이렉트되는 경우:
  ```powershell
  # Python 설치 경로 직접 사용
  C:\Python311\python.exe install.py
  ```
- 환경 변수 설정 후 터미널 재시작 필요

## 확장

### 새 LLM 어댑터 추가

1. `adapters/` 디렉토리에 새 어댑터 생성
2. `LLMAdapter` 상속 및 `review()`, `is_available()` 구현
3. `config.json`의 `enabled_adapters`에 추가
4. `adapters/__init__.py`에 export 추가

```python
# adapters/new_llm.py
from .base import LLMAdapter, ReviewResult, Severity

class NewLLMAdapter(LLMAdapter):
    def __init__(self, config):
        super().__init__("new_llm", config)

    def is_available(self) -> bool:
        # API 키 또는 CLI 확인
        return get_api_key("NEW_LLM_API_KEY") is not None

    def review(self, prompt: str, context: dict) -> ReviewResult:
        # 리뷰 로직 구현
        pass
```

## 의존성

### 필수
- Python 3.8+

### 선택
- `filelock`: Race condition 방지
- `certifi`: SSL 인증서 (macOS)

```bash
pip install filelock certifi
```

## 라이선스

MIT
