# 터미널 테트리스 구현 계획

## 개요
- **기술**: Python + curses
- **컬러**: 256색 지원 (fallback 포함)
- **기능**: 표준형 (기본 + 다음 블록 미리보기 + 레벨/속도 증가)

## 아키텍처

```
┌─────────────────────────────────────────────┐
│  ┌─────────────┐  ┌─────────┐              │
│  │   게임 보드   │  │  정보창  │              │
│  │   10 x 20   │  │ NEXT:   │              │
│  │             │  │ SCORE:  │              │
│  │             │  │ LEVEL:  │              │
│  │             │  │ LINES:  │              │
│  └─────────────┘  └─────────┘              │
└─────────────────────────────────────────────┘
```

## 모듈 구조

### 1. 상수 및 데이터 (constants)
- COLS = 10, ROWS = 20
- 7가지 테트로미노 모양 및 회전 상태
- 컬러 매핑

### 2. Piece 클래스
- 속성: x, y, shape_idx, rotation
- 메서드: rotate(), get_blocks()

### 3. Board 클래스
- 속성: grid (20x10), locked_positions
- 메서드: is_valid(), lock_piece(), clear_lines()

### 4. Game 클래스
- 속성: board, current_piece, next_piece, score, level, lines
- 메서드: update(), handle_input(), is_game_over()
- 레벨 시스템: 10줄마다 레벨 증가, 속도 증가

### 5. Renderer 클래스
- curses 초기화 및 컬러 설정
- draw_board(), draw_piece(), draw_info_panel()
- 블록 문자: ▓▓ (2칸 폭으로 정사각형 표현)

## 조작법
- ← → : 좌우 이동
- ↓ : 소프트 드롭
- ↑ 또는 z : 회전
- Space : 하드 드롭
- q : 종료
- r : 재시작 (게임 오버 시)

## 구현 순서
1. [x] 구현 계획 문서 작성
2. [x] 핵심 코드 구현 (Piece, Board)
3. [x] 컬러 및 렌더링 구현
4. [x] 게임 루프 및 입력 처리
5. [x] 테스트 및 실행 확인 (문법 검사 완료)

## 파일 구조
```
test/
├── tetris.py          # 기존 pygame 버전
└── tetris_terminal.py # 새 터미널 버전
```
