import pygame
import pytest
from helpers import SNAKE_LAYOUTS, TURN_LAYOUTS
from pygame.math import Vector2

import snake as game_module

DIRECTIONS = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}


def test_initial_state(snake_obj):
    assert snake_obj.body == [Vector2(5, 10), Vector2(4, 10), Vector2(3, 10)]
    assert snake_obj.direction == Vector2(0, 0)
    assert snake_obj.new_block is False


@pytest.mark.parametrize("direction", DIRECTIONS.values(), ids=DIRECTIONS.keys())
def test_move_advances_head_and_keeps_length(snake_obj, direction):
    snake_obj.direction = Vector2(direction)
    before = [block.copy() for block in snake_obj.body]

    snake_obj.move_snake()

    assert snake_obj.body[0] == before[0] + Vector2(direction)
    assert snake_obj.body[1:] == before[:-1]  # the tail block was dropped
    assert len(snake_obj.body) == 3


def test_move_after_add_block_grows_by_one_and_keeps_tail(snake_obj):
    snake_obj.direction = Vector2(1, 0)
    before = [block.copy() for block in snake_obj.body]

    snake_obj.add_block()
    snake_obj.move_snake()

    assert len(snake_obj.body) == 4
    assert snake_obj.body[1:] == before
    assert snake_obj.new_block is False


def test_growth_happens_only_once(snake_obj):
    snake_obj.direction = Vector2(1, 0)
    snake_obj.add_block()
    snake_obj.move_snake()
    snake_obj.move_snake()
    assert len(snake_obj.body) == 4


def test_reset_restores_start_position_and_pending_growth(snake_obj):
    snake_obj.direction = Vector2(0, -1)
    snake_obj.add_block()
    snake_obj.move_snake()

    snake_obj.reset()

    assert snake_obj.body == [Vector2(5, 10), Vector2(4, 10), Vector2(3, 10)]
    assert snake_obj.direction == Vector2(0, 0)
    assert snake_obj.new_block is False


@pytest.mark.parametrize("layout", SNAKE_LAYOUTS.keys())
def test_cell_ahead_follows_direction_or_facing(snake_obj, set_snake, layout):
    cells, direction = SNAKE_LAYOUTS[layout]
    set_snake(snake_obj, cells, direction)
    head, neck = Vector2(cells[0]), Vector2(cells[1])

    expected = head + (
        Vector2(direction) if Vector2(direction) != Vector2(0, 0) else head - neck
    )

    assert snake_obj.cell_ahead() == expected


def test_crunch_sound_is_played(snake_obj):
    snake_obj.play_crunch_sound()
    snake_obj.crunch_sound.play.assert_called_once_with()


@pytest.mark.parametrize(
    "cells,head_sprite",
    [
        ([(5, 5), (6, 5), (7, 5)], "head_left"),  # body to the right -> looking left
        ([(5, 5), (4, 5), (3, 5)], "head_right"),
        ([(5, 5), (5, 6), (5, 7)], "head_up"),
        ([(5, 5), (5, 4), (5, 3)], "head_down"),
    ],
)
def test_head_sprite_follows_neck_position(snake_obj, set_snake, cells, head_sprite):
    set_snake(snake_obj, cells)
    assert snake_obj.sprite_for(0) is snake_obj.sprites[head_sprite]


@pytest.mark.parametrize(
    "cells,tail_sprite",
    [
        (
            [(7, 5), (6, 5), (5, 5)],
            "tail_left",
        ),  # the rest of the snake is to the right of the tail -> tail points left
        ([(5, 5), (6, 5), (7, 5)], "tail_right"),
        ([(5, 7), (5, 6), (5, 5)], "tail_up"),
        ([(5, 5), (5, 6), (5, 7)], "tail_down"),
    ],
)
def test_tail_sprite_follows_previous_block(snake_obj, set_snake, cells, tail_sprite):
    set_snake(snake_obj, cells)
    assert snake_obj.sprite_for(len(cells) - 1) is snake_obj.sprites[tail_sprite]


@pytest.mark.parametrize("layout", TURN_LAYOUTS.keys())
def test_body_sprite_matches_the_turn(snake_obj, set_snake, mock_screen, layout):
    cells, sprite_name = TURN_LAYOUTS[layout]
    set_snake(snake_obj, cells)

    assert snake_obj.sprite_for(1) is snake_obj.sprites[sprite_name]

    snake_obj.draw_snake()
    assert mock_screen.blit.call_count == len(cells)
    assert mock_screen.blit.call_args_list[1].args[0] is snake_obj.sprites[sprite_name]


def test_every_sprite_is_loaded_once(snake_obj):
    assert set(snake_obj.sprites) == set(game_module.SPRITE_NAMES)
    assert len(snake_obj.sprites) == 14


@pytest.mark.parametrize(
    "cells",
    [
        [
            (5, 5),
            (5, 5),
            (5, 6),
        ],  # head on top of its neck (the frame after a reversal)
        [(5, 5), (5, 6), (5, 5), (5, 7)],  # head on top of the block two places back
        [(5, 5), (5, 6), (5, 7), (5, 7)],  # tail on top of the block before it
    ],
    ids=["head_on_neck", "head_on_body", "tail_on_body"],
)
def test_overlapping_blocks_after_a_collision_still_draw(
    snake_obj, set_snake, mock_screen, cells
):
    set_snake(snake_obj, cells)
    snake_obj.draw_snake()  # the game-over frame must not crash
    assert mock_screen.blit.call_count == len(cells)


def test_step_returns_the_offset_between_two_blocks():
    assert game_module.step(Vector2(1, 2), Vector2(3, 5)) == (2, 3)


def test_draw_snake_places_blocks_on_the_grid(snake_obj, mock_screen):
    snake_obj.draw_snake()
    rects = [call.args[1] for call in mock_screen.blit.call_args_list]
    size = game_module.CELL_SIZE
    assert rects == [pygame.Rect(x * size, 10 * size, size, size) for x in (5, 4, 3)]


def test_snake_needs_its_sprites(monkeypatch):
    def missing(path):
        raise game_module.AssetError(path)

    monkeypatch.setattr(game_module, "load_image", missing)
    with pytest.raises(game_module.AssetError):
        game_module.Snake()


# --- steering: a turn is only refused when it would go straight into the neck ---------


@pytest.mark.parametrize(
    "heading,turn,accepted",
    [
        (None, (0, -1), True),
        (None, (1, 0), True),
        (None, (0, 1), True),
        (None, (-1, 0), False),  # None = fresh round, facing right
        ((1, 0), (0, -1), True),
        ((1, 0), (0, 1), True),
        ((1, 0), (1, 0), True),
        ((1, 0), (-1, 0), False),
        ((-1, 0), (0, -1), True),
        ((-1, 0), (-1, 0), True),
        ((-1, 0), (1, 0), False),
        ((0, 1), (1, 0), True),
        ((0, 1), (-1, 0), True),
        ((0, 1), (0, -1), False),
        ((0, -1), (1, 0), True),
        ((0, -1), (-1, 0), True),
        ((0, -1), (0, 1), False),
    ],
)
def test_set_direction_accepts_everything_but_a_reversal(
    snake_obj, set_snake, heading, turn, accepted
):
    if heading is None:
        start = snake_obj.direction.copy()  # fresh snake, direction (0, 0)
    else:
        hx, hy = heading
        set_snake(snake_obj, [(10 - hx * i, 10 - hy * i) for i in range(3)], heading)
        start = Vector2(heading)

    snake_obj.set_direction(Vector2(turn))

    assert snake_obj.direction == (Vector2(turn) if accepted else start)


def test_reversal_is_judged_against_the_neck_not_the_last_key(snake_obj, set_snake):
    set_snake(snake_obj, [(10, 10), (9, 10), (8, 10)], (1, 0))  # heading right
    snake_obj.set_direction(Vector2(0, -1))  # UP, accepted
    snake_obj.set_direction(
        Vector2(-1, 0)
    )  # LEFT before the next tick: would hit the neck
    assert snake_obj.direction == Vector2(0, -1)


# --- score and start position ---------------------------------------------------------


def test_score_counts_blocks_beyond_the_initial_length(snake_obj, set_snake):
    assert snake_obj.score == 0
    set_snake(snake_obj, [(x, 5) for x in range(game_module.INITIAL_LENGTH + 4)])
    assert snake_obj.score == 4


def test_initial_body_is_a_fresh_copy_of_the_start_position():
    first, second = game_module.initial_body(), game_module.initial_body()
    assert first == second == [Vector2(cell) for cell in game_module.START_BODY]
    first[0].x = 99
    assert second[0] != first[0]  # mutating one snake never affects the next
    assert game_module.INITIAL_LENGTH == len(game_module.START_BODY) == 3
