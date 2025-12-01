#!/usr/bin/env python3
"""
리뷰 오케스트레이터 - 다중 LLM을 병렬 호출하고 결과를 취합

사용법:
    echo '{"stage": "code", "context": {...}}' | python review_orchestrator.py

stdin 입력 (Claude Code Hook에서 전달):
{
    "session_id": "abc123",
    "tool_name": "Edit",
    "tool_input": {...},
    "transcript_path": "/path/to/transcript.json",
    "cwd": "/project/root"
}
"""
import sys
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from adapters import GeminiAdapter, CopilotAdapter, ReviewResult
from adapters.base import Severity
from state_manager import get_state_manager
from security import get_security_validator, load_config


class AuditLogger:
    """감사 로그 기록"""

    def __init__(self, log_dir: str = "~/.claude/hooks/logs"):
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event: Dict[str, Any]):
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit-{today}.jsonl"

        event["timestamp"] = datetime.now().isoformat()

        with open(log_file, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")


class ReviewOrchestrator:
    """다중 LLM 리뷰 오케스트레이터"""

    def __init__(self):
        self.config = load_config()
        self.state_manager = get_state_manager()
        self.security = get_security_validator()
        self.audit_logger = AuditLogger()

        # 어댑터 초기화
        self.adapters = []
        enabled = self.config.get("enabled_adapters", ["gemini", "copilot"])

        if "gemini" in enabled:
            adapter = GeminiAdapter(self.config)
            if adapter.is_available():
                self.adapters.append(adapter)

        if "copilot" in enabled:
            adapter = CopilotAdapter(self.config)
            if adapter.is_available():
                self.adapters.append(adapter)

    def extract_context(self, hook_input: Dict[str, Any]) -> Dict[str, Any]:
        """Hook 입력에서 동적 컨텍스트 추출"""
        context = {
            "session_id": hook_input.get("session_id", "unknown"),
            "tool_name": hook_input.get("tool_name", ""),
            "cwd": hook_input.get("cwd", ""),
        }

        tool_input = hook_input.get("tool_input", {})

        # Edit 도구: diff 추출
        if "old_string" in tool_input and "new_string" in tool_input:
            context["file_path"] = tool_input.get("file_path", "")
            context["diff"] = f"- {tool_input['old_string']}\n+ {tool_input['new_string']}"
            context["code"] = tool_input.get("new_string", "")

        # Write 도구: 전체 내용
        elif "content" in tool_input:
            context["file_path"] = tool_input.get("file_path", "")
            context["code"] = tool_input.get("content", "")

        # TodoWrite 도구: 계획 추출
        elif "todos" in tool_input:
            context["todos"] = tool_input.get("todos", [])

        # 민감정보 마스킹
        if context.get("code"):
            context["code"] = self.security.mask_sensitive_data(context["code"])
        if context.get("diff"):
            context["diff"] = self.security.mask_sensitive_data(context["diff"])

        return context

    def load_prompt(self, stage: str) -> str:
        """단계별 프롬프트 로드"""
        prompt_path = Path("~/.claude/hooks/prompts").expanduser() / f"{stage}.txt"
        if prompt_path.exists():
            return prompt_path.read_text()

        # 기본 프롬프트
        default_prompts = {
            "plan": "당신은 시니어 개발자입니다. 아래 작업 계획을 검토하고 불필요한 작업(YAGNI), 누락된 사항, 잠재적 문제점을 찾아주세요.",
            "code": "당신은 시니어 코드 리뷰어입니다. 아래 코드 변경을 검토하고 버그, 보안 취약점, 코드 품질 문제를 찾아주세요.",
            "test": "당신은 QA 전문가입니다. 아래 테스트 결과를 분석하고 추가 테스트 필요 여부, 누락된 케이스를 확인해주세요.",
            "final": "당신은 시니어 아키텍트입니다. 전체 작업을 종합적으로 검토하고 최종 품질을 평가해주세요."
        }
        return default_prompts.get(stage, default_prompts["code"])

    def resolve_conflict(self, results: List[ReviewResult]) -> Severity:
        """LLM 의견 충돌 해결"""
        conflict_config = self.config.get("conflict_resolution", {})
        policy = conflict_config.get("policy", "conservative")

        severities = [r.severity for r in results if r.success]

        if not severities:
            return Severity.OK

        if policy == "conservative" or policy == "highest_severity":
            # 가장 높은 심각도 선택
            return max(severities)

        elif policy == "majority_vote":
            # 다수결 (동률 시 높은 심각도)
            from collections import Counter
            counts = Counter(severities)
            max_count = max(counts.values())
            candidates = [s for s, c in counts.items() if c == max_count]
            return max(candidates)

        elif policy == "weighted_vote":
            # 가중치 적용
            weights = conflict_config.get("weights", {})
            weighted_scores = {}
            for result in results:
                if result.success:
                    weight = weights.get(result.adapter_name, 1.0)
                    severity_score = list(Severity).index(result.severity)
                    weighted_scores[result.adapter_name] = severity_score * weight

            if weighted_scores:
                max_adapter = max(weighted_scores, key=weighted_scores.get)
                for result in results:
                    if result.adapter_name == max_adapter:
                        return result.severity

        return max(severities) if severities else Severity.OK

    def run_parallel_reviews(self, prompt: str, context: Dict[str, Any]) -> List[ReviewResult]:
        """병렬로 LLM 리뷰 실행"""
        results = []

        if not self.adapters:
            return results

        parallel = self.config.get("parallel_execution", True)

        if parallel and len(self.adapters) > 1:
            with ThreadPoolExecutor(max_workers=len(self.adapters)) as executor:
                futures = {
                    executor.submit(adapter.review, prompt, context): adapter
                    for adapter in self.adapters
                }
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        adapter = futures[future]
                        results.append(ReviewResult(
                            adapter_name=adapter.name,
                            severity=Severity.OK,
                            issues=[],
                            raw_response="",
                            success=False,
                            error=str(e)
                        ))
        else:
            for adapter in self.adapters:
                try:
                    result = adapter.review(prompt, context)
                    results.append(result)
                except Exception as e:
                    results.append(ReviewResult(
                        adapter_name=adapter.name,
                        severity=Severity.OK,
                        issues=[],
                        raw_response="",
                        success=False,
                        error=str(e)
                    ))

        return results

    def check_override(self, session_id: str) -> bool:
        """Override 체크"""
        override_config = self.config.get("override", {})
        if not override_config.get("enabled", True):
            return False

        # 환경 변수 체크
        if os.environ.get("CLAUDE_SKIP_REVIEW") == "1":
            return True

        # 상태 체크
        return self.state_manager.check_and_consume_override(session_id)

    def check_debounce(self, session_id: str, stage: str) -> bool:
        """Debounce 체크 - True면 스킵해야 함"""
        debounce_config = self.config.get("debounce", {})
        if not debounce_config.get("enabled", True):
            return False

        if stage not in debounce_config.get("stages", ["code"]):
            return False

        seconds = debounce_config.get("seconds", 3)
        return self.state_manager.should_debounce(session_id, stage, seconds)

    def build_system_message(self, results: List[ReviewResult], final_severity: Severity, stage: str) -> str:
        """Claude에게 전달할 시스템 메시지 생성"""
        if final_severity == Severity.OK:
            return f"[자기검열-{stage}] ✅ 검토 통과"

        messages = [f"[자기검열-{stage}] ⚠️ {final_severity.value} 수준 이슈 발견:"]

        for result in results:
            if result.success and result.issues:
                messages.append(f"\n### {result.adapter_name} 피드백:")
                for issue in result.issues:
                    messages.append(f"- [{issue.severity.value}] {issue.description}")
                    if issue.suggestion:
                        messages.append(f"  → 제안: {issue.suggestion}")

        if final_severity in [Severity.CRITICAL, Severity.HIGH]:
            messages.append("\n⚠️ 위 문제들을 수정해주세요.")

        return "\n".join(messages)

    def orchestrate(self, stage: str, hook_input: Dict[str, Any]) -> Dict[str, Any]:
        """메인 오케스트레이션 로직"""
        context = self.extract_context(hook_input)
        session_id = context["session_id"]

        # Override 체크
        if self.check_override(session_id):
            self.audit_logger.log({
                "event_type": "override",
                "session_id": session_id,
                "stage": stage
            })
            return {
                "decision": "continue",
                "systemMessage": f"[자기검열-{stage}] 🔓 Override로 스킵됨"
            }

        # Debounce 체크
        if self.check_debounce(session_id, stage):
            return {
                "decision": "continue",
                "systemMessage": ""  # Debounce 시 메시지 없음
            }

        # Debounce 시간 갱신
        self.state_manager.update_last_call_time(session_id, stage)

        # 프롬프트 로드 및 리뷰 실행
        prompt = self.load_prompt(stage)
        results = self.run_parallel_reviews(prompt, context)

        # 충돌 해결
        final_severity = self.resolve_conflict(results)

        # 시스템 메시지 생성
        system_message = self.build_system_message(results, final_severity, stage)

        # 재시도 로직
        rework_config = self.config.get("rework_settings", {})
        stage_config = self.config.get("stage_settings", {}).get(stage, {})
        max_retries = stage_config.get("max_retries", rework_config.get("max_retries", 3))

        should_continue = True
        if final_severity in [Severity.CRITICAL, Severity.HIGH]:
            retry_count = self.state_manager.get_retry_count(session_id, stage)
            if retry_count < max_retries:
                self.state_manager.increment_retry_count(session_id, stage)
                should_continue = False
                system_message += f"\n\n(재시도 {retry_count + 1}/{max_retries})"
            else:
                system_message += f"\n\n⚠️ 최대 재시도 횟수({max_retries})에 도달. 경고와 함께 진행합니다."

        # 감사 로그
        self.audit_logger.log({
            "event_type": "review",
            "session_id": session_id,
            "stage": stage,
            "llm_results": [r.to_dict() for r in results],
            "final_severity": final_severity.value,
            "continue_decision": should_continue
        })

        return {
            "decision": "continue" if should_continue else "block",
            "systemMessage": system_message
        }


def main():
    """CLI 엔트리포인트"""
    # stdin에서 입력 읽기
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({
            "decision": "continue",
            "systemMessage": "[자기검열] ⚠️ 입력 파싱 실패"
        }))
        sys.exit(0)

    stage = input_data.get("stage", "code")
    hook_input = input_data.get("hook_input", input_data)

    orchestrator = ReviewOrchestrator()
    result = orchestrator.orchestrate(stage, hook_input)

    # Claude Code Hook 형식으로 출력
    output = {}
    if result.get("systemMessage"):
        output["systemMessage"] = result["systemMessage"]

    if result.get("decision") == "block":
        output["continue"] = False
    else:
        output["continue"] = True

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
