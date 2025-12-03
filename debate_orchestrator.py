"""
LLM Debate Orchestrator
이견 발생 시 토론을 통해 합의 도출

동작 방식:
1. 1차 라운드: 각 LLM 독립 리뷰
2. 조건 확인: 이견 or HIGH+ 발견
3. 2차 라운드: 상대 의견 공유 → 재검토
4. 합의 도출 또는 가중 투표
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from adapters.base import LLMAdapter, ReviewResult, Severity, Issue


@dataclass
class DebateRound:
    """토론 라운드 결과"""
    round_num: int
    results: List[ReviewResult]
    consensus_reached: bool
    final_severity: Optional[Severity] = None


class DebateOrchestrator:
    """LLM 토론 오케스트레이터"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        debate_config = config.get("debate", {})
        self.enabled = debate_config.get("enabled", False)
        self.max_rounds = debate_config.get("max_rounds", 2)
        self.trigger_on_disagreement = debate_config.get("trigger_on_disagreement", True)
        self.trigger_on_high = debate_config.get("trigger_on_high_severity", True)

    def needs_debate(self, results: List[ReviewResult]) -> Tuple[bool, str]:
        """토론 필요 여부 판단"""
        if not self.enabled:
            return False, "debate disabled"

        successful = [r for r in results if r.success and not r.is_self_review]
        if len(successful) < 1:
            return False, "not enough results"

        severities = [r.severity for r in successful]

        # 조건 1: HIGH+ 발견
        if self.trigger_on_high:
            if any(s in [Severity.HIGH, Severity.CRITICAL] for s in severities):
                return True, "high severity found"

        # 조건 2: 심각도 불일치 (2개 이상 결과가 있을 때)
        if self.trigger_on_disagreement and len(severities) >= 2:
            severity_levels = set(severities)
            if len(severity_levels) > 1:
                # 2단계 이상 차이 (예: OK vs HIGH)
                ordered = [Severity.OK, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
                indices = [ordered.index(s) for s in severities]
                if max(indices) - min(indices) >= 2:
                    return True, "significant disagreement"

        return False, "no debate needed"

    def build_debate_prompt(
        self,
        original_prompt: str,
        other_results: List[ReviewResult],
        round_num: int
    ) -> str:
        """토론 프롬프트 생성"""
        others_opinion = self._format_others_opinions(other_results)

        return f"""## 코드 리뷰 토론 - Round {round_num}

다른 리뷰어의 의견을 검토하고 최종 판단을 내려주세요.

### 다른 리뷰어 의견:
{others_opinion}

### 원래 리뷰 요청:
{original_prompt}

### 지침:
1. 다른 리뷰어의 의견을 신중히 검토하세요
2. 동의하면 그 이유를, 반대하면 근거를 제시하세요
3. 최종 severity와 이슈 목록을 결정하세요
4. 새로운 이슈를 발견했다면 추가하세요

### 응답 형식:
```json
{{
  "severity": "OK|LOW|MEDIUM|HIGH|CRITICAL",
  "agree_with_others": true/false,
  "reasoning": "동의/반대 이유",
  "issues": [
    {{
      "description": "문제 설명",
      "severity": "...",
      "suggestion": "수정 제안"
    }}
  ]
}}
```
"""

    def _format_others_opinions(self, results: List[ReviewResult]) -> str:
        """다른 리뷰어 의견 포맷팅"""
        parts = []
        for r in results:
            parts.append(f"**{r.adapter_name}** (Severity: {r.severity.value}):")
            if r.issues:
                for issue in r.issues:
                    parts.append(f"  - [{issue.severity.value}] {issue.description}")
                    if issue.suggestion:
                        parts.append(f"    → 제안: {issue.suggestion}")
            else:
                parts.append("  (이슈 없음)")
            parts.append("")
        return "\n".join(parts)

    def run_debate(
        self,
        adapters: List[LLMAdapter],
        initial_results: List[ReviewResult],
        original_prompt: str,
        context: Dict[str, Any]
    ) -> DebateRound:
        """토론 실행"""
        current_results = initial_results.copy()

        for round_num in range(2, self.max_rounds + 2):  # 2라운드부터 시작
            new_results = []

            for adapter in adapters:
                # 해당 어댑터 이외의 결과를 보여줌
                other_results = [r for r in current_results if r.adapter_name != adapter.name]

                if not other_results:
                    continue

                debate_prompt = self.build_debate_prompt(
                    original_prompt, other_results, round_num
                )

                result = adapter.review(debate_prompt, context)
                new_results.append(result)

            if not new_results:
                break

            current_results = new_results

            # 합의 확인
            consensus, final_severity = self._check_consensus(current_results)
            if consensus:
                return DebateRound(
                    round_num=round_num,
                    results=current_results,
                    consensus_reached=True,
                    final_severity=final_severity
                )

        # 합의 실패 → 가중 투표
        final_severity = self._weighted_vote(current_results)
        return DebateRound(
            round_num=self.max_rounds + 1,
            results=current_results,
            consensus_reached=False,
            final_severity=final_severity
        )

    def _check_consensus(self, results: List[ReviewResult]) -> Tuple[bool, Optional[Severity]]:
        """합의 확인"""
        successful = [r for r in results if r.success]
        if not successful:
            return False, None

        severities = [r.severity for r in successful]
        unique = set(severities)

        # 모두 같은 severity면 합의
        if len(unique) == 1:
            return True, severities[0]

        # 1단계 차이까지는 합의로 간주 (예: LOW와 MEDIUM)
        ordered = [Severity.OK, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        indices = [ordered.index(s) for s in severities]
        if max(indices) - min(indices) <= 1:
            # 더 높은 쪽으로 합의
            return True, ordered[max(indices)]

        return False, None

    def _weighted_vote(self, results: List[ReviewResult]) -> Severity:
        """가중 투표로 최종 결정"""
        weights = self.config.get("conflict_resolution", {}).get("weights", {})

        severity_scores = {
            Severity.OK: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4
        }

        total_weight = 0
        weighted_score = 0

        for r in results:
            if not r.success:
                continue
            weight = weights.get(r.adapter_name, 1.0)
            score = severity_scores.get(r.severity, 0)
            weighted_score += weight * score
            total_weight += weight

        if total_weight == 0:
            return Severity.OK

        avg_score = weighted_score / total_weight

        # 반올림하여 severity 결정
        score_to_severity = {v: k for k, v in severity_scores.items()}
        rounded_score = round(avg_score)
        return score_to_severity.get(rounded_score, Severity.MEDIUM)

    def format_debate_result(self, debate_round: DebateRound) -> str:
        """토론 결과 포맷팅"""
        parts = [
            f"\n### 🗣️ LLM 토론 결과 (Round {debate_round.round_num})",
            f"합의 도달: {'✅ 예' if debate_round.consensus_reached else '❌ 아니오 (가중 투표)'}",
            f"최종 Severity: **{debate_round.final_severity.value}**",
            ""
        ]

        for r in debate_round.results:
            if r.success:
                parts.append(f"**{r.adapter_name}**: {r.severity.value}")
                if r.issues:
                    for issue in r.issues[:3]:  # 최대 3개
                        parts.append(f"  - {issue.description}")

        return "\n".join(parts)
