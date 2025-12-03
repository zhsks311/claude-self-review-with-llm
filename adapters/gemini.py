"""
Gemini API Adapter (v2)
- REST API 직접 호출 (CLI 대체)
- 무료 티어: 1500 requests/day
- 모델: gemini-1.5-flash (빠르고 저렴)
"""
import os
import sys
import ssl
import time
import json
import shutil
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from pathlib import Path

# certifi는 선택적 (Windows에서 없을 수 있음)
try:
    import certifi
    HAS_CERTIFI = True
except ImportError:
    HAS_CERTIFI = False

from .base import LLMAdapter, ReviewResult, Severity

# API Key Loader 임포트 (상위 디렉토리에서)
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from api_key_loader import get_api_key
except ImportError:
    def get_api_key(key_name: str, default=None):
        return os.environ.get(key_name, default)


class GeminiAdapter(LLMAdapter):
    """Gemini API를 사용한 리뷰 어댑터 (v2)"""

    API_BASE = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-2.5-flash-lite"

    def __init__(self, config: Dict[str, Any]):
        super().__init__("gemini", config)
        gemini_config = config.get("gemini", {})

        # API 키: config > api_key_loader > 환경변수 순서로 시도
        config_key = gemini_config.get("api_key", "")
        if config_key and not config_key.startswith("${"):
            self.api_key = config_key
        else:
            self.api_key = get_api_key("GEMINI_API_KEY")

        self.model = gemini_config.get("model", self.DEFAULT_MODEL)
        self.use_api = gemini_config.get("use_api", True)
        # CLI 폴백용
        self.cli_path = shutil.which("gemini")

    def is_available(self) -> bool:
        """API 키 또는 CLI 사용 가능 여부"""
        if self.use_api and self.api_key:
            return True
        return self.cli_path is not None

    def review(self, prompt: str, context: Dict[str, Any]) -> ReviewResult:
        if not self.is_available():
            return ReviewResult(
                adapter_name=self.name,
                severity=Severity.OK,
                issues=[],
                raw_response="",
                success=False,
                error="Gemini not available (no API key or CLI)"
            )

        start_time = time.time()
        full_prompt = self._build_prompt(prompt, context)

        try:
            # API 우선, CLI 폴백
            if self.use_api and self.api_key:
                response = self._call_api(full_prompt)
            else:
                response = self._call_cli(full_prompt)

            duration_ms = int((time.time() - start_time) * 1000)

            if response is None:
                return ReviewResult(
                    adapter_name=self.name,
                    severity=Severity.OK,
                    issues=[],
                    raw_response="",
                    success=False,
                    error="Empty response from Gemini",
                    duration_ms=duration_ms
                )

            review_result = self.parse_response(response)
            review_result.duration_ms = duration_ms
            return review_result

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            return ReviewResult(
                adapter_name=self.name,
                severity=Severity.OK,
                issues=[],
                raw_response="",
                success=False,
                error=f"API error {e.code}: {error_body}",
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

    def _call_api(self, prompt: str) -> Optional[str]:
        """Gemini REST API 직접 호출"""
        url = f"{self.API_BASE}/models/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2000
            }
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )

        # SSL 컨텍스트 설정 (macOS/Windows 인증서 문제 해결)
        try:
            if HAS_CERTIFI:
                ssl_context = ssl.create_default_context(cafile=certifi.where())
            else:
                ssl_context = ssl.create_default_context()
        except Exception:
            ssl_context = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=self.timeout, context=ssl_context) as response:
            result = json.loads(response.read().decode('utf-8'))
            # Gemini API 응답 구조: candidates[0].content.parts[0].text
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return None

    def _call_cli(self, prompt: str) -> Optional[str]:
        """Gemini CLI 폴백"""
        result = subprocess.run(
            [self.cli_path, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=self.timeout
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI error: {result.stderr}")
        return result.stdout

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
