"""
LLM Adapter 기본 클래스
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum


class Severity(Enum):
    OK = "OK"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_string(cls, value: str) -> "Severity":
        try:
            return cls(value.upper())
        except ValueError:
            return cls.OK

    def __lt__(self, other):
        order = [Severity.OK, Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        return order.index(self) < order.index(other)


@dataclass
class Issue:
    description: str
    severity: Severity
    location: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ReviewResult:
    adapter_name: str
    severity: Severity
    issues: List[Issue]
    raw_response: str
    success: bool = True
    error: Optional[str] = None
    duration_ms: int = 0
    is_self_review: bool = False  # Claude 셀프 리뷰 여부

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter": self.adapter_name,
            "severity": self.severity.value,
            "issues": [
                {
                    "description": i.description,
                    "severity": i.severity.value,
                    "location": i.location,
                    "suggestion": i.suggestion
                }
                for i in self.issues
            ],
            "success": self.success,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "is_self_review": self.is_self_review
        }


class LLMAdapter(ABC):
    """LLM Adapter 기본 인터페이스"""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.timeout = config.get("timeout_seconds", 60)

    @abstractmethod
    def review(self, prompt: str, context: Dict[str, Any]) -> ReviewResult:
        """
        코드 리뷰 수행

        Args:
            prompt: 리뷰 프롬프트
            context: 동적 컨텍스트 (diff, file_path 등)

        Returns:
            ReviewResult
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """어댑터가 사용 가능한지 확인 (CLI 설치 여부 등)"""
        pass

    def parse_response(self, response: str) -> ReviewResult:
        """
        LLM 응답을 파싱하여 ReviewResult 생성

        기대하는 JSON 형식:
        {
            "severity": "OK|LOW|MEDIUM|HIGH|CRITICAL",
            "issues": [
                {
                    "description": "문제 설명",
                    "severity": "...",
                    "location": "파일:라인",
                    "suggestion": "수정 제안"
                }
            ]
        }
        """
        import json
        import re

        try:
            # JSON 블록 추출 시도
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)

            data = json.loads(response)
            severity = Severity.from_string(data.get("severity", "OK"))
            issues = [
                Issue(
                    description=i.get("description", ""),
                    severity=Severity.from_string(i.get("severity", "OK")),
                    location=i.get("location"),
                    suggestion=i.get("suggestion")
                )
                for i in data.get("issues", [])
            ]

            return ReviewResult(
                adapter_name=self.name,
                severity=severity,
                issues=issues,
                raw_response=response,
                success=True
            )

        except (json.JSONDecodeError, KeyError) as e:
            # JSON 파싱 실패 시 텍스트 분석으로 폴백
            return self._parse_text_response(response)

    def _parse_text_response(self, response: str) -> ReviewResult:
        """텍스트 응답에서 심각도 추론"""
        response_lower = response.lower()

        if any(word in response_lower for word in ["critical", "심각", "보안취약"]):
            severity = Severity.CRITICAL
        elif any(word in response_lower for word in ["high", "높음", "버그", "오류"]):
            severity = Severity.HIGH
        elif any(word in response_lower for word in ["medium", "중간", "개선"]):
            severity = Severity.MEDIUM
        elif any(word in response_lower for word in ["low", "낮음", "사소"]):
            severity = Severity.LOW
        else:
            severity = Severity.OK

        return ReviewResult(
            adapter_name=self.name,
            severity=severity,
            issues=[Issue(description=response, severity=severity)],
            raw_response=response,
            success=True
        )
