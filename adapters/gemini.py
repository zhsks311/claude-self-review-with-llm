"""
Gemini CLI Adapter
"""
import subprocess
import time
import shutil
from typing import Dict, Any

from .base import LLMAdapter, ReviewResult, Severity


class GeminiAdapter(LLMAdapter):
    """Gemini CLI를 사용한 리뷰 어댑터"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("gemini", config)
        self.cli_path = shutil.which("gemini")

    def is_available(self) -> bool:
        return self.cli_path is not None

    def review(self, prompt: str, context: Dict[str, Any]) -> ReviewResult:
        if not self.is_available():
            return ReviewResult(
                adapter_name=self.name,
                severity=Severity.OK,
                issues=[],
                raw_response="",
                success=False,
                error="Gemini CLI not found"
            )

        start_time = time.time()

        try:
            # 컨텍스트를 프롬프트에 포함
            full_prompt = self._build_prompt(prompt, context)

            # Gemini CLI 호출
            result = subprocess.run(
                [self.cli_path, "-p", full_prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.returncode != 0:
                return ReviewResult(
                    adapter_name=self.name,
                    severity=Severity.OK,
                    issues=[],
                    raw_response=result.stderr,
                    success=False,
                    error=f"CLI error: {result.stderr}",
                    duration_ms=duration_ms
                )

            # 응답 파싱
            review_result = self.parse_response(result.stdout)
            review_result.duration_ms = duration_ms
            return review_result

        except subprocess.TimeoutExpired:
            return ReviewResult(
                adapter_name=self.name,
                severity=Severity.OK,
                issues=[],
                raw_response="",
                success=False,
                error=f"Timeout after {self.timeout}s",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return ReviewResult(
                adapter_name=self.name,
                severity=Severity.OK,
                issues=[],
                raw_response="",
                success=False,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000)
            )

    def _build_prompt(self, base_prompt: str, context: Dict[str, Any]) -> str:
        """컨텍스트 정보를 포함한 프롬프트 생성"""
        parts = [base_prompt]

        if context.get("file_path"):
            parts.append(f"\n## 파일 경로\n{context['file_path']}")

        if context.get("diff"):
            parts.append(f"\n## 변경 내용\n```\n{context['diff']}\n```")

        if context.get("code"):
            parts.append(f"\n## 코드\n```\n{context['code']}\n```")

        if context.get("user_request"):
            parts.append(f"\n## 사용자 요청\n{context['user_request']}")

        parts.append("""
## 응답 형식
반드시 아래 JSON 형식으로 응답하세요:
```json
{
  "severity": "OK|LOW|MEDIUM|HIGH|CRITICAL",
  "issues": [
    {
      "description": "문제 설명",
      "severity": "OK|LOW|MEDIUM|HIGH|CRITICAL",
      "location": "파일:라인 (옵션)",
      "suggestion": "수정 제안 (옵션)"
    }
  ]
}
```
""")

        return "\n".join(parts)
