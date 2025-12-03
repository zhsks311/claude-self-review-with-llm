# Claude Code Self-Review Hook

Claude Code에서 작업 완료 시 자동으로 셀프 리뷰를 수행하는 훅 시스템입니다.

## 주요 기능

- **작업 완료 시점 검토**: 모든 TODO가 완료되면 자동으로 리뷰 실행
- **이중 검증**: Claude 셀프 리뷰 + 외부 LLM(Gemini, Copilot) 검토
- **의도 비교**: 사용자의 원래 요청과 구현 결과 비교
- **품질 체크**: 누락/과잉 구현 자동 탐지

## 설치

```bash
# 저장소 클론 또는 파일 다운로드 후
cd path/to/hooks

# 설치 (기존 설정 백업)
./install.sh --backup

# 또는 강제 설치 (기존 파일 덮어쓰기)
./install.sh --force
```

## 제거

```bash
# 훅 파일만 제거 (기본 파일 유지)
./uninstall.sh

# 전체 제거
./uninstall.sh --all
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
              결과 취합 → Claude에게 전달
                      │
                      ▼
              문제 발견 시 수정 작업 진행
```

## 파일 구조

```
hooks/
├── adapters/                      # LLM 어댑터
│   ├── __init__.py
│   ├── base.py                    # 기본 인터페이스
│   ├── claude_self.py             # Claude 셀프 리뷰
│   ├── gemini.py                  # Gemini 어댑터
│   └── copilot.py                 # GitHub Copilot 어댑터
├── prompts/                       # 프롬프트 파일
│   ├── completion_self.txt        # 셀프 리뷰 프롬프트
│   └── completion_external.txt    # 외부 LLM용 프롬프트
├── logs/                          # 감사 로그
├── state/                         # 상태 파일
├── completion_orchestrator.py     # 완료 검토 오케스트레이션
├── intent_extractor.py            # 의도 추출
├── todo_state_detector.py         # TODO 완료 감지
├── state_manager.py               # 상태 관리
├── security.py                    # 보안 검증
├── config.json                    # 설정
├── review-completion.sh           # 완료 검토 엔트리포인트
├── review-test.sh                 # 테스트 검토
├── collect-project-context.sh     # 프로젝트 정보 수집
├── install.sh                     # 설치 스크립트
├── uninstall.sh                   # 제거 스크립트
└── settings.json.template         # 설정 템플릿
```

## 설정

### config.json

```json
{
  "completion_review": {
    "enabled": true,
    "include_self_review": true,
    "include_external_review": true,
    "max_reviews": 3
  },
  "intent_extraction": {
    "max_chars": 10000
  },
  "enabled_adapters": ["gemini", "copilot"]
}
```

### 외부 LLM 설정

#### Gemini
```bash
export GEMINI_API_KEY="your-api-key"
```

#### GitHub Copilot
```bash
gh auth login
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

## 심각도 레벨 (외부 LLM)

| 레벨 | 설명 | 동작 |
|------|------|------|
| OK | 문제 없음 | 진행 |
| LOW | 사소한 개선 | 진행 + 메시지 |
| MEDIUM | 개선 권장 | 진행 + 메시지 |
| HIGH | 수정 필요 | 경고 + 메시지 |
| CRITICAL | 즉시 수정 | 경고 + 메시지 |

## 검열 스킵 (Override)

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
3. 스크립트 실행 권한 확인: `chmod +x ~/.claude/hooks/*.sh`

### 외부 LLM이 작동하지 않는 경우
1. API 키/인증 확인
2. `config.json`에서 `include_external_review: false`로 비활성화 가능

### 로그 확인
```bash
# 완료 검토 감사 로그
cat ~/.claude/hooks/logs/completion-audit-$(date +%Y-%m-%d).jsonl

# 상태 확인
ls ~/.claude/hooks/state/
```

## 의존성

- Python 3.8+
- (선택) Gemini CLI
- (선택) GitHub Copilot CLI

### 선택적 의존성
```bash
pip install filelock  # Race condition 방지 (없어도 동작)
```

## 확장

새 LLM 추가:

1. `adapters/` 디렉토리에 새 어댑터 생성
2. `LLMAdapter` 상속 및 `review()`, `is_available()` 구현
3. `config.json`의 `enabled_adapters`에 추가
4. `adapters/__init__.py`에 export 추가

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

## 라이선스

MIT
