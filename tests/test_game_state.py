from unittest.mock import MagicMock

import pygame
import pytest
from pygame.math import Vector2

import snake as game_module
from snake import EXPLODING, GAME_OVER, PAUSED, PLAYING, RESUMING

ALL_STATES = [PLAYING, PAUSED, RESUMING, EXPLODING, GAME_OVER]
COUNTDOWN_MS = game_module.COUNTDOWN_STEPS * game_module.COUNTDOWN_STEP_MS


# --- pause state transitions ----------------------------------------------------------

# (state before, state after one toggle)
PAUSE_TRANSITIONS = [
    (PLAYING, PAUSED),
    (PAUSED, RESUMING),
    (RESUMING, PAUSED),  # toggling during the countdown pauses again
    (EXPLODING, EXPLODING),  # can't pause through the explosion
    (GAME_OVER, GAME_OVER),
]


@pytest.mark.parametrize("before,after", PAUSE_TRANSITIONS)
def test_toggle_pause_transitions(game, before, after):
    game.state = before
    game.toggle_pause()
    assert game.state == after


@pytest.mark.parametrize("before,after", PAUSE_TRANSITIONS[:4])
def test_p_key_toggles_pause_like_the_button(game, before, after):
    game.state = before
    game.handle_key(pygame.K_p)
    assert game.state == after


def test_p_on_game_over_screen_counts_as_any_key_and_restarts(game):
    game.state = GAME_OVER
    game.handle_key(pygame.K_p)
    assert game.state == PLAYING


def test_pause_resume_cycle_returns_to_playing(game, clock):
    game.toggle_pause()
    game.toggle_pause()
    assert game.state == RESUMING
    clock.advance(COUNTDOWN_MS)
    game.update_state()
    assert game.state == PLAYING


def test_resuming_records_the_countdown_start(game, clock):
    game.state = PAUSED
    clock.advance(1234)
    game.toggle_pause()
    assert game.state_start == clock.now


@pytest.mark.parametrize(
    "elapsed,expected",
    [
        (0, RESUMING),
        (1, RESUMING),
        (COUNTDOWN_MS - 1, RESUMING),
        (COUNTDOWN_MS, PLAYING),
        (COUNTDOWN_MS + 500, PLAYING),
    ],
)
def test_countdown_lasts_three_steps(game, clock, elapsed, expected):
    game.state = PAUSED
    game.toggle_pause()
    clock.advance(elapsed)
    game.update_state()
    assert game.state == expected


@pytest.mark.parametrize(
    "elapsed,shown",
    [
        (0, "3"),
        (999, "3"),
        (1000, "2"),
        (1999, "2"),
        (2000, "1"),
        (2999, "1"),
        (5000, "1"),
    ],
)
def test_countdown_displays_3_2_1(game, clock, elapsed, shown):
    game.state = PAUSED
    game.toggle_pause()
    clock.advance(elapsed)
    game.countdown_text = MagicMock()
    game.countdown_text.render.return_value = pygame.Surface((10, 10))

    game.draw_countdown()

    assert game.countdown_text.render.call_args.args[0] == shown


@pytest.mark.parametrize("state", [PAUSED, RESUMING])
def test_snake_does_not_move_while_paused_or_counting_down(game, state):
    game.snake.direction = Vector2(1, 0)
    before = [block.copy() for block in game.snake.body]
    game.state = state
    game.update()
    assert game.snake.body == before


@pytest.mark.parametrize("state", [PAUSED, RESUMING, EXPLODING, GAME_OVER])
def test_ignored_states_do_not_move_snake_or_eat_items(game, place_items, state):
    place_items(game, apple=(6, 10), bomb=None)
    game.snake.direction = Vector2(1, 0)
    game.state = state
    if state == GAME_OVER:
        game.final_score = 0
    game.update()
    assert game.snake.body[0] == Vector2(5, 10)
    game.snake.crunch_sound.play.assert_not_called()


def test_game_time_does_not_advance_the_state_while_paused(game, clock):
    game.state = PAUSED
    clock.advance(60_000)
    game.update_state()
    assert game.state == PAUSED


# --- keyboard steering ----------------------------------------------------------------

STEERING = [
    # heading before (None = fresh round, facing right), key, direction after
    (None, pygame.K_UP, (0, -1)),
    (None, pygame.K_RIGHT, (1, 0)),
    (None, pygame.K_DOWN, (0, 1)),
    (None, pygame.K_LEFT, (0, 0)),  # refused: the neck is right there
    ((1, 0), pygame.K_UP, (0, -1)),
    ((-1, 0), pygame.K_DOWN, (0, 1)),
    ((0, 1), pygame.K_UP, (0, 1)),  # can't reverse
    ((0, -1), pygame.K_DOWN, (0, -1)),
    ((1, 0), pygame.K_LEFT, (1, 0)),
    ((-1, 0), pygame.K_RIGHT, (-1, 0)),
    ((1, 0), pygame.K_a, (1, 0)),  # unrelated key
]


def face(game, set_snake, heading):
    """Put the snake mid-board, already travelling in the given direction."""
    hx, hy = heading
    set_snake(game, [(10 - hx * i, 10 - hy * i) for i in range(3)], heading)


@pytest.mark.parametrize("heading,key,after", STEERING)
def test_arrow_keys_steer_but_never_reverse(game, set_snake, heading, key, after):
    if heading is not None:
        face(game, set_snake, heading)

    game.handle_key(key)

    assert game.snake.direction == Vector2(after)


def test_two_quick_key_presses_cannot_reverse_the_snake(game, set_snake):
    # regression: UP then LEFT inside one 150 ms tick sent the head into its neck
    face(game, set_snake, (1, 0))

    game.handle_key(pygame.K_UP)
    game.handle_key(pygame.K_LEFT)
    game.update()

    assert game.state == PLAYING
    assert game.snake.body[0] == Vector2(10, 9)


def test_left_as_the_very_first_key_does_not_kill_the_snake(game):
    # regression: the fresh snake faces right, so LEFT used to be an instant game over
    game.handle_key(pygame.K_LEFT)
    game.update()

    assert game.state == PLAYING
    assert game.snake.body[0] == Vector2(5, 10)


@pytest.mark.parametrize("state", [PAUSED, RESUMING, EXPLODING])
def test_arrow_keys_are_ignored_outside_playing(game, state):
    game.snake.direction = Vector2(1, 0)
    game.state = state
    game.handle_key(pygame.K_UP)
    assert game.snake.direction == Vector2(1, 0)


def test_snake_waits_for_the_first_key_press(game):
    game.update()
    assert game.state == PLAYING
    assert game.snake.body[0] == Vector2(5, 10)


# --- dying ----------------------------------------------------------------------------

DEATH_SCENARIOS = {
    # name: (snake cells before the move, direction, expected state after one update)
    "safe_move": ([(5, 10), (4, 10), (3, 10)], (1, 0), PLAYING),
    "wall_left": ([(0, 5), (1, 5), (2, 5)], (-1, 0), GAME_OVER),
    "wall_right": ([(19, 5), (18, 5), (17, 5)], (1, 0), GAME_OVER),
    "wall_top": ([(5, 0), (5, 1), (5, 2)], (0, -1), GAME_OVER),
    "wall_bottom": ([(5, 19), (5, 18), (5, 17)], (0, 1), GAME_OVER),
    "last_tile_before_wall": ([(18, 5), (17, 5), (16, 5)], (1, 0), PLAYING),
    "blocked_tile_from_below": ([(19, 1), (19, 2), (19, 3)], (0, -1), GAME_OVER),
    "blocked_tile_from_left": ([(18, 0), (17, 0), (16, 0)], (1, 0), GAME_OVER),
    "next_to_blocked_tile": ([(18, 1), (17, 1), (16, 1)], (1, 0), PLAYING),
    "self_collision": ([(5, 5), (5, 6), (4, 6), (4, 5), (4, 4)], (-1, 0), GAME_OVER),
}


@pytest.mark.parametrize("scenario", DEATH_SCENARIOS.keys())
def test_death_scenarios(game, set_snake, place_items, scenario):
    cells, direction, expected = DEATH_SCENARIOS[scenario]
    set_snake(game, cells, direction)
    place_items(game, apple=(12, 12))

    game.update()

    assert game.state == expected


def test_game_over_records_the_score_before_reset(game, set_snake):
    set_snake(
        game, [(0, 5), (1, 5), (2, 5), (3, 5), (4, 5)], (-1, 0)
    )  # 5 blocks = score 2
    game.update()
    assert game.state == GAME_OVER
    assert game.final_score == 2
    assert game.game_over_title == game_module.GAME_OVER_TITLE


def test_game_over_freezes_everything(game, set_snake):
    set_snake(game, [(0, 5), (1, 5), (2, 5)], (-1, 0))
    game.update()
    frozen = [block.copy() for block in game.snake.body]
    game.update()
    assert game.snake.body == frozen


# --- explosion -> game over -> restart ------------------------------------------------


@pytest.mark.parametrize(
    "elapsed,expected",
    [
        (0, EXPLODING),
        (game_module.EXPLOSION_FLASH_MS - 1, EXPLODING),
        (game_module.EXPLOSION_FLASH_MS, GAME_OVER),
        (game_module.EXPLOSION_FLASH_MS + 300, GAME_OVER),
    ],
)
def test_explosion_flash_leads_to_game_over(game, clock, elapsed, expected):
    game.start_explosion()
    clock.advance(elapsed)
    game.update_state()
    assert game.state == expected


def test_keys_are_ignored_during_the_explosion_flash(game):
    game.start_explosion()
    game.handle_key(pygame.K_SPACE)
    assert game.state == EXPLODING


@pytest.mark.parametrize(
    "key", [pygame.K_SPACE, pygame.K_UP, pygame.K_a, pygame.K_RETURN]
)
def test_any_key_restarts_from_game_over(game, set_snake, place_items, key):
    set_snake(game, [(0, 5), (1, 5), (2, 5), (3, 5)], (-1, 0))
    place_items(game, apple=(12, 12), bomb=(15, 15))
    game.game_over()

    game.handle_key(key)

    assert game.state == PLAYING
    assert game.snake.body == [Vector2(5, 10), Vector2(4, 10), Vector2(3, 10)]
    assert game.snake.direction == Vector2(0, 0)
    assert game.item_spawner.bomb is None  # a new round starts without a bomb


def test_new_round_places_the_apple_on_a_free_tile(game):
    game.start_new_round()
    apple = game.item_spawner.apple.pos
    assert apple not in game.snake.body
    assert (int(apple.x), int(apple.y)) not in game.blocked_cells


def test_new_game_starts_playing_without_a_bomb(game):
    assert game.state == PLAYING
    assert game.item_spawner.bomb is None
    assert game.blocked_cells == {(game_module.CELL_NUMBER - 1, 0)}


# --- click routing --------------------------------------------------------------------


def test_clicking_the_button_pauses_the_game(game):
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(780, 20), button=1)
    game.handle_click(click)
    assert game.state == PAUSED


def test_clicking_elsewhere_does_nothing(game):
    game.handle_click(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(400, 400), button=1)
    )
    assert game.state == PLAYING


# --- drawing smoke tests (every state renders without errors) -------------------------


@pytest.mark.parametrize("state", ALL_STATES)
@pytest.mark.parametrize("blink_phase", [0, 500], ids=["hint_visible", "hint_hidden"])
def test_draw_elements_in_every_state(game, clock, place_items, state, blink_phase):
    place_items(game, apple=(12, 12), bomb=(15, 15))
    game.state = state
    game.state_start = clock.now
    game.final_score = 3
    clock.now = (clock.now // 1000) * 1000 + blink_phase

    game.draw_elements()


def test_win_screen_uses_the_win_title(game):
    game.game_over(game_module.WIN_TITLE)
    game.title_text = MagicMock()
    game.title_text.render.return_value = pygame.Surface((10, 10))
    game.draw_game_over()
    assert game.title_text.render.call_args.args[0] == game_module.WIN_TITLE


# --- GameState enum -------------------------------------------------------------------


def test_game_state_has_the_five_phases_with_unique_values():
    assert [state.name for state in game_module.GameState] == [
        "PLAYING",
        "PAUSED",
        "RESUMING",
        "EXPLODING",
        "GAME_OVER",
    ]
    assert len({state.value for state in game_module.GameState}) == 5


@pytest.mark.parametrize(
    "alias,member",
    [
        (PLAYING, game_module.GameState.PLAYING),
        (PAUSED, game_module.GameState.PAUSED),
        (RESUMING, game_module.GameState.RESUMING),
        (EXPLODING, game_module.GameState.EXPLODING),
        (GAME_OVER, game_module.GameState.GAME_OVER),
    ],
)
def test_module_level_state_names_are_the_enum_members(alias, member):
    assert alias is member


def test_state_is_not_comparable_to_a_plain_string(game):
    assert game.state != "playing"  # typos like 'plaiyng' can no longer pass silently


# --- pre-rendered grass ---------------------------------------------------------------


def original_checkerboard(row, col):
    """The rule the old per-frame draw_grass loops used."""
    return col % 2 == 0 if row % 2 == 0 else col % 2 != 0


def test_prerendered_grass_matches_the_original_checkerboard(game):
    size = game_module.CELL_SIZE
    for row in range(game_module.CELL_NUMBER):
        for col in range(game_module.CELL_NUMBER):
            color = tuple(
                game.grass.get_at((col * size + size // 2, row * size + size // 2))
            )[:3]
            expected = (
                game_module.GRASS_COLOR
                if original_checkerboard(row, col)
                else game_module.BACKGROUND_COLOR
            )
            assert color == expected, (row, col)


def test_grass_covers_the_whole_window(game):
    assert game.grass.get_size() == game_module.screen.get_size()


def test_draw_grass_is_a_single_blit_of_the_prerendered_surface(game, mock_screen):
    game.draw_grass()
    mock_screen.blit.assert_called_once_with(game.grass, (0, 0))


def test_grass_is_rendered_once_not_every_frame(game, monkeypatch):
    calls = []
    monkeypatch.setattr(game_module, "render_grass", lambda: calls.append(1))
    for _ in range(5):
        game.draw_elements()
    assert calls == []
