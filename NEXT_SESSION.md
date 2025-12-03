# 다음 세션 작업 내역

## 완료된 작업
1. **Copilot CLI 비활성화** - 쿼터 제한으로 제외
2. **하이브리드 토론 시스템 구현**
   - `debate_orchestrator.py`: LLM 간 토론 로직
   - HIGH+ 심각도 또는 2단계 이상 불일치 시 토론 트리거
3. **completion_orchestrator.py 통합** - 토론 로직 통합 완료
4. **Gemini API 어댑터** - REST API 직접 호출 (gemini-2.5-flash-lite)

## 다음 작업: GPT 어댑터 추가
OpenAI GPT를 외부 LLM 리뷰어로 추가

### 필요한 작업
1. `adapters/gpt.py` 생성 (gemini.py 패턴 참고)
2. `adapters/__init__.py`에 GPTAdapter 추가
3. `config.json`에 gpt 설정 추가
4. `completion_orchestrator.py`에서 GPT 어댑터 초기화

### GPT API 정보
- API 엔드포인트: `https://api.openai.com/v1/chat/completions`
- 추천 모델: `gpt-4o-mini` (저렴, 빠름) 또는 `gpt-4o`
- API 키 환경변수: `OPENAI_API_KEY`

## 현재 활성 LLM
| LLM | 상태 | 용도 |
|-----|------|------|
| Gemini | ✅ API 연동 | 외부 리뷰 |
| Claude Self | ✅ 서브에이전트 | 셀프 리뷰 |
| Copilot | ❌ 비활성화 | - |
| GPT | 🔜 예정 | 외부 리뷰 |

## 주요 파일
- `config.json`: 전체 설정
- `adapters/`: LLM 어댑터들
- `completion_orchestrator.py`: 완료 시점 검토
- `debate_orchestrator.py`: LLM 토론 로직
- `quota_monitor.py`: 쿼터 모니터링
