#!/usr/bin/env python3
"""curses 기반 터미널 테트리스 게임"""

import curses
import random
import time
from dataclasses import dataclass
from typing import List, Tuple, Set, Optional

# 게임 상수
COLS = 10
ROWS = 20
BLOCK_CHAR = "[]"  # 2칸 폭으로 정사각형 표현

# 테트로미노 정의 (SRS 회전 시스템 기반)
SHAPES = {
    'I': [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)],
    ],
    'O': [
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)],
    ],
    'T': [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)],
    ],
    'S': [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
    ],
    'Z': [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 0), (0, 1), (1, 1), (0, 2)],
    ],
    'J': [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    'L': [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
}

SHAPE_NAMES = list(SHAPES.keys())

# 컬러 인덱스 (curses color pair)
COLORS = {
    'I': 1,  # 시안
    'O': 2,  # 노랑
    'T': 3,  # 마젠타
    'S': 4,  # 초록
    'Z': 5,  # 빨강
    'J': 6,  # 파랑
    'L': 7,  # 주황 (빨강+노랑 대체)
}


@dataclass
class Piece:
    """현재 조작 중인 테트로미노"""
    x: int
    y: int
    shape_name: str
    rotation: int = 0

    @property
    def blocks(self) -> List[Tuple[int, int]]:
        """현재 회전 상태의 블록 좌표 반환"""
        return SHAPES[self.shape_name][self.rotation]

    @property
    def color(self) -> int:
        return COLORS[self.shape_name]

    def get_absolute_blocks(self) -> List[Tuple[int, int]]:
        """절대 좌표 반환"""
        return [(self.x + dx, self.y + dy) for dx, dy in self.blocks]

    def rotate(self) -> None:
        self.rotation = (self.rotation + 1) % 4


class Board:
    """게임 보드 상태 관리"""

    def __init__(self):
        self.locked: Set[Tuple[int, int]] = set()
        self.colors: dict[Tuple[int, int], int] = {}

    def is_valid_position(self, piece: Piece) -> bool:
        """피스 위치가 유효한지 검사"""
        for x, y in piece.get_absolute_blocks():
            if x < 0 or x >= COLS or y >= ROWS:
                return False
            if y >= 0 and (x, y) in self.locked:
                return False
        return True

    def lock_piece(self, piece: Piece) -> None:
        """피스를 보드에 고정"""
        for x, y in piece.get_absolute_blocks():
            self.locked.add((x, y))
            self.colors[(x, y)] = piece.color

    def clear_lines(self) -> int:
        """완성된 줄 제거, 제거된 줄 수 반환"""
        lines_cleared = 0
        y = ROWS - 1

        while y >= 0:
            # 해당 줄이 꽉 찼는지 확인
            if all((x, y) in self.locked for x in range(COLS)):
                lines_cleared += 1
                # 해당 줄 제거
                for x in range(COLS):
                    self.locked.discard((x, y))
                    self.colors.pop((x, y), None)
                # 위의 줄들을 아래로 이동
                new_locked = set()
                new_colors = {}
                for (bx, by), color in list(self.colors.items()):
                    if by < y:
                        new_locked.add((bx, by + 1))
                        new_colors[(bx, by + 1)] = color
                    else:
                        new_locked.add((bx, by))
                        new_colors[(bx, by)] = color
                self.locked = new_locked
                self.colors = new_colors
            else:
                y -= 1

        return lines_cleared

    def is_game_over(self) -> bool:
        """게임 오버 여부 확인"""
        return any(y < 0 for (x, y) in self.locked)


class Game:
    """게임 상태 및 로직"""

    def __init__(self):
        self.board = Board()
        self.current_piece: Optional[Piece] = None
        self.next_piece: Optional[Piece] = None
        self.score = 0
        self.level = 1
        self.lines = 0
        self.game_over = False
        self.spawn_piece()

    def spawn_piece(self) -> None:
        """새 피스 생성"""
        if self.next_piece is None:
            self.next_piece = self._create_random_piece()
        self.current_piece = self.next_piece
        self.next_piece = self._create_random_piece()

        if not self.board.is_valid_position(self.current_piece):
            self.game_over = True

    def _create_random_piece(self) -> Piece:
        shape = random.choice(SHAPE_NAMES)
        return Piece(x=COLS // 2 - 2, y=-2, shape_name=shape)

    def move(self, dx: int, dy: int) -> bool:
        """피스 이동, 성공 여부 반환"""
        if self.current_piece is None or self.game_over:
            return False

        self.current_piece.x += dx
        self.current_piece.y += dy

        if not self.board.is_valid_position(self.current_piece):
            self.current_piece.x -= dx
            self.current_piece.y -= dy
            return False
        return True

    def rotate(self) -> bool:
        """피스 회전, 성공 여부 반환"""
        if self.current_piece is None or self.game_over:
            return False

        old_rotation = self.current_piece.rotation
        self.current_piece.rotate()

        if not self.board.is_valid_position(self.current_piece):
            # 벽 킥 시도
            for kick_x in [-1, 1, -2, 2]:
                self.current_piece.x += kick_x
                if self.board.is_valid_position(self.current_piece):
                    return True
                self.current_piece.x -= kick_x
            # 회전 취소
            self.current_piece.rotation = old_rotation
            return False
        return True

    def hard_drop(self) -> None:
        """하드 드롭"""
        if self.current_piece is None or self.game_over:
            return
        while self.move(0, 1):
            pass
        self.lock_current_piece()

    def soft_drop(self) -> bool:
        """소프트 드롭 (한 칸 아래)"""
        return self.move(0, 1)

    def lock_current_piece(self) -> None:
        """현재 피스 고정 및 줄 제거"""
        if self.current_piece is None:
            return

        self.board.lock_piece(self.current_piece)
        cleared = self.board.clear_lines()

        if cleared > 0:
            self.lines += cleared
            # 점수 계산 (원본 테트리스 점수 시스템)
            points = {1: 100, 2: 300, 3: 500, 4: 800}
            self.score += points.get(cleared, 0) * self.level
            # 레벨 업 (10줄마다)
            self.level = self.lines // 10 + 1

        if self.board.is_game_over():
            self.game_over = True
        else:
            self.spawn_piece()

    def update(self) -> None:
        """자동 낙하 업데이트"""
        if self.game_over:
            return
        if not self.soft_drop():
            self.lock_current_piece()

    @property
    def fall_interval(self) -> float:
        """현재 레벨에 따른 낙하 간격 (초)"""
        # 레벨이 올라갈수록 빨라짐
        return max(0.1, 0.5 - (self.level - 1) * 0.05)

    def reset(self) -> None:
        """게임 리셋"""
        self.board = Board()
        self.current_piece = None
        self.next_piece = None
        self.score = 0
        self.level = 1
        self.lines = 0
        self.game_over = False
        self.spawn_piece()


class Renderer:
    """curses 기반 렌더러"""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.setup_colors()
        curses.curs_set(0)  # 커서 숨김
        stdscr.nodelay(True)  # non-blocking 입력
        stdscr.timeout(50)  # 50ms 타임아웃

    def setup_colors(self) -> None:
        """컬러 페어 설정"""
        curses.start_color()
        curses.use_default_colors()

        # 컬러 페어 정의
        curses.init_pair(1, curses.COLOR_CYAN, -1)     # I
        curses.init_pair(2, curses.COLOR_YELLOW, -1)   # O
        curses.init_pair(3, curses.COLOR_MAGENTA, -1)  # T
        curses.init_pair(4, curses.COLOR_GREEN, -1)    # S
        curses.init_pair(5, curses.COLOR_RED, -1)      # Z
        curses.init_pair(6, curses.COLOR_BLUE, -1)     # J
        curses.init_pair(7, curses.COLOR_WHITE, -1)    # L (흰색으로 대체)
        curses.init_pair(8, curses.COLOR_WHITE, -1)    # 테두리

    def draw(self, game: Game) -> None:
        """전체 화면 그리기"""
        self.stdscr.clear()

        # 게임 보드 그리기
        self.draw_board(game, start_x=1, start_y=1)

        # 정보 패널 그리기
        self.draw_info_panel(game, start_x=COLS * 2 + 4, start_y=1)

        # 게임 오버 표시
        if game.game_over:
            self.draw_game_over()

        self.stdscr.refresh()

    def draw_board(self, game: Game, start_x: int, start_y: int) -> None:
        """게임 보드 그리기"""
        # 테두리
        for y in range(ROWS + 2):
            self.stdscr.addstr(start_y + y, start_x - 1, "|", curses.color_pair(8))
            self.stdscr.addstr(start_y + y, start_x + COLS * 2, "|", curses.color_pair(8))

        self.stdscr.addstr(start_y + ROWS + 1, start_x - 1, "+" + "-" * (COLS * 2) + "+", curses.color_pair(8))
        self.stdscr.addstr(start_y - 1, start_x - 1, "+" + "-" * (COLS * 2) + "+", curses.color_pair(8))

        # 고정된 블록 그리기
        for (x, y), color in game.board.colors.items():
            if 0 <= y < ROWS:
                self.stdscr.addstr(
                    start_y + y, start_x + x * 2,
                    BLOCK_CHAR,
                    curses.color_pair(color) | curses.A_BOLD
                )

        # 현재 피스 그리기
        if game.current_piece and not game.game_over:
            for x, y in game.current_piece.get_absolute_blocks():
                if 0 <= y < ROWS and 0 <= x < COLS:
                    self.stdscr.addstr(
                        start_y + y, start_x + x * 2,
                        BLOCK_CHAR,
                        curses.color_pair(game.current_piece.color) | curses.A_BOLD
                    )

    def draw_info_panel(self, game: Game, start_x: int, start_y: int) -> None:
        """정보 패널 그리기"""
        self.stdscr.addstr(start_y, start_x, "NEXT:", curses.A_BOLD)

        # 다음 피스 미리보기
        if game.next_piece:
            for dx, dy in game.next_piece.blocks:
                self.stdscr.addstr(
                    start_y + 1 + dy, start_x + dx * 2,
                    BLOCK_CHAR,
                    curses.color_pair(game.next_piece.color) | curses.A_BOLD
                )

        # 점수 정보
        self.stdscr.addstr(start_y + 6, start_x, f"SCORE: {game.score}", curses.A_BOLD)
        self.stdscr.addstr(start_y + 8, start_x, f"LEVEL: {game.level}", curses.A_BOLD)
        self.stdscr.addstr(start_y + 10, start_x, f"LINES: {game.lines}", curses.A_BOLD)

        # 조작법
        self.stdscr.addstr(start_y + 13, start_x, "CONTROLS:", curses.A_UNDERLINE)
        self.stdscr.addstr(start_y + 14, start_x, "Arrow keys: Move")
        self.stdscr.addstr(start_y + 15, start_x, "Up/Z: Rotate")
        self.stdscr.addstr(start_y + 16, start_x, "Space: Hard drop")
        self.stdscr.addstr(start_y + 17, start_x, "Q: Quit")
        self.stdscr.addstr(start_y + 18, start_x, "R: Restart")

    def draw_game_over(self) -> None:
        """게임 오버 화면"""
        msg = " GAME OVER "
        restart_msg = " Press R to restart "
        y = ROWS // 2 + 1
        x = (COLS * 2 + 2 - len(msg)) // 2
        x2 = (COLS * 2 + 2 - len(restart_msg)) // 2

        self.stdscr.addstr(y, x, msg, curses.A_REVERSE | curses.A_BOLD)
        self.stdscr.addstr(y + 1, x2, restart_msg, curses.A_REVERSE)


def main(stdscr) -> None:
    """메인 게임 루프"""
    renderer = Renderer(stdscr)
    game = Game()
    last_fall_time = time.time()

    while True:
        # 자동 낙하
        current_time = time.time()
        if current_time - last_fall_time >= game.fall_interval:
            game.update()
            last_fall_time = current_time

        # 입력 처리
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key == ord('q') or key == ord('Q'):
            break
        elif key == ord('r') or key == ord('R'):
            game.reset()
            last_fall_time = time.time()
        elif not game.game_over:
            if key == curses.KEY_LEFT:
                game.move(-1, 0)
            elif key == curses.KEY_RIGHT:
                game.move(1, 0)
            elif key == curses.KEY_DOWN:
                game.soft_drop()
            elif key == curses.KEY_UP or key == ord('z') or key == ord('Z'):
                game.rotate()
            elif key == ord(' '):
                game.hard_drop()

        # 렌더링
        renderer.draw(game)


if __name__ == "__main__":
    curses.wrapper(main)
