# LLM Adapters
from .base import LLMAdapter, ReviewResult, Severity, Issue
from .gemini import GeminiAdapter
from .copilot import CopilotAdapter
from .claude_self import ClaudeSelfAdapter

__all__ = [
    "LLMAdapter",
    "ReviewResult",
    "Severity",
    "Issue",
    "GeminiAdapter",
    "CopilotAdapter",
    "ClaudeSelfAdapter"
]
