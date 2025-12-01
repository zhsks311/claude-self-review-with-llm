#!/usr/bin/env python3
"""Pygame 기반 테트리스 게임"""

import pygame
import random

# 화면 설정
BLOCK_SIZE = 30
COLS = 10
ROWS = 20
SCREEN_WIDTH = BLOCK_SIZE * COLS
SCREEN_HEIGHT = BLOCK_SIZE * ROWS
FPS = 60

# 색상 정의
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
COLORS = [
    (0, 255, 255),    # I - 시안
    (255, 255, 0),    # O - 노랑
    (128, 0, 128),    # T - 보라
    (0, 255, 0),      # S - 초록
    (255, 0, 0),      # Z - 빨강
    (0, 0, 255),      # J - 파랑
    (255, 165, 0),    # L - 주황
]

# 테트로미노 모양 정의 (각 회전 상태)
SHAPES = [
    # I
    [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
        [(0, 2), (1, 2), (2, 2), (3, 2)],
        [(1, 0), (1, 1), (1, 2), (1, 3)],
    ],
    # O
    [
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (2, 1)],
    ],
    # T
    [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)],
    ],
    # S
    [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
        [(1, 1), (2, 1), (0, 2), (1, 2)],
        [(0, 0), (0, 1), (1, 1), (1, 2)],
    ],
    # Z
    [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (1, 2), (2, 2)],
        [(1, 0), (0, 1), (1, 1), (0, 2)],
    ],
    # J
    [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    # L
    [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
]


class Piece:
    """현재 조작 중인 테트로미노"""

    def __init__(self, x: int, y: int, shape_idx: int):
        self.x = x
        self.y = y
        self.shape_idx = shape_idx
        self.rotation = 0

    @property
    def shape(self) -> list:
        return SHAPES[self.shape_idx][self.rotation]

    @property
    def color(self) -> tuple:
        return COLORS[self.shape_idx]

    def rotate(self):
        self.rotation = (self.rotation + 1) % 4


def create_grid(locked_positions: dict) -> list:
    """게임 그리드 생성"""
    grid = [[BLACK for _ in range(COLS)] for _ in range(ROWS)]
    for (x, y), color in locked_positions.items():
        if 0 <= y < ROWS:
            grid[y][x] = color
    return grid


def get_piece_positions(piece: Piece) -> list:
    """피스의 절대 좌표 반환"""
    return [(piece.x + dx, piece.y + dy) for dx, dy in piece.shape]


def valid_space(piece: Piece, locked_positions: dict) -> bool:
    """이동/회전이 유효한지 검사"""
    for x, y in get_piece_positions(piece):
        if x < 0 or x >= COLS or y >= ROWS:
            return False
        if y >= 0 and (x, y) in locked_positions:
            return False
    return True


def check_lost(locked_positions: dict) -> bool:
    """게임 오버 여부 확인"""
    return any(y < 0 for (x, y) in locked_positions)


def clear_rows(grid: list, locked_positions: dict) -> int:
    """완성된 줄 제거 및 점수 반환"""
    cleared = 0
    rows_to_clear = []

    for y in range(ROWS - 1, -1, -1):
        if BLACK not in grid[y]:
            rows_to_clear.append(y)
            cleared += 1

    for row in rows_to_clear:
        # 해당 줄의 블록 제거
        for x in range(COLS):
            if (x, row) in locked_positions:
                del locked_positions[(x, row)]

        # 위의 블록들을 아래로 이동
        new_locked = {}
        for (x, y), color in locked_positions.items():
            if y < row:
                new_locked[(x, y + 1)] = color
            else:
                new_locked[(x, y)] = color
        locked_positions.clear()
        locked_positions.update(new_locked)

    return cleared


def draw_grid(surface: pygame.Surface, grid: list):
    """그리드 렌더링"""
    for y, row in enumerate(grid):
        for x, color in enumerate(row):
            pygame.draw.rect(
                surface,
                color,
                (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
            )
    # 그리드 선 그리기
    for y in range(ROWS + 1):
        pygame.draw.line(surface, GRAY, (0, y * BLOCK_SIZE), (SCREEN_WIDTH, y * BLOCK_SIZE))
    for x in range(COLS + 1):
        pygame.draw.line(surface, GRAY, (x * BLOCK_SIZE, 0), (x * BLOCK_SIZE, SCREEN_HEIGHT))


def draw_piece(surface: pygame.Surface, piece: Piece):
    """현재 피스 렌더링"""
    for x, y in get_piece_positions(piece):
        if y >= 0:
            pygame.draw.rect(
                surface,
                piece.color,
                (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
            )


def draw_text(surface: pygame.Surface, text: str, size: int, color: tuple, pos: tuple):
    """텍스트 렌더링"""
    font = pygame.font.SysFont("arial", size)
    label = font.render(text, True, color)
    rect = label.get_rect(center=pos)
    surface.blit(label, rect)


def get_new_piece() -> Piece:
    """새 피스 생성"""
    shape_idx = random.randint(0, len(SHAPES) - 1)
    return Piece(COLS // 2 - 2, -2, shape_idx)


def main():
    """메인 게임 루프"""
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()

    locked_positions = {}
    current_piece = get_new_piece()
    next_piece = get_new_piece()

    fall_time = 0
    fall_speed = 0.5  # 초 단위
    score = 0
    running = True
    game_over = False

    while running:
        grid = create_grid(locked_positions)
        fall_time += clock.get_rawtime()
        clock.tick(FPS)

        # 자동 낙하
        if fall_time / 1000 >= fall_speed:
            fall_time = 0
            current_piece.y += 1
            if not valid_space(current_piece, locked_positions):
                current_piece.y -= 1
                # 피스 고정
                for x, y in get_piece_positions(current_piece):
                    locked_positions[(x, y)] = current_piece.color
                # 줄 제거
                cleared = clear_rows(create_grid(locked_positions), locked_positions)
                score += cleared * 100
                # 새 피스
                current_piece = next_piece
                next_piece = get_new_piece()
                # 게임 오버 체크
                if check_lost(locked_positions):
                    game_over = True

        # 이벤트 처리
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                if game_over:
                    if event.key == pygame.K_RETURN:
                        # 재시작
                        locked_positions.clear()
                        current_piece = get_new_piece()
                        next_piece = get_new_piece()
                        score = 0
                        game_over = False
                    continue

                if event.key == pygame.K_LEFT:
                    current_piece.x -= 1
                    if not valid_space(current_piece, locked_positions):
                        current_piece.x += 1

                elif event.key == pygame.K_RIGHT:
                    current_piece.x += 1
                    if not valid_space(current_piece, locked_positions):
                        current_piece.x -= 1

                elif event.key == pygame.K_DOWN:
                    current_piece.y += 1
                    if not valid_space(current_piece, locked_positions):
                        current_piece.y -= 1

                elif event.key == pygame.K_UP:
                    current_piece.rotate()
                    if not valid_space(current_piece, locked_positions):
                        # 회전 취소 (3번 더 회전하면 원래대로)
                        current_piece.rotate()
                        current_piece.rotate()
                        current_piece.rotate()

                elif event.key == pygame.K_SPACE:
                    # 하드 드롭
                    while valid_space(current_piece, locked_positions):
                        current_piece.y += 1
                    current_piece.y -= 1

        # 렌더링
        screen.fill(BLACK)
        draw_grid(screen, grid)
        draw_piece(screen, current_piece)

        # 점수 표시
        draw_text(screen, f"Score: {score}", 20, WHITE, (SCREEN_WIDTH // 2, 15))

        # 게임 오버 표시
        if game_over:
            draw_text(screen, "GAME OVER", 40, WHITE, (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
            draw_text(screen, "Press ENTER to restart", 20, WHITE, (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
