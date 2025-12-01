"""
Todo 상태 감지 모듈 - TodoWrite의 완료 상태를 감지
모든 todo가 completed 상태가 되는 시점을 판단
"""
from dataclasses import dataclass
from typing import List, Dict, Any

from state_manager import get_state_manager, StateManager


@dataclass
class TodoState:
    """Todo 상태 정보"""
    all_completed: bool  # 모든 todo가 completed인지
    just_completed: bool  # 이번 호출에서 방금 완료됨 (이전에는 미완료였음)
    total: int  # 전체 todo 수
    completed: int  # 완료된 todo 수


class TodoStateDetector:
    """Todo 완료 상태 감지기"""

    def __init__(self, state_manager: StateManager = None):
        self.state_manager = state_manager or get_state_manager()

    def detect_completion(self, session_id: str, todos: List[Dict[str, Any]]) -> TodoState:
        """
        Todo 완료 상태 감지

        Args:
            session_id: 세션 ID
            todos: TodoWrite의 todos 배열

        Returns:
            TodoState: 완료 상태 정보
        """
        if not todos:
            return TodoState(
                all_completed=False,
                just_completed=False,
                total=0,
                completed=0
            )

        total = len(todos)
        completed = sum(1 for t in todos if t.get("status") == "completed")
        all_completed = completed == total

        # 이전 상태와 비교하여 "방금 완료됨" 감지
        prev_state = self.state_manager.get_todo_state(session_id)
        prev_all_completed = prev_state.get("all_completed", False)

        # 이전에 미완료 → 현재 완료 = 방금 완료됨
        just_completed = all_completed and not prev_all_completed

        # 현재 상태 저장
        self.state_manager.save_todo_state(session_id, {
            "all_completed": all_completed,
            "total": total,
            "completed": completed,
            "todos_snapshot": [
                {"content": t.get("content", ""), "status": t.get("status", "")}
                for t in todos
            ]
        })

        return TodoState(
            all_completed=all_completed,
            just_completed=just_completed,
            total=total,
            completed=completed
        )

    def should_trigger_review(self, session_id: str, todos: List[Dict[str, Any]]) -> bool:
        """
        완료 검토를 트리거해야 하는지 판단

        Returns:
            True if 모든 todo가 방금 완료됨
        """
        state = self.detect_completion(session_id, todos)
        return state.just_completed


# 편의를 위한 함수
def get_todo_state_detector() -> TodoStateDetector:
    return TodoStateDetector()
