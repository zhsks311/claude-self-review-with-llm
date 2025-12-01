"""
상태 관리 모듈 - 세션별 재시도 횟수, debounce, override 상태 관리
filelock을 사용하여 race condition 방지
"""
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from filelock import FileLock
except ImportError:
    # filelock 없으면 간단한 fallback
    class FileLock:
        def __init__(self, path): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass


class StateManager:
    def __init__(self, state_dir: str = "~/.claude/hooks/state"):
        self.state_dir = Path(state_dir).expanduser()
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_state_path(self, session_id: str, state_type: str) -> Path:
        return self.state_dir / f"{session_id}_{state_type}.json"

    def _get_lock_path(self, session_id: str, state_type: str) -> Path:
        return self.state_dir / f"{session_id}_{state_type}.lock"

    def _read_state(self, session_id: str, state_type: str) -> Dict[str, Any]:
        path = self._get_state_path(session_id, state_type)
        lock_path = self._get_lock_path(session_id, state_type)

        with FileLock(str(lock_path)):
            if path.exists():
                try:
                    return json.loads(path.read_text())
                except json.JSONDecodeError:
                    return {}
            return {}

    def _write_state(self, session_id: str, state_type: str, data: Dict[str, Any]):
        path = self._get_state_path(session_id, state_type)
        lock_path = self._get_lock_path(session_id, state_type)

        with FileLock(str(lock_path)):
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ===== Retry Count 관리 =====
    def get_retry_count(self, session_id: str, stage: str) -> int:
        state = self._read_state(session_id, "retry")
        return state.get(stage, 0)

    def increment_retry_count(self, session_id: str, stage: str) -> int:
        state = self._read_state(session_id, "retry")
        state[stage] = state.get(stage, 0) + 1
        self._write_state(session_id, "retry", state)
        return state[stage]

    def reset_retry_count(self, session_id: str, stage: str):
        state = self._read_state(session_id, "retry")
        state[stage] = 0
        self._write_state(session_id, "retry", state)

    # ===== Debounce 관리 =====
    def get_last_call_time(self, session_id: str, stage: str) -> Optional[float]:
        state = self._read_state(session_id, "debounce")
        return state.get(stage)

    def update_last_call_time(self, session_id: str, stage: str):
        state = self._read_state(session_id, "debounce")
        state[stage] = time.time()
        self._write_state(session_id, "debounce", state)

    def should_debounce(self, session_id: str, stage: str, debounce_seconds: float) -> bool:
        """debounce_seconds 내에 호출이 있었으면 True (스킵해야 함)"""
        last_call = self.get_last_call_time(session_id, stage)
        if last_call is None:
            return False
        return (time.time() - last_call) < debounce_seconds

    # ===== Override 관리 =====
    def set_override(self, session_id: str, skip_count: int = 1):
        """다음 N번의 검열을 스킵"""
        state = self._read_state(session_id, "override")
        state["skip_count"] = skip_count
        state["set_at"] = datetime.now().isoformat()
        self._write_state(session_id, "override", state)

    def check_and_consume_override(self, session_id: str) -> bool:
        """override가 설정되어 있으면 True 반환하고 카운트 감소"""
        state = self._read_state(session_id, "override")
        skip_count = state.get("skip_count", 0)

        if skip_count > 0:
            state["skip_count"] = skip_count - 1
            self._write_state(session_id, "override", state)
            return True
        return False

    # ===== Todo State 관리 =====
    def get_todo_state(self, session_id: str) -> Dict[str, Any]:
        """현재 todo 상태 조회"""
        return self._read_state(session_id, "todo")

    def save_todo_state(self, session_id: str, state: Dict[str, Any]):
        """todo 상태 저장"""
        state["updated_at"] = datetime.now().isoformat()
        self._write_state(session_id, "todo", state)

    # ===== Completion Review 횟수 관리 =====
    def get_completion_review_count(self, session_id: str) -> int:
        """완료 검토 횟수 조회 (무한 루프 방지용)"""
        state = self._read_state(session_id, "todo")
        return state.get("review_count", 0)

    def increment_completion_review_count(self, session_id: str) -> int:
        """완료 검토 횟수 증가"""
        state = self._read_state(session_id, "todo")
        state["review_count"] = state.get("review_count", 0) + 1
        state["last_review_at"] = datetime.now().isoformat()
        self._write_state(session_id, "todo", state)
        return state["review_count"]

    def reset_completion_review_count(self, session_id: str):
        """완료 검토 횟수 초기화 (새 작업 시작 시)"""
        state = self._read_state(session_id, "todo")
        state["review_count"] = 0
        self._write_state(session_id, "todo", state)

    # ===== 세션 정리 =====
    def cleanup_session(self, session_id: str):
        """세션 종료 시 상태 파일 정리"""
        for state_type in ["retry", "debounce", "override", "todo"]:
            path = self._get_state_path(session_id, state_type)
            lock_path = self._get_lock_path(session_id, state_type)
            if path.exists():
                path.unlink()
            if lock_path.exists():
                lock_path.unlink()


# 싱글톤 인스턴스
_state_manager: Optional[StateManager] = None

def get_state_manager() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
