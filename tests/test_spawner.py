import random

import pytest
from helpers import BLOCKED_TILE, GRID, SNAKE_LAYOUTS, board_cells
from pygame.math import Vector2

import snake as game_module


def cell(item):
    return (int(item.pos.x), int(item.pos.y))


def make_spawner(**kwargs):
    return game_module.ItemSpawner(GRID, blocked_cells={BLOCKED_TILE}, **kwargs)


# --- construction ---------------------------------------------------------------------


@pytest.mark.parametrize("chance", [-0.1, 1.01, 5])
def test_bomb_chance_must_be_a_probability(chance):
    with pytest.raises(ValueError):
        game_module.ItemSpawner(GRID, bomb_chance=chance)


@pytest.mark.parametrize("chance", [0, 0.5, 1])
def test_valid_bomb_chances_are_accepted(chance):
    assert game_module.ItemSpawner(GRID, bomb_chance=chance).bomb_chance == chance


def test_starts_with_an_apple_and_no_bomb(spawner):
    assert spawner.bomb is None
    assert spawner.items() == [spawner.apple]


def test_items_lists_bomb_after_apple(spawner):
    spawner.bomb = game_module.Bomb(spawner.bomb_sprite, spawner.explosion_sound)
    assert spawner.items() == [spawner.apple, spawner.bomb]


def test_draw_items_draws_every_item(spawner, mock_screen):
    spawner.bomb = game_module.Bomb(spawner.bomb_sprite, spawner.explosion_sound)
    spawner.draw_items()
    assert mock_screen.blit.call_count == 2


def test_cell_rounds_a_vector_to_a_grid_tuple():
    assert game_module.ItemSpawner.cell(Vector2(3, 4)) == (3, 4)


# --- where items may spawn ------------------------------------------------------------


@pytest.mark.parametrize("layout", SNAKE_LAYOUTS.keys())
def test_free_cells_exclude_body_blocked_tile_and_cell_ahead(
    spawner, snake_obj, set_snake, layout
):
    cells, direction = SNAKE_LAYOUTS[layout]
    set_snake(snake_obj, cells, direction)
    ahead = spawner.cell(snake_obj.cell_ahead())

    free = spawner.free_cells(snake_obj)

    assert not set(cells) & set(free)
    assert BLOCKED_TILE not in free
    assert ahead not in free
    on_board_forbidden = (
        set(cells)
        | {BLOCKED_TILE}
        | ({ahead} if 0 <= ahead[0] < GRID and 0 <= ahead[1] < GRID else set())
    )
    assert len(free) == GRID * GRID - len(on_board_forbidden)


@pytest.mark.parametrize("layout", SNAKE_LAYOUTS.keys())
def test_random_respawns_never_touch_snake_blocked_tile_or_each_other(
    snake_obj, set_snake, layout
):
    cells, direction = SNAKE_LAYOUTS[layout]
    set_snake(snake_obj, cells, direction)
    spawner = make_spawner(bomb_chance=1, rng=random.Random(7))
    ahead = spawner.cell(snake_obj.cell_ahead())

    for _ in range(300):
        assert spawner.respawn(snake_obj) is True
        assert cell(spawner.apple) not in [*cells, BLOCKED_TILE, ahead]
        assert cell(spawner.bomb) not in [*cells, BLOCKED_TILE, ahead]
        assert cell(spawner.bomb) != cell(spawner.apple)


def test_respawn_uses_the_scripted_tiles(spawner, snake_obj, scripted_rng):
    scripted_rng.choices = [(12, 12), (3, 3)]
    scripted_rng.rolls = [0.0]

    assert spawner.respawn(snake_obj) is True

    assert cell(spawner.apple) == (12, 12)
    assert cell(spawner.bomb) == (3, 3)


def test_bomb_is_chosen_from_tiles_that_exclude_the_apple(
    spawner, snake_obj, scripted_rng
):
    scripted_rng.choices = [(12, 12), (3, 3)]
    scripted_rng.rolls = [0.0]

    spawner.respawn(snake_obj)

    apple_candidates, bomb_candidates = scripted_rng.choice_calls
    assert (12, 12) in apple_candidates
    assert (12, 12) not in bomb_candidates


# --- the bomb roll --------------------------------------------------------------------


@pytest.mark.parametrize(
    "chance,roll,bomb_expected",
    [
        (0.5, 0.0, True),
        (0.5, 0.499, True),
        (0.5, 0.5, False),
        (0.5, 0.99, False),
        (0, 0.0, False),
        (1, 0.999, True),
    ],
)
def test_bomb_roll(snake_obj, scripted_rng, chance, roll, bomb_expected):
    spawner = make_spawner(bomb_chance=chance, rng=scripted_rng)
    scripted_rng.rolls = [roll]

    spawner.respawn(snake_obj)

    assert (spawner.bomb is not None) == bomb_expected


def test_respawn_always_discards_the_previous_bomb(spawner, snake_obj, scripted_rng):
    spawner.bomb = game_module.Bomb(spawner.bomb_sprite, spawner.explosion_sound)
    spawner.bomb.pos = Vector2(15, 15)
    scripted_rng.rolls = [0.9]  # failed roll

    spawner.respawn(snake_obj)

    assert spawner.bomb is None


def test_bomb_can_move_to_a_different_tile(spawner, snake_obj, scripted_rng):
    spawner.bomb = game_module.Bomb(spawner.bomb_sprite, spawner.explosion_sound)
    spawner.bomb.pos = Vector2(15, 15)
    scripted_rng.choices = [(12, 12), (2, 2)]
    scripted_rng.rolls = [0.1]

    spawner.respawn(snake_obj)

    assert cell(spawner.bomb) == (2, 2)


def test_initial_spawn_without_bomb_does_not_roll(spawner, snake_obj, scripted_rng):
    scripted_rng.rolls = [0.0]  # would spawn a bomb if it were consulted

    spawner.respawn(snake_obj, allow_bomb=False)

    assert spawner.bomb is None
    assert scripted_rng.rolls == [0.0]


def test_new_bomb_reuses_the_loaded_sprite_and_sound(spawner, snake_obj, scripted_rng):
    scripted_rng.rolls = [0.0]
    spawner.respawn(snake_obj)
    assert spawner.bomb.sprite is spawner.bomb_sprite
    assert spawner.bomb.explosion_sound is spawner.explosion_sound


# --- crowded boards -------------------------------------------------------------------


def test_single_free_tile_gets_the_apple_and_no_bomb(
    spawner, snake_obj, set_snake, scripted_rng
):
    free_tile = (10, 10)
    cells = [(9, 10), *board_cells(exclude=[free_tile, BLOCKED_TILE, (9, 10)])]
    set_snake(
        snake_obj, cells, direction=(1, 0)
    )  # ...and the free tile is straight ahead of the head
    scripted_rng.rolls = [0.0]

    assert spawner.respawn(snake_obj) is True

    assert (
        cell(spawner.apple) == free_tile
    )  # the "ahead" rule gives way when nothing else is left
    assert spawner.bomb is None


def test_two_free_tiles_give_apple_and_bomb(
    spawner, snake_obj, set_snake, scripted_rng
):
    cells = [(9, 10), *board_cells(exclude=[(1, 1), (2, 2), BLOCKED_TILE, (9, 10)])]
    set_snake(snake_obj, cells, direction=(-1, 0))
    scripted_rng.choices = [(1, 1), (2, 2)]
    scripted_rng.rolls = [0.0]

    spawner.respawn(snake_obj)

    assert {cell(spawner.apple), cell(spawner.bomb)} == {(1, 1), (2, 2)}


def test_no_free_tile_returns_false(spawner, snake_obj, set_snake):
    set_snake(snake_obj, board_cells(exclude=[BLOCKED_TILE]), direction=(1, 0))

    assert spawner.respawn(snake_obj) is False
    assert spawner.bomb is None


def test_blocked_tiles_are_configurable(snake_obj, scripted_rng):
    spawner = game_module.ItemSpawner(
        GRID, rng=scripted_rng, blocked_cells={(0, 0), (1, 0)}
    )
    free = spawner.free_cells(snake_obj)
    assert (0, 0) not in free and (1, 0) not in free
    assert BLOCKED_TILE in free  # not blocked in this spawner
