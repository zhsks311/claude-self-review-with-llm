"""
의도 추출 모듈 - transcript에서 사용자의 원래 요청 추출
토큰 제한을 고려하여 요약 기능 포함
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


class IntentExtractor:
    """Transcript에서 사용자 의도 추출"""

    MAX_CHARS = 10000  # 토큰 제한 (약 2500 토큰)

    def extract_from_transcript(self, transcript_path: str) -> Dict[str, Any]:
        """
        Transcript 파일에서 사용자 의도 추출

        Args:
            transcript_path: transcript JSON 파일 경로

        Returns:
            Dict containing:
                - original_request: 첫 번째 사용자 메시지 (원래 요청)
                - combined_intent: 모든 사용자 메시지 (토큰 제한 적용)
                - message_count: 사용자 메시지 수
        """
        try:
            transcript = self._load_transcript(transcript_path)
            user_messages = self._extract_user_messages(transcript)

            if not user_messages:
                return self._empty_result()

            combined = self._combine_with_limit(user_messages)

            return {
                "original_request": user_messages[0],
                "combined_intent": combined,
                "message_count": len(user_messages),
                "truncated": len("\n---\n".join(user_messages)) > self.MAX_CHARS
            }
        except Exception as e:
            return {
                "original_request": "",
                "combined_intent": "",
                "message_count": 0,
                "error": str(e)
            }

    def _load_transcript(self, transcript_path: str) -> List[Dict[str, Any]]:
        """Transcript 파일 로드"""
        path = Path(transcript_path)
        if not path.exists():
            return []

        content = path.read_text(encoding="utf-8")
        data = json.loads(content)

        # transcript 구조에 따라 처리
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "messages" in data:
            return data["messages"]
        return []

    def _extract_user_messages(self, transcript: List[Dict[str, Any]]) -> List[str]:
        """사용자 메시지만 추출"""
        messages = []
        for msg in transcript:
            role = msg.get("role", "")
            if role == "user" or role == "human":
                content = msg.get("content", "")
                # content가 리스트인 경우 (멀티모달)
                if isinstance(content, list):
                    text_parts = [
                        p.get("text", "") for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    content = "\n".join(text_parts)
                if content and content.strip():
                    messages.append(content.strip())
        return messages

    def _combine_with_limit(self, messages: List[str]) -> str:
        """
        메시지 결합 (토큰 제한 적용)

        제한 초과 시: 첫 메시지(원래 요청) + 마지막 N개 메시지
        """
        separator = "\n\n---\n\n"
        combined = separator.join(messages)

        if len(combined) <= self.MAX_CHARS:
            return combined

        # 첫 메시지는 필수 포함
        first = messages[0]
        remaining_chars = self.MAX_CHARS - len(first) - 100  # 여유 공간

        # 마지막 메시지들부터 역순으로 추가
        last_messages = []
        for msg in reversed(messages[1:]):
            if len(separator.join(last_messages)) + len(msg) < remaining_chars:
                last_messages.insert(0, msg)
            else:
                break

        if last_messages:
            return f"{first}\n\n[...중간 {len(messages) - 1 - len(last_messages)}개 메시지 생략...]\n\n{separator.join(last_messages)}"
        else:
            # 첫 메시지만 반환 (너무 긴 경우)
            return first[:self.MAX_CHARS]

    def _empty_result(self) -> Dict[str, Any]:
        """빈 결과 반환"""
        return {
            "original_request": "",
            "combined_intent": "",
            "message_count": 0
        }


# 편의를 위한 함수
def get_intent_extractor() -> IntentExtractor:
    return IntentExtractor()
