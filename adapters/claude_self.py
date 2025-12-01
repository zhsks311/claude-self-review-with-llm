"""
Claude 셀프 리뷰 어댑터
systemMessage를 통해 Claude에게 자기 작업 검토를 유도

v2: Task 서브에이전트 기본 활용
- code-reviewer 서브에이전트로 독립적인 코드 리뷰 수행
- 메인 Claude와 분리된 관점에서 검토
"""
from typing import Dict, Any, List

from .base import LLMAdapter, ReviewResult, Severity, Issue


class ClaudeSelfAdapter(LLMAdapter):
    """
    Claude 셀프 리뷰 어댑터 v2

    특징:
    - Task 서브에이전트(code-reviewer) 활용
    - 메인 세션과 독립된 관점에서 코드 리뷰
    - 무료, 쿼터 제한 없음
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__("claude_self", config)
        self.use_subagent = config.get("completion_review", {}).get("use_subagent", True)

    def is_available(self) -> bool:
        """항상 사용 가능"""
        return True

    def review(self, prompt: str, context: Dict[str, Any]) -> ReviewResult:
        """
        셀프 리뷰 메시지 생성

        Note: 실제 검토는 하지 않고, Claude에게 검토를 요청하는 메시지만 생성
        """
        message = self._build_self_review_message(context)

        return ReviewResult(
            adapter_name=self.name,
            severity=Severity.OK,  # 셀프 리뷰는 severity 판단 안함
            issues=[],
            raw_response=message,
            success=True,
            is_self_review=True
        )

    def _build_self_review_message(self, context: Dict[str, Any]) -> str:
        """셀프 리뷰 요청 메시지 생성"""
        todos = context.get("todos", [])
        combined_intent = context.get("combined_intent", "")
        original_request = context.get("original_request", "")
        cwd = context.get("cwd", "")

        todos_formatted = self._format_todos(todos)

        # 원래 요청이 너무 길면 요약본 사용
        intent_display = combined_intent if combined_intent else original_request
        if len(intent_display) > 3000:
            intent_display = intent_display[:3000] + "\n\n[...이하 생략...]"

        if self.use_subagent:
            return self._build_subagent_review_message(
                intent_display, todos_formatted, cwd
            )
        else:
            return self._build_simple_review_message(
                intent_display, todos_formatted
            )

    def _build_subagent_review_message(
        self, intent: str, todos: str, cwd: str
    ) -> str:
        """서브에이전트를 활용한 리뷰 요청 메시지"""
        return f"""## 작업 완료 - 서브에이전트 코드 리뷰 요청

모든 TODO가 완료되었습니다. **Task 도구로 code-reviewer 서브에이전트를 실행**하여 독립적인 관점에서 코드를 검토해주세요.

### 실행 방법:
Task 도구를 사용하여 다음과 같이 code-reviewer 에이전트를 실행하세요:

```
subagent_type: "pr-review-toolkit:code-reviewer"
prompt: |
  다음 작업의 코드 리뷰를 수행해주세요.

  ## 사용자 요청:
  {intent[:1500]}

  ## 완료된 작업:
  {todos}

  ## 작업 디렉토리: {cwd}

  최근 변경된 파일들을 git diff로 확인하고 리뷰해주세요.
```

### 리뷰 후 조치:
- **CRITICAL/HIGH 이슈**: 즉시 수정
- **MEDIUM 이슈**: 수정 권장, 사용자 판단
- **LOW 이슈**: 참고용

서브에이전트 리뷰 결과를 바탕으로 필요한 수정을 진행해주세요."""

    def _build_simple_review_message(self, intent: str, todos: str) -> str:
        """구조화된 체크리스트 기반 셀프 리뷰 (v3)"""
        return f"""## 작업 완료 - 구조화된 셀프 리뷰

모든 TODO가 완료되었습니다. **아래 체크리스트를 하나씩 검토**하고, 문제 발견 시 즉시 수정하세요.

### 사용자 원래 요청:
{intent}

### 완료된 작업:
{todos}

---

## 필수 체크리스트 (각 항목을 명시적으로 확인)

### 1. 🎯 요구사항 충족
- [ ] 사용자가 요청한 **모든 기능**이 구현되었는가?
- [ ] 요청하지 않은 **불필요한 기능**을 추가하지 않았는가?
- [ ] 암묵적으로 기대되는 **엣지 케이스**를 처리했는가?

### 2. 🔒 보안 (OWASP Top 10)
- [ ] **SQL Injection**: 사용자 입력이 직접 쿼리에 포함되지 않는가?
- [ ] **XSS**: 사용자 입력이 HTML에 이스케이프 없이 출력되지 않는가?
- [ ] **Command Injection**: 사용자 입력이 shell 명령에 포함되지 않는가?
- [ ] **Secrets**: API 키, 비밀번호가 하드코딩되지 않았는가?

### 3. ⚠️ 에러 핸들링
- [ ] 외부 API 호출에 **타임아웃**이 설정되어 있는가?
- [ ] 파일/네트워크 작업에 **예외 처리**가 있는가?
- [ ] 에러 메시지가 **민감 정보를 노출**하지 않는가?

### 4. 🧪 테스트 가능성
- [ ] 작성한 코드가 **테스트 가능한 구조**인가?
- [ ] 테스트가 요청된 경우, **실제로 테스트를 실행**했는가?

### 5. 📝 코드 품질
- [ ] **중복 코드**가 없는가?
- [ ] 변수/함수명이 **명확한 의도**를 표현하는가?
- [ ] 불필요한 **주석이나 디버그 코드**가 남아있지 않은가?

---

## 검토 결과 보고

위 체크리스트를 검토한 후, 다음 형식으로 보고하세요:

```
✅ 통과: [통과한 항목 수]/[전체 항목 수]
⚠️ 발견된 이슈: [있으면 나열]
🔧 수정 필요: [있으면 즉시 수정 진행]
```

**문제 발견 시 보고만 하지 말고, 즉시 수정 작업을 진행하세요.**"""

    def _format_todos(self, todos: List[Dict[str, Any]]) -> str:
        """Todo 목록 포맷팅"""
        if not todos:
            return "(없음)"

        lines = []
        for i, todo in enumerate(todos, 1):
            content = todo.get("content", "")
            status = todo.get("status", "")
            status_icon = "✅" if status == "completed" else "⏳"
            lines.append(f"{i}. {status_icon} {content}")

        return "\n".join(lines)
