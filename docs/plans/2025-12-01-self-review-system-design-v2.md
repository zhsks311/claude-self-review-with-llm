# Claude Code 자기검열 시스템 설계

> **버전**: v2.0 (2025-12-01)
> **변경 사항**: Gemini/Copilot 피드백 반영 - LLM 충돌 처리, 보안, Debounce, Override 메커니즘 추가

## 개요

Claude Code로 코드 작업 시, 계획 수립부터 코드 작성, 테스트, 완료까지 모든 단계에서 자동으로 자기검열을 수행하는 시스템.

### 목표

1. **다양한 시각**: 여러 LLM이 서로 다른 관점에서 검토
2. **상호 검증**: Claude가 작성한 코드를 다른 LLM이 검증하여 편향 감소
3. **자동 재작업**: 심각한 문제 발견 시 자동으로 수정 요청

### 범위

- 로컬 개발 환경 우선 (추후 팀/CI 확장 가능)
- 방식 A (Hooks 기반)로 시작, 추후 방식 B (MCP) 확장 가능

---

## 아키텍처

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code Session                       │
├─────────────────────────────────────────────────────────────┤
│  [계획] → [코드 작성] → [테스트 실행] → [완료]              │
│     ↓          ↓             ↓            ↓                 │
│  TodoWrite   Edit/Write     Bash        Stop Event          │
└─────┬──────────┬─────────────┬────────────┬─────────────────┘
      ↓          ↓             ↓            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Hook Layer (settings.json)                │
│                                                              │
│  PostToolUse     PostToolUse      PostToolUse    Stop        │
│  (TodoWrite)     (Edit|Write)     (Bash)         Event       │
│      ↓               ↓                ↓            ↓         │
│  [Debounce]     [Debounce]       [필터링]      [검열]        │
│      ↓               ↓                ↓            ↓         │
│  계획 검열       코드 검열        테스트 검열   종합 검열    │
└──────┬───────────────┬────────────────┬────────────┬────────┘
       └───────────────┴────────────────┴────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              review-orchestrator.py (Python)                 │
│                                                              │
│   stdin (JSON) → 동적 컨텍스트 추출 → 다중 LLM 호출         │
│                                                              │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                   │
│   │ Gemini  │   │ Copilot │   │ (확장)  │                   │
│   │  CLI    │   │   CLI   │   │         │                   │
│   └────┬────┘   └────┬────┘   └────┬────┘                   │
│        └─────────────┼─────────────┘                        │
│                      ↓                                       │
│         [충돌 해결 정책] → 최종 심각도 결정                  │
│                      ↓                                       │
│              결과 취합 & JSON 포맷팅                         │
│                      ↓                                       │
│   stdout: {"systemMessage": "...", "continue": true|false}  │
│                      ↓                                       │
│              [감사 로그 기록]                                │
└─────────────────────────────────────────────────────────────┘
\`\`\`

---

## [신규] 동적 컨텍스트

### 정적 vs 동적 컨텍스트

| 구분 | 수집 시점 | 내용 |
|------|----------|------|
| **정적** | SessionStart | Java 버전, Spring 버전, DB 종류, 아키텍처 |
| **동적** | 각 Hook 실행 시 | diff, userRequest, 변경 파일 경로, 세션 히스토리 |

### 동적 컨텍스트 구조

Hook에 전달되는 stdin JSON에서 추출:

\`\`\`json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.json",
  "cwd": "/project/root",
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/src/main/java/Service.java",
    "old_string": "기존 코드",
    "new_string": "새 코드"
  }
}
\`\`\`

---

## [신규] LLM 의견 충돌 처리 정책

### 문제 상황

Gemini는 "OK"를, Copilot은 "CRITICAL"을 반환할 경우 어떻게 처리할 것인가?

### 충돌 해결 정책

| 정책 | 설명 | 사용 시기 |
|------|------|----------|
| **conservative** (기본) | 하나라도 CRITICAL이면 CRITICAL | 안전 우선 |
| highest_severity | 가장 높은 심각도 선택 | conservative와 동일 |
| majority_vote | 다수결 (동률 시 높은 심각도) | LLM 3개 이상 사용 시 |
| weighted_vote | LLM별 가중치 적용 | 특정 LLM 신뢰도 높을 때 |

### 기본 정책: conservative

- 하나의 LLM이라도 CRITICAL → 최종 CRITICAL
- 안전을 우선시하는 자기검열 시스템 목적에 부합

---

## [신규] Debounce 메커니즘

### 문제 상황

Edit/Write가 연속 호출될 때마다 검열 실행 → 과도한 비용/지연

### 해결

마지막 도구 호출 후 **3초 동안 추가 호출이 없을 때만** 검열 실행

\`\`\`
Edit 호출 → 3초 대기 → 새 Edit 없음 → 검열 실행
Edit 호출 → 2초 후 새 Edit → 이전 검열 취소 → 다시 3초 대기
\`\`\`

---

## [신규] 사용자 Override 메커니즘

### 문제 상황

검열 시스템이 "불필요"로 판단하지만, 사용자가 의도한 변경일 수 있음

### 해결

1. **대화 내 키워드**: \`/review-skip\` 또는 \`검열 스킵\`
2. **환경 변수**: \`CLAUDE_SKIP_REVIEW=1\`
3. **설정 파일**: skip_count, skip_until 등

### Override 시 감사 로그 필수 기록

---

## [신규] 보안

### 위협 및 대응

| 위협 | 대응 |
|------|------|
| 명령 인젝션 | 입력 검증, 허용 목록 |
| 민감정보 유출 | 패턴 마스킹 (password=, api_key= 등) |
| LLM 응답 조작 | JSON 스키마 검증 |

### 허용 파일 확장자

\`.java\`, \`.kt\`, \`.xml\`, \`.yml\`, \`.yaml\`, \`.properties\`, \`.json\`

---

## [신규] 감사 로그 및 모니터링

### 로그 위치

\`\`\`
~/.claude/hooks/logs/
├── audit-2025-12-01.jsonl      # 일별 감사 로그
├── metrics-2025-12-01.json     # 일별 메트릭
└── errors-2025-12-01.jsonl     # 에러 로그
\`\`\`

### 기록 항목

- timestamp, session_id, event_type
- stage (plan/code/test/final)
- llm_results, final_severity
- continue_decision, duration_ms

---

## [신규] 상태 관리

### 상태 파일

\`\`\`
~/.claude/hooks/state/
├── {session_id}_retry_count.json
├── {session_id}_last_call.json
└── {session_id}_override.json
\`\`\`

### Race Condition 방지

- filelock 라이브러리 사용
- 세션별 독립 상태 파일

---

## 디렉토리 구조 (수정)

\`\`\`
~/.claude/hooks/
├── config.json                 # 전역 설정
├── review-orchestrator.py      # 메인 오케스트레이터 (Python)
├── state/                      # 상태 관리
├── logs/                       # 감사 로그
├── adapters/
│   ├── base.py
│   ├── gemini.py
│   └── copilot.py
├── prompts/
│   ├── plan.txt
│   ├── code.txt
│   ├── test.txt
│   └── final.txt
├── collect-project-context.sh
├── review-plan.sh
├── review-code.sh
├── review-test.sh
└── review-final.sh
\`\`\`

---

## 설정 파일 (확장)

\`\`\`json
{
  "enabled_adapters": ["gemini", "copilot"],
  "timeout_seconds": 60,
  "parallel_execution": true,

  "conflict_resolution": {
    "policy": "conservative",
    "weights": { "gemini": 1.0, "copilot": 1.2 }
  },

  "debounce": {
    "enabled": true,
    "seconds": 3,
    "stages": ["code"]
  },

  "override": {
    "enabled": true,
    "keywords": ["/review-skip", "검열 스킵"],
    "require_audit_log": true
  },

  "security": {
    "mask_sensitive_data": true,
    "allowed_file_extensions": [".java", ".kt", ".xml", ".yml", ".yaml", ".json"],
    "validate_llm_response": true
  },

  "logging": {
    "audit_enabled": true,
    "metrics_enabled": true,
    "retention_days": 30
  },

  "rework_settings": {
    "max_retries": 3,
    "exponential_backoff": true,
    "critical_triggers": ["security", "injection", "FAIL"],
    "high_triggers": ["버그", "bug", "누락", "missing"]
  },

  "stage_settings": {
    "plan": { "enabled": true, "max_retries": 2 },
    "code": { "enabled": true, "max_retries": 3, "debounce": true },
    "test": { "enabled": true, "max_retries": 2 },
    "final": { "enabled": true, "max_retries": 2 }
  }
}
\`\`\`

---

## 재작업 흐름 (수정)

\`\`\`
작업 시작
    ↓
[계획] → [Debounce] → [검열] → CRITICAL/HIGH? → 재작업 (max 2회)
    ↓
[코드] → [Debounce] → [검열] → CRITICAL/HIGH? → 재작업 (max 3회)
    ↓
[테스트] → [필터링] → [검열] → CRITICAL/HIGH? → 재작업 (max 2회)
    ↓
[완료] → [종합검열] → FAIL? → 재작업 (max 2회)
    ↓
✅ 완료 (또는 max_retries 초과 시 경고 후 진행)
\`\`\`

### 무한 루프 방지

1. 단계별 max_retries 제한
2. 지수 백오프 (1초 → 2초 → 4초)
3. 사용자 Override (/review-skip)
4. max_retries 초과 시 경고만 표시하고 진행

---

## 구현 순서

1. 기반 구조 (디렉토리, config.json)
2. 상태 관리 모듈 (state/, filelock)
3. 보안 모듈 (입력 검증, 마스킹)
4. LLM Adapters (Python)
5. 오케스트레이터 (충돌 해결, 심각도 분류)
6. 단계별 검열 스크립트 (+ Debounce)
7. 감사 로그 모듈
8. 프롬프트 템플릿
9. 테스트 및 검증

---

## 참고 자료

- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
- [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-copilot-cli)
