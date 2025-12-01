# Claude Code 자기검열 시스템 설계

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

```
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
│  계획 검열       코드 검열        테스트 검열   종합 검열    │
└──────┬───────────────┬────────────────┬────────────┬────────┘
       └───────────────┴────────────────┴────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              review-orchestrator.sh                          │
│                                                              │
│   stdin (JSON) → 컨텍스트 추출 → 다중 LLM 호출              │
│                                                              │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                   │
│   │ Gemini  │   │ Copilot │   │ (확장)  │                   │
│   │  CLI    │   │   CLI   │   │         │                   │
│   └────┬────┘   └────┬────┘   └────┬────┘                   │
│        └─────────────┼─────────────┘                        │
│                      ↓                                       │
│              결과 취합 & JSON 포맷팅                         │
│                      ↓                                       │
│   stdout: {"systemMessage": "...", "continue": true|false}  │
└─────────────────────────────────────────────────────────────┘
```

---

## 디렉토리 구조

```
~/.claude/hooks/
├── config.json                 # 전역 설정
├── review-orchestrator.sh      # 메인 오케스트레이터
├── adapters/
│   ├── gemini.sh               # Gemini CLI 래퍼
│   ├── copilot.sh              # GitHub Copilot CLI 래퍼
│   └── openai.sh               # OpenAI CLI 래퍼 (확장용)
├── prompts/
│   ├── plan.txt                # 계획 검열 프롬프트
│   ├── code.txt                # 코드 검열 프롬프트
│   ├── test.txt                # 테스트 검열 프롬프트
│   └── final.txt               # 종합 검열 프롬프트
├── collect-project-context.sh  # 프로젝트 정보 수집
├── review-plan.sh              # 계획 검열 엔트리포인트
├── review-code.sh              # 코드 검열 엔트리포인트
├── review-test.sh              # 테스트 검열 엔트리포인트
└── review-final.sh             # 종합 검열 엔트리포인트
```

---

## Hook 설정

### settings.json 전체 구조

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/collect-project-context.sh",
            "timeout": 30
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
            "command": "$HOME/.claude/hooks/review-plan.sh",
            "timeout": 120
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/review-code.sh",
            "timeout": 120
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/review-test.sh",
            "timeout": 120
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/review-final.sh",
            "timeout": 180
          }
        ]
      }
    ]
  }
}
```

---

## 검열 단계별 상세

### 1. 프로젝트 컨텍스트 수집 (SessionStart)

**트리거**: 세션 시작 시 (startup)

**수집 항목**:
| 항목 | 수집 방법 |
|------|----------|
| Java 버전 | pom.xml 또는 build.gradle |
| Spring Boot 버전 | pom.xml parent 또는 build.gradle |
| DB 종류 | application.yml/properties |
| 주요 의존성 | pom.xml dependencies |
| 코드 컨벤션 | .editorconfig, checkstyle.xml |
| 테스트 프레임워크 | JUnit4/5, Mockito 등 |
| 아키텍처 패턴 | 패키지 구조 분석 |

**출력**: `.claude/project-context.json`

### 2. 계획 검열 (PostToolUse - TodoWrite)

**트리거**: Claude가 TodoWrite로 작업 계획 작성 시

**검열 목표**:
- 요구사항 누락 여부
- 엣지 케이스 고려 여부
- 작업 분해의 적절성
- 의존성 순서 검증
- **불필요한 작업 포함 여부 (YAGNI)**

**프롬프트 핵심**:
```
1. 누락: 요청을 완수하기 위해 빠진 단계가 있는가?
2. 과잉: 요청하지 않은 불필요한 작업이 포함되어 있는가?
3. 순서: 작업 순서가 논리적인가?
4. YAGNI: 조기 최적화, 과도한 추상화가 있는가?
```

### 3. 코드 검열 (PostToolUse - Edit/Write)

**트리거**: Claude가 Edit 또는 Write로 코드 수정 시

**검열 목표**:
- 버그 및 로직 오류
- 보안 취약점 (OWASP Top 10)
- 코드 컨벤션 위반
- **불필요한 코드 추가 여부**
- 버전 호환성 (Java/Spring 버전)
- DB 호환성

**프롬프트 핵심**:
```
1. 버그: 로직 오류, null 참조, 경계 조건 문제가 있는가?
2. 보안: SQL 인젝션, XSS, 인증 우회 등 취약점이 있는가?
3. 버전 호환성: Java/Spring 버전에서 지원되는 API인가?
4. DB 호환성: DB 종류에 맞는 쿼리/문법인가?
5. 과잉: 요청하지 않은 리팩토링, 주석, 기능 추가가 있는가?
6. 컨벤션: 기존 코드 스타일과 일치하는가?
```

### 4. 테스트 검열 (PostToolUse - Bash)

**트리거**: Claude가 Bash로 테스트 명령 실행 시 (mvn test, gradle test 등)

**검열 목표**:
- 테스트 커버리지 적절성
- 테스트 케이스 누락 (엣지 케이스, 예외 상황)
- 테스트 품질 (의미 있는 assertion)
- **불필요한 테스트** (중복 검증)

**프롬프트 핵심**:
```
1. 커버리지: 핵심 비즈니스 로직이 테스트되고 있는가?
2. 엣지 케이스: null, 빈 값, 경계값 테스트가 있는가?
3. 예외 처리: 예외 상황 테스트가 있는가?
4. 품질: assertion이 의미 있는가?
5. 중복: 불필요한 중복 테스트가 있는가?
6. Mocking: 적절한 수준의 mocking인가?
```

### 5. 종합 검열 (Stop)

**트리거**: Claude가 응답 완료 시

**검열 목표**:
- 원래 요청 대비 완료율
- 누락된 작업 확인
- **불필요하게 추가된 작업** 식별
- 계획과 실제 결과물 일치 여부

**프롬프트 핵심**:
```
1. 완료율: 원래 요청의 모든 항목이 구현되었는가?
2. 계획 준수: 계획대로 작업이 진행되었는가?
3. 과잉 작업: 요청하지 않은 변경이 있는가?
4. 일관성: 변경사항들이 서로 충돌하지 않는가?
5. 빌드 가능: 변경 후 프로젝트가 정상 빌드될 것으로 보이는가?
```

---

## 재작업 메커니즘

### 심각도 분류

| 심각도 | 트리거 키워드 | 동작 |
|--------|--------------|------|
| CRITICAL | ❌, FAIL, security, injection | 즉시 재작업 (continue: false) |
| HIGH | 버그, bug, 누락, missing | 재작업 요청 (continue: false) |
| MEDIUM | ⚠️, WARN, consider | 경고 표시 (continue: true) |
| LOW | ✓, OK, good | 정보 표시 (continue: true) |

### 재작업 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                        작업 시작                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│  [1] 계획 수립 (TodoWrite)                                       │
│       ↓                                                          │
│  [검열] → CRITICAL/HIGH? ─YES→ 재작업 요청 ─→ [1]로 돌아감       │
│       ↓ NO                                                       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│  [2] 코드 작성 (Edit/Write)                                      │
│       ↓                                                          │
│  [검열] → CRITICAL/HIGH? ─YES→ 재작업 요청 ─→ [2]로 돌아감       │
│       ↓ NO                                                       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│  [3] 테스트 (Bash)                                               │
│       ↓                                                          │
│  [검열] → CRITICAL/HIGH? ─YES→ 재작업 요청 ─→ [2] 또는 [3]       │
│       ↓ NO                                                       │
└─────────────────────────┬───────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│  [4] 완료 (Stop)                                                 │
│       ↓                                                          │
│  [종합검열] → FAIL? ─YES→ 재작업 요청 ─→ 해당 단계로 돌아감      │
│       ↓ NO                                                       │
│                    ✅ 작업 완료                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 무한 루프 방지

- 각 검열 단계별 최대 재시도 횟수 제한 (기본 3회)
- 최대 재시도 초과 시 경고만 표시하고 진행
- 세션 ID + 검열 타입별 재시도 카운트 관리

---

## 다중 LLM 오케스트레이터

### LLM별 역할 분담

| LLM | 강점 | 담당 검열 영역 |
|-----|------|---------------|
| Gemini | 긴 컨텍스트 처리 | 전체 맥락 분석, 누락 검출, 아키텍처 |
| Copilot | 코드 특화 | 버그, 컨벤션, 보안 취약점 |
| OpenAI (확장) | 범용 추론 | 로직 검증, 엣지 케이스 |

### 병렬 실행

```bash
# 병렬 실행으로 응답 시간 최소화
GEMINI_RESULT=$("$HOOKS_DIR/adapters/gemini.sh" "$PROMPT" &)
COPILOT_RESULT=$("$HOOKS_DIR/adapters/copilot.sh" "$PROMPT" &)
wait
```

### 결과 취합

각 LLM의 결과를 취합하여 심각도 판단 후 JSON 출력:

```json
{
  "continue": true|false,
  "stopReason": "재작업 필요시 사유",
  "systemMessage": "🔍 검열 결과:\n[Gemini] ...\n[Copilot] ..."
}
```

---

## 설정 파일

### config.json

```json
{
  "enabled_adapters": ["gemini", "copilot"],
  "timeout_seconds": 60,
  "parallel_execution": true,
  "fail_on_adapter_error": false,
  "rework_settings": {
    "max_retries": 3,
    "critical_triggers": ["❌", "security", "injection", "FAIL"],
    "high_triggers": ["버그", "bug", "누락", "missing"],
    "auto_rework_on": ["critical", "high"],
    "warn_only_on": ["medium", "low"]
  },
  "stage_settings": {
    "plan": { "enabled": true, "max_retries": 2 },
    "code": { "enabled": true, "max_retries": 3 },
    "test": { "enabled": true, "max_retries": 2 },
    "final": { "enabled": true, "max_retries": 2 }
  }
}
```

---

## 구현 순서

1. **기반 구조 구축**
   - 디렉토리 구조 생성
   - config.json 작성
   - settings.json에 hooks 설정 추가

2. **프로젝트 컨텍스트 수집**
   - collect-project-context.sh 구현
   - Java/Spring/DB 정보 파싱 로직

3. **LLM Adapters 구현**
   - gemini.sh (Gemini CLI 설치 필요)
   - copilot.sh (이미 설치됨)

4. **오케스트레이터 구현**
   - review-orchestrator.sh
   - 심각도 분류 로직
   - 재작업 판단 로직

5. **단계별 검열 스크립트**
   - review-plan.sh
   - review-code.sh
   - review-test.sh
   - review-final.sh

6. **프롬프트 템플릿**
   - prompts/*.txt

7. **테스트 및 검증**
   - 각 단계별 동작 확인
   - 재작업 메커니즘 검증
   - 무한 루프 방지 확인

---

## 확장 계획 (방식 B - MCP)

A 방식으로 검증 완료 후, MCP 서버로 확장 가능:

- 같은 스크립트를 MCP 서버 내부에서 호출
- Claude가 능동적으로 검열 요청 가능
- 더 정교한 상호작용 지원

```
[A 방식] hooks/review-code.sh
    ↓
[B 방식] mcp-server/index.ts → spawn("./hooks/review-code.sh")
```

---

## 참고 자료

- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Hooks Guide](https://code.claude.com/docs/en/hooks-guide)
