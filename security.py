"""
보안 모듈 - 입력 검증, 민감정보 마스킹, LLM 응답 검증
"""
import re
import json
from typing import Dict, Any, List, Optional
from pathlib import Path


class SecurityValidator:
    def __init__(self, config: Dict[str, Any]):
        security_config = config.get("security", {})
        self.mask_sensitive = security_config.get("mask_sensitive_data", True)
        self.allowed_extensions = security_config.get("allowed_file_extensions", [])
        self.sensitive_patterns = security_config.get("sensitive_patterns", [
            "password", "api_key", "secret", "token", "credential",
            "private_key", "access_key", "auth_token"
        ])
        self.validate_response = security_config.get("validate_llm_response", True)

    def validate_file_path(self, file_path: str) -> bool:
        """허용된 파일 확장자인지 검증"""
        if not self.allowed_extensions:
            return True
        path = Path(file_path)
        return path.suffix.lower() in self.allowed_extensions

    def mask_sensitive_data(self, content: str) -> str:
        """민감정보 패턴 마스킹"""
        if not self.mask_sensitive:
            return content

        masked = content
        for pattern in self.sensitive_patterns:
            # key=value 형태 마스킹
            regex = rf'({pattern}\s*[=:]\s*)["\']?([^"\'\s\n]+)["\']?'
            masked = re.sub(regex, r'\1***MASKED***', masked, flags=re.IGNORECASE)

            # JSON 형태 마스킹
            json_regex = rf'("{pattern}"\s*:\s*)["\']([^"\']+)["\']'
            masked = re.sub(json_regex, r'\1"***MASKED***"', masked, flags=re.IGNORECASE)

        return masked

    def sanitize_input(self, text: str) -> str:
        """명령 인젝션 방지를 위한 입력 정제"""
        # 쉘 메타문자 이스케이프
        dangerous_chars = ['`', '$', '$(', '${', ';', '&&', '||', '|', '>', '<', '\n']
        sanitized = text
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        return sanitized

    def validate_llm_response(self, response: str) -> Dict[str, Any]:
        """LLM 응답이 올바른 JSON 형식인지 검증"""
        if not self.validate_response:
            return {"valid": True, "data": response}

        try:
            data = json.loads(response)

            # 필수 필드 검증
            required_fields = ["severity", "issues"]
            for field in required_fields:
                if field not in data:
                    return {
                        "valid": False,
                        "error": f"Missing required field: {field}",
                        "data": None
                    }

            # severity 값 검증
            valid_severities = ["OK", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
            if data["severity"] not in valid_severities:
                return {
                    "valid": False,
                    "error": f"Invalid severity: {data['severity']}",
                    "data": None
                }

            return {"valid": True, "data": data}

        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "error": f"Invalid JSON: {str(e)}",
                "data": None
            }

    def extract_code_safely(self, tool_input: Dict[str, Any]) -> Optional[str]:
        """도구 입력에서 안전하게 코드 추출"""
        code = None

        # Edit 도구의 경우
        if "new_string" in tool_input:
            code = tool_input.get("new_string", "")
        # Write 도구의 경우
        elif "content" in tool_input:
            code = tool_input.get("content", "")

        if code:
            return self.mask_sensitive_data(code)
        return None


def load_config() -> Dict[str, Any]:
    """설정 파일 로드"""
    config_path = Path("~/.claude/hooks/config.json").expanduser()
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


# 전역 인스턴스
_validator: Optional[SecurityValidator] = None

def get_security_validator() -> SecurityValidator:
    global _validator
    if _validator is None:
        config = load_config()
        _validator = SecurityValidator(config)
    return _validator
