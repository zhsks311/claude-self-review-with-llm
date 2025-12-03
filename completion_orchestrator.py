#!/usr/bin/env python3
"""
완료 시점 검토 오케스트레이터
모든 TODO가 완료되면 Claude 셀프 리뷰 + 외부 LLM 검토 실행

사용법:
    echo '{"session_id": "...", "tool_input": {"todos": [...]}, ...}' | python completion_orchestrator.py
"""
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from adapters import GeminiAdapter, CopilotAdapter, ReviewResult
from adapters.base import Severity
from adapters.claude_self import ClaudeSelfAdapter
from state_manager import get_state_manager
from security import get_security_validator, load_config
from todo_state_detector import TodoStateDetector
from intent_extractor import IntentExtractor
from quota_monitor import get_quota_monitor
from debate_orchestrator import DebateOrchestrator


class AuditLogger:
    """감사 로그 기록"""

    def __init__(self, log_dir: str = "~/.claude/hooks/logs"):
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event: Dict[str, Any]):
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"completion-audit-{today}.jsonl"

        event["timestamp"] = datetime.now().isoformat()

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


class CompletionOrchestrator:
    """완료 시점 검토 오케스트레이터"""

    def __init__(self):
        self.config = load_config()
        self.state_manager = get_state_manager()
        self.security = get_security_validator()
        self.audit_logger = AuditLogger()
        self.todo_detector = TodoStateDetector(self.state_manager)
        self.intent_extractor = IntentExtractor()
        self.quota_monitor = get_quota_monitor()
        self.debate_orchestrator = DebateOrchestrator(self.config)

        # 어댑터 초기화
        self.self_adapter = ClaudeSelfAdapter(self.config)
        self.external_adapters = self._init_external_adapters()

    def _init_external_adapters(self) -> List:
        """외부 LLM 어댑터 초기화 (쿼터 체크 포함)"""
        adapters = []
        completion_config = self.config.get("completion_review", {})

        if not completion_config.get("include_external_review", True):
            return adapters

        enabled = self.config.get("enabled_adapters", ["gemini", "copilot"])
        # 쿼터 사용 가능한 어댑터만 필터링
        available = self.quota_monitor.get_available_adapters(enabled)

        if "gemini" in available:
            adapter = GeminiAdapter(self.config)
            if adapter.is_available():
                adapters.append(adapter)

        if "copilot" in available:
            adapter = CopilotAdapter(self.config)
            if adapter.is_available():
                adapters.append(adapter)

        return adapters

    def _build_context(self, hook_input: Dict[str, Any], todos: List[Dict]) -> Dict[str, Any]:
        """컨텍스트 구축"""
        transcript_path = hook_input.get("transcript_path")

        # 의도 추출
        intent_info = {}
        if transcript_path:
            intent_info = self.intent_extractor.extract_from_transcript(transcript_path)

        return {
            "session_id": hook_input.get("session_id", "unknown"),
            "todos": todos,
            "combined_intent": intent_info.get("combined_intent", ""),
            "original_request": intent_info.get("original_request", ""),
            "message_count": intent_info.get("message_count", 0),
            "cwd": hook_input.get("cwd", "")
        }

    def _load_prompt(self, prompt_name: str) -> str:
        """프롬프트 로드"""
        prompt_path = Path("~/.claude/hooks/prompts").expanduser() / f"{prompt_name}.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        # 기본 프롬프트
        return """당신은 시니어 소프트웨어 아키텍트입니다.
작업 완료 상태를 검토하고 다음을 확인해주세요:
1. 사용자 요청이 모두 구현되었는가?
2. 빠진 기능이나 요구사항이 있는가?
3. 요청하지 않은 불필요한 기능이 추가되었는가?

JSON 형식으로 응답해주세요:
{
  "severity": "OK|LOW|MEDIUM|HIGH|CRITICAL",
  "issues": [{"description": "...", "severity": "...", "suggestion": "..."}]
}"""

    def _run_parallel_reviews(self, context: Dict[str, Any]) -> List[ReviewResult]:
        """병렬로 리뷰 실행 (쿼터 모니터링 포함)"""
        results = []
        completion_config = self.config.get("completion_review", {})

        # 셀프 리뷰 (서브에이전트 활용)
        if completion_config.get("include_self_review", True):
            self_result = self.self_adapter.review("", context)
            results.append(self_result)

        # 외부 LLM 리뷰 (쿼터 체크됨)
        # 매 호출마다 어댑터 재초기화 (쿼터 상태 반영)
        self.external_adapters = self._init_external_adapters()

        if self.external_adapters:
            prompt = self._load_prompt("completion_external")

            full_prompt = f"""{prompt}

## 사용자 원래 요청:
{context.get("combined_intent", "N/A")}

## 완료된 작업 목록:
{self._format_todos(context.get("todos", []))}
"""

            with ThreadPoolExecutor(max_workers=len(self.external_adapters)) as executor:
                futures = {
                    executor.submit(adapter.review, full_prompt, context): adapter
                    for adapter in self.external_adapters
                }
                for future in as_completed(futures):
                    adapter = futures[future]
                    try:
                        result = future.result()
                        # 쿼터 모니터링: 성공/실패 기록
                        if result.success:
                            self.quota_monitor.record_success(adapter.name)
                        else:
                            self.quota_monitor.record_failure(adapter.name, result.error or "Unknown error")
                        results.append(result)
                    except Exception as e:
                        self.quota_monitor.record_failure(adapter.name, str(e))
                        results.append(ReviewResult(
                            adapter_name=adapter.name,
                            severity=Severity.OK,
                            issues=[],
                            raw_response="",
                            success=False,
                            error=str(e)
                        ))

        return results

    def _format_todos(self, todos: List[Dict]) -> str:
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

    def _build_output(
        self,
        results: List[ReviewResult],
        context: Dict[str, Any],
        debate_result: Optional['DebateRound'] = None
    ) -> Dict[str, Any]:
        """출력 생성 (조건부 블록 로직)"""
        from debate_orchestrator import DebateRound  # Type hint용

        messages = []

        # 셀프 리뷰 메시지 (Claude에게 검토 요청)
        for r in results:
            if r.is_self_review:
                messages.append(r.raw_response)

        # 외부 LLM 결과
        external_results = [r for r in results if not r.is_self_review and r.success]
        final_severity = Severity.OK

        # 토론이 있었으면 토론 결과의 severity 사용
        if debate_result and debate_result.final_severity:
            final_severity = debate_result.final_severity
            messages.append(self.debate_orchestrator.format_debate_result(debate_result))
        elif external_results:
            final_severity = max((r.severity for r in external_results), default=Severity.OK)

            if final_severity != Severity.OK:
                messages.append(f"\n### 외부 LLM 검토 결과 ({final_severity.value}):")
                for r in external_results:
                    if r.issues:
                        messages.append(f"\n**{r.adapter_name}**:")
                        for issue in r.issues:
                            messages.append(f"- [{issue.severity.value}] {issue.description}")
                            if issue.suggestion:
                                messages.append(f"  → 제안: {issue.suggestion}")

        # 조건부 블록: CRITICAL만 블록, 나머지는 경고만
        should_block = final_severity == Severity.CRITICAL

        if should_block:
            messages.append("\n⛔ **CRITICAL 이슈 발견**: 작업이 블록되었습니다. 위 문제를 해결한 후 다시 시도해주세요.")

        return {
            "continue": not should_block,
            "systemMessage": "\n".join(messages)
        }

    def orchestrate(self, hook_input: Dict[str, Any]) -> Dict[str, Any]:
        """메인 오케스트레이션"""
        session_id = hook_input.get("session_id", "unknown")
        todos = hook_input.get("tool_input", {}).get("todos", [])

        # 1. 완료 상태 확인
        todo_state = self.todo_detector.detect_completion(session_id, todos)

        if not todo_state.just_completed:
            # 방금 완료된 게 아니면 스킵
            return {"continue": True, "systemMessage": ""}

        # 2. 검토 횟수 확인 (무한 루프 방지)
        completion_config = self.config.get("completion_review", {})
        max_reviews = completion_config.get("max_reviews", 3)
        review_count = self.state_manager.get_completion_review_count(session_id)

        if review_count >= max_reviews:
            self.audit_logger.log({
                "event_type": "max_reviews_reached",
                "session_id": session_id,
                "review_count": review_count
            })
            return {
                "continue": True,
                "systemMessage": f"[완료검토] 최대 검토 횟수({max_reviews})에 도달. 진행합니다."
            }

        self.state_manager.increment_completion_review_count(session_id)

        # 3. 컨텍스트 구축
        context = self._build_context(hook_input, todos)

        # 4. 병렬 리뷰 실행
        results = self._run_parallel_reviews(context)

        # 4.5. 토론 필요 여부 확인 및 실행
        debate_result = None
        external_results = [r for r in results if not r.is_self_review and r.success]

        if external_results:
            needs_debate, reason = self.debate_orchestrator.needs_debate(external_results)

            if needs_debate:
                # 토론 실행
                debate_result = self.debate_orchestrator.run_debate(
                    adapters=self.external_adapters,
                    initial_results=external_results,
                    original_prompt=self._load_prompt("completion_external"),
                    context=context
                )

                # 토론 결과로 외부 LLM 결과 교체
                self_results = [r for r in results if r.is_self_review]
                results = self_results + debate_result.results

        # 5. 감사 로그 (쿼터 상태 + 토론 정보 포함)
        audit_data = {
            "event_type": "completion_review",
            "session_id": session_id,
            "review_count": review_count + 1,
            "todo_count": len(todos),
            "intent_length": len(context.get("combined_intent", "")),
            "llm_results": [r.to_dict() for r in results if not r.is_self_review],
            "quota_status": self.quota_monitor.get_summary()
        }

        if debate_result:
            audit_data["debate"] = {
                "triggered": True,
                "reason": reason,
                "rounds": debate_result.round_num,
                "consensus_reached": debate_result.consensus_reached,
                "final_severity": debate_result.final_severity.value if debate_result.final_severity else None
            }

        self.audit_logger.log(audit_data)

        # 6. 출력 생성
        return self._build_output(results, context, debate_result)


def main():
    """CLI 엔트리포인트"""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({
            "continue": True,
            "systemMessage": "[완료검토] 입력 파싱 실패"
        }))
        sys.exit(0)

    orchestrator = CompletionOrchestrator()
    result = orchestrator.orchestrate(input_data)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
