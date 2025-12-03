#!/usr/bin/env python3
"""
훅 시스템 개선 테스트
- 쿼터 모니터링
- 조건부 블록 로직
"""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from quota_monitor import QuotaMonitor, QuotaStatus, get_quota_monitor
from adapters.base import Severity, ReviewResult, Issue


def test_quota_monitor_success_tracking():
    """성공 기록 테스트"""
    print("\n=== 쿼터 모니터: 성공 기록 테스트 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = QuotaMonitor(state_dir=tmpdir)

        # 초기 상태
        assert monitor.is_available("gemini") == True
        print("✓ 초기 상태: gemini 사용 가능")

        # 성공 기록
        monitor.record_success("gemini")
        assert monitor.quotas["gemini"].success_count == 1
        assert monitor.quotas["gemini"].status == QuotaStatus.AVAILABLE
        print("✓ 성공 기록 후: success_count=1, status=AVAILABLE")

    print("✅ 성공 기록 테스트 통과")


def test_quota_monitor_failure_tracking():
    """실패 기록 및 쿨다운 테스트"""
    print("\n=== 쿼터 모니터: 실패 기록 테스트 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = QuotaMonitor(state_dir=tmpdir)

        # 쿼터 에러로 실패
        monitor.record_failure("copilot", "quota exceeded error")
        assert monitor.quotas["copilot"].status == QuotaStatus.EXHAUSTED
        assert monitor.is_available("copilot") == False
        print("✓ 쿼터 에러 후: status=EXHAUSTED, 사용 불가")

        # 쿨다운 확인
        assert monitor.quotas["copilot"].cooldown_until is not None
        print(f"✓ 쿨다운 설정됨: {monitor.quotas['copilot'].cooldown_until}")

    print("✅ 실패 기록 테스트 통과")


def test_quota_monitor_consecutive_failures():
    """연속 실패 시 쿼터 소진 테스트"""
    print("\n=== 쿼터 모니터: 연속 실패 테스트 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = QuotaMonitor(state_dir=tmpdir)

        # 일반 에러로 3회 연속 실패
        monitor.record_failure("gemini", "timeout error")
        assert monitor.quotas["gemini"].status == QuotaStatus.UNKNOWN
        print("✓ 1회 실패: status=UNKNOWN")

        monitor.record_failure("gemini", "connection error")
        assert monitor.quotas["gemini"].status == QuotaStatus.LOW
        print("✓ 2회 연속 실패: status=LOW")

        monitor.record_failure("gemini", "server error")
        assert monitor.quotas["gemini"].status == QuotaStatus.EXHAUSTED
        assert monitor.is_available("gemini") == False
        print("✓ 3회 연속 실패: status=EXHAUSTED, 사용 불가")

    print("✅ 연속 실패 테스트 통과")


def test_quota_monitor_available_adapters():
    """사용 가능한 어댑터 필터링 테스트"""
    print("\n=== 쿼터 모니터: 어댑터 필터링 테스트 ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = QuotaMonitor(state_dir=tmpdir)

        # gemini만 쿼터 소진
        monitor.record_failure("gemini", "quota limit reached")

        available = monitor.get_available_adapters(["gemini", "copilot"])
        assert "gemini" not in available
        assert "copilot" in available
        print(f"✓ 사용 가능 어댑터: {available}")

    print("✅ 어댑터 필터링 테스트 통과")


def test_conditional_blocking_critical():
    """조건부 블록: CRITICAL만 블록 테스트"""
    print("\n=== 조건부 블록: CRITICAL 테스트 ===")

    # _build_output 로직을 직접 테스트
    from completion_orchestrator import CompletionOrchestrator

    # Mock 설정
    with patch('completion_orchestrator.load_config') as mock_config, \
         patch('completion_orchestrator.get_state_manager'), \
         patch('completion_orchestrator.get_security_validator'), \
         patch('completion_orchestrator.get_quota_monitor'):

        mock_config.return_value = {
            "completion_review": {"use_subagent": True}
        }

        orchestrator = CompletionOrchestrator()

        # CRITICAL 결과
        critical_result = ReviewResult(
            adapter_name="gemini",
            severity=Severity.CRITICAL,
            issues=[Issue("보안 취약점 발견", Severity.CRITICAL)],
            raw_response="",
            success=True
        )

        output = orchestrator._build_output([critical_result], {})
        assert output["continue"] == False
        assert "CRITICAL" in output["systemMessage"]
        print("✓ CRITICAL: continue=False (블록됨)")

    print("✅ CRITICAL 블록 테스트 통과")


def test_conditional_blocking_high():
    """조건부 블록: HIGH는 경고만 테스트"""
    print("\n=== 조건부 블록: HIGH 테스트 ===")

    from completion_orchestrator import CompletionOrchestrator

    with patch('completion_orchestrator.load_config') as mock_config, \
         patch('completion_orchestrator.get_state_manager'), \
         patch('completion_orchestrator.get_security_validator'), \
         patch('completion_orchestrator.get_quota_monitor'):

        mock_config.return_value = {
            "completion_review": {"use_subagent": True}
        }

        orchestrator = CompletionOrchestrator()

        # HIGH 결과
        high_result = ReviewResult(
            adapter_name="copilot",
            severity=Severity.HIGH,
            issues=[Issue("버그 가능성", Severity.HIGH)],
            raw_response="",
            success=True
        )

        output = orchestrator._build_output([high_result], {})
        assert output["continue"] == True
        print("✓ HIGH: continue=True (경고만)")

    print("✅ HIGH 경고 테스트 통과")


def test_conditional_blocking_ok():
    """조건부 블록: OK는 통과 테스트"""
    print("\n=== 조건부 블록: OK 테스트 ===")

    from completion_orchestrator import CompletionOrchestrator

    with patch('completion_orchestrator.load_config') as mock_config, \
         patch('completion_orchestrator.get_state_manager'), \
         patch('completion_orchestrator.get_security_validator'), \
         patch('completion_orchestrator.get_quota_monitor'):

        mock_config.return_value = {
            "completion_review": {"use_subagent": True}
        }

        orchestrator = CompletionOrchestrator()

        # OK 결과
        ok_result = ReviewResult(
            adapter_name="gemini",
            severity=Severity.OK,
            issues=[],
            raw_response="",
            success=True
        )

        output = orchestrator._build_output([ok_result], {})
        assert output["continue"] == True
        print("✓ OK: continue=True (통과)")

    print("✅ OK 통과 테스트 통과")


def test_gemini_adapter_config():
    """Gemini API 어댑터 설정 테스트"""
    print("\n=== Gemini API 어댑터 설정 테스트 ===")

    from adapters.gemini import GeminiAdapter

    # 기본 모델 확인
    assert GeminiAdapter.DEFAULT_MODEL == "gemini-2.5-flash-lite"
    print("✓ 기본 모델: gemini-2.5-flash-lite")

    # API 모드 확인
    config = {"gemini": {"use_api": True}}
    adapter = GeminiAdapter(config)
    assert adapter.use_api == True
    assert adapter.model == "gemini-2.5-flash-lite"
    print("✓ API 모드 활성화, 모델 설정 확인")

    # API 키 없을 때 CLI 폴백 확인
    config_no_key = {"gemini": {"use_api": True}}
    adapter_no_key = GeminiAdapter(config_no_key)
    # API 키 없고 CLI도 없으면 사용 불가
    if not adapter_no_key.api_key and not adapter_no_key.cli_path:
        assert adapter_no_key.is_available() == False
        print("✓ API 키/CLI 없으면 사용 불가 확인")
    else:
        print("✓ API 키 또는 CLI 사용 가능")

    print("✅ Gemini API 어댑터 설정 테스트 통과")


def run_all_tests():
    """모든 테스트 실행"""
    print("=" * 50)
    print("훅 시스템 개선 테스트 시작")
    print("=" * 50)

    tests = [
        ("쿼터 모니터: 성공 기록", test_quota_monitor_success_tracking),
        ("쿼터 모니터: 실패 기록", test_quota_monitor_failure_tracking),
        ("쿼터 모니터: 연속 실패", test_quota_monitor_consecutive_failures),
        ("쿼터 모니터: 어댑터 필터링", test_quota_monitor_available_adapters),
        ("조건부 블록: CRITICAL", test_conditional_blocking_critical),
        ("조건부 블록: HIGH", test_conditional_blocking_high),
        ("조건부 블록: OK", test_conditional_blocking_ok),
        ("Gemini API 어댑터 설정", test_gemini_adapter_config),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {name} 실패: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {name} 에러: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"테스트 결과: {passed} 통과, {failed} 실패")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
