#!/usr/bin/env python3
"""curses 기반 터미널 지렁이(스네이크) 게임"""

import curses
import random
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional


class Direction(Enum):
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def opposite(self) -> "Direction":
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        return opposites[self]


# 게임 상수
GAME_WIDTH = 40
GAME_HEIGHT = 20
INITIAL_SPEED = 0.15  # 초 단위 (낮을수록 빠름)
SPEED_INCREMENT = 0.005  # 먹이 먹을 때마다 빨라짐
MIN_SPEED = 0.05


@dataclass
class Food:
    x: int
    y: int
    char: str = "*"
    points: int = 10


class Snake:
    """뱀 클래스"""

    def __init__(self, start_x: int, start_y: int):
        # deque: 머리는 앞, 꼬리는 뒤
        self.body: deque[Tuple[int, int]] = deque()
        self.body.append((start_x, start_y))
        self.body.append((start_x - 1, start_y))
        self.body.append((start_x - 2, start_y))
        self.direction = Direction.RIGHT
        self.grow_pending = False

    @property
    def head(self) -> Tuple[int, int]:
        return self.body[0]

    def move(self) -> None:
        """뱀 이동"""
        hx, hy = self.head
        dx, dy = self.direction.value
        new_head = (hx + dx, hy + dy)
        self.body.appendleft(new_head)

        if self.grow_pending:
            self.grow_pending = False
        else:
            self.body.pop()

    def grow(self) -> None:
        """다음 이동 시 성장"""
        self.grow_pending = True

    def change_direction(self, new_direction: Direction) -> None:
        """방향 전환 (반대 방향 무시)"""
        if new_direction != self.direction.opposite:
            self.direction = new_direction

    def collides_with_self(self) -> bool:
        """자기 몸과 충돌 체크"""
        return self.head in list(self.body)[1:]


class Game:
    """게임 상태 및 로직"""

    def __init__(self):
        self.snake = Snake(GAME_WIDTH // 2, GAME_HEIGHT // 2)
        self.food: Optional[Food] = None
        self.score = 0
        self.game_over = False
        self.speed = INITIAL_SPEED
        self.spawn_food()

    def spawn_food(self) -> None:
        """먹이 생성 (뱀 몸과 겹치지 않게)"""
        while True:
            x = random.randint(1, GAME_WIDTH - 2)
            y = random.randint(1, GAME_HEIGHT - 2)
            if (x, y) not in self.snake.body:
                self.food = Food(x, y)
                break

    def update(self) -> None:
        """게임 상태 업데이트"""
        if self.game_over:
            return

        self.snake.move()

        # 벽 충돌 체크
        hx, hy = self.snake.head
        if hx <= 0 or hx >= GAME_WIDTH - 1 or hy <= 0 or hy >= GAME_HEIGHT - 1:
            self.game_over = True
            return

        # 자기 몸 충돌 체크
        if self.snake.collides_with_self():
            self.game_over = True
            return

        # 먹이 먹기 체크
        if self.food and self.snake.head == (self.food.x, self.food.y):
            self.score += self.food.points
            self.snake.grow()
            self.speed = max(MIN_SPEED, self.speed - SPEED_INCREMENT)
            self.spawn_food()

    def reset(self) -> None:
        """게임 리셋"""
        self.snake = Snake(GAME_WIDTH // 2, GAME_HEIGHT // 2)
        self.food = None
        self.score = 0
        self.game_over = False
        self.speed = INITIAL_SPEED
        self.spawn_food()


class Renderer:
    """curses 기반 렌더러"""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.setup_colors()
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(50)

    def setup_colors(self) -> None:
        """컬러 설정"""
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_GREEN, -1)    # 뱀 몸
        curses.init_pair(2, curses.COLOR_YELLOW, -1)   # 뱀 머리
        curses.init_pair(3, curses.COLOR_RED, -1)      # 먹이
        curses.init_pair(4, curses.COLOR_WHITE, -1)    # 테두리
        curses.init_pair(5, curses.COLOR_CYAN, -1)     # 정보

    def draw(self, game: Game) -> None:
        """전체 화면 그리기"""
        self.stdscr.clear()

        # 게임 영역 그리기
        self.draw_border()
        self.draw_snake(game.snake)
        self.draw_food(game.food)
        self.draw_info(game)

        if game.game_over:
            self.draw_game_over(game)

        self.stdscr.refresh()

    def draw_border(self) -> None:
        """테두리 그리기"""
        # 상단/하단
        for x in range(GAME_WIDTH):
            self.stdscr.addstr(0, x * 2, "##", curses.color_pair(4))
            self.stdscr.addstr(GAME_HEIGHT - 1, x * 2, "##", curses.color_pair(4))

        # 좌측/우측
        for y in range(GAME_HEIGHT):
            self.stdscr.addstr(y, 0, "##", curses.color_pair(4))
            self.stdscr.addstr(y, (GAME_WIDTH - 1) * 2, "##", curses.color_pair(4))

    def draw_snake(self, snake: Snake) -> None:
        """뱀 그리기"""
        for i, (x, y) in enumerate(snake.body):
            if 0 < x < GAME_WIDTH - 1 and 0 < y < GAME_HEIGHT - 1:
                if i == 0:
                    # 머리
                    char = self._get_head_char(snake.direction)
                    self.stdscr.addstr(y, x * 2, char, curses.color_pair(2) | curses.A_BOLD)
                else:
                    # 몸통
                    self.stdscr.addstr(y, x * 2, "[]", curses.color_pair(1))

    def _get_head_char(self, direction: Direction) -> str:
        """방향에 따른 머리 문자"""
        heads = {
            Direction.UP: "/\\",
            Direction.DOWN: "\\/",
            Direction.LEFT: "<=",
            Direction.RIGHT: "=>",
        }
        return heads[direction]

    def draw_food(self, food: Optional[Food]) -> None:
        """먹이 그리기"""
        if food:
            self.stdscr.addstr(
                food.y, food.x * 2,
                "@@",
                curses.color_pair(3) | curses.A_BOLD
            )

    def draw_info(self, game: Game) -> None:
        """정보 패널 그리기"""
        info_x = GAME_WIDTH * 2 + 3

        self.stdscr.addstr(1, info_x, "SNAKE GAME", curses.color_pair(5) | curses.A_BOLD)
        self.stdscr.addstr(3, info_x, f"SCORE: {game.score}", curses.A_BOLD)
        self.stdscr.addstr(4, info_x, f"LENGTH: {len(game.snake.body)}")
        self.stdscr.addstr(5, info_x, f"SPEED: {int((INITIAL_SPEED - game.speed) / SPEED_INCREMENT) + 1}")

        self.stdscr.addstr(8, info_x, "CONTROLS:", curses.A_UNDERLINE)
        self.stdscr.addstr(9, info_x, "Arrow keys: Move")
        self.stdscr.addstr(10, info_x, "Q: Quit")
        self.stdscr.addstr(11, info_x, "R: Restart")

    def draw_game_over(self, game: Game) -> None:
        """게임 오버 화면"""
        center_y = GAME_HEIGHT // 2
        center_x = GAME_WIDTH

        self.stdscr.addstr(center_y - 1, center_x - 5, " GAME OVER ", curses.A_REVERSE | curses.A_BOLD)
        self.stdscr.addstr(center_y, center_x - 7, f" Score: {game.score} ", curses.A_REVERSE)
        self.stdscr.addstr(center_y + 1, center_x - 9, " Press R to restart ", curses.A_REVERSE)


def main(stdscr) -> None:
    """메인 게임 루프"""
    renderer = Renderer(stdscr)
    game = Game()
    last_update_time = time.time()

    while True:
        current_time = time.time()

        # 게임 업데이트
        if current_time - last_update_time >= game.speed:
            game.update()
            last_update_time = current_time

        # 입력 처리
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key == ord('q') or key == ord('Q'):
            break
        elif key == ord('r') or key == ord('R'):
            game.reset()
            last_update_time = time.time()
        elif not game.game_over:
            if key == curses.KEY_UP:
                game.snake.change_direction(Direction.UP)
            elif key == curses.KEY_DOWN:
                game.snake.change_direction(Direction.DOWN)
            elif key == curses.KEY_LEFT:
                game.snake.change_direction(Direction.LEFT)
            elif key == curses.KEY_RIGHT:
                game.snake.change_direction(Direction.RIGHT)

        # 렌더링
        renderer.draw(game)


if __name__ == "__main__":
    curses.wrapper(main)
