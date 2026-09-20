import pygame
import pytest
from helpers import board_cells, vectors
from pygame.math import Vector2

import snake as game_module

APPLE_TILE = (6, 10)  # right in front of the initial snake, whose head is at (5,10)


# --- the Item abstraction -------------------------------------------------------------


def test_item_is_abstract():
    with pytest.raises(TypeError):
        game_module.Item(pygame.Surface((1, 1)))


def test_subclass_must_implement_on_eaten():
    class Incomplete(game_module.Item):
        pass

    with pytest.raises(TypeError):
        Incomplete(pygame.Surface((1, 1)))


def test_apple_and_bomb_are_items(spawner):
    assert isinstance(spawner.apple, game_module.Item)
    assert isinstance(
        game_module.Bomb(pygame.Surface((1, 1)), object()), game_module.Item
    )


def test_item_draws_its_sprite_on_its_tile(mock_screen):
    sprite = pygame.Surface((40, 40))
    item = game_module.Apple(sprite)
    item.pos = Vector2(3, 7)

    item.draw()

    mock_screen.blit.assert_called_once_with(sprite, pygame.Rect(120, 280, 40, 40))


# --- eating an apple ------------------------------------------------------------------


def eat(game, place_items, apple=None, bomb=None):
    """Run one tick with the snake heading right, its head landing on (6,10)."""
    place_items(game, apple=apple or (12, 12), bomb=bomb)
    game.snake.direction = Vector2(1, 0)
    game.update()


def test_eating_apple_grows_snake_and_plays_crunch(game, place_items):
    eat(game, place_items, apple=APPLE_TILE)

    assert game.snake.new_block is True
    game.snake.crunch_sound.play.assert_called_once_with()
    game.item_spawner.explosion_sound.play.assert_not_called()
    assert game.state == game_module.PLAYING


def test_snake_actually_gets_longer_on_the_next_move(game, place_items):
    eat(game, place_items, apple=APPLE_TILE)
    game.update()
    assert len(game.snake.body) == 4


def test_eating_apple_moves_apple_to_a_new_tile(game, place_items, scripted_rng):
    scripted_rng.choices = [(12, 12)]
    eat(game, place_items, apple=APPLE_TILE)
    assert game.item_spawner.apple.pos == Vector2(12, 12)


@pytest.mark.parametrize(
    "roll,bomb_expected",
    [(0.0, True), (0.49, True), (0.5, False), (0.99, False)],
    ids=["sure_bomb", "just_below_50", "exactly_50", "no_bomb"],
)
def test_bomb_appears_alongside_new_apple_only_on_winning_roll(
    game, place_items, scripted_rng, roll, bomb_expected
):
    scripted_rng.choices = [(12, 12), (3, 3)]
    scripted_rng.rolls = [roll]

    eat(game, place_items, apple=APPLE_TILE)

    bomb = game.item_spawner.bomb
    assert (bomb is not None) == bomb_expected
    if bomb_expected:
        assert bomb.pos == Vector2(3, 3)


def test_bomb_disappears_when_next_apple_is_eaten_and_roll_fails(
    game, place_items, scripted_rng
):
    scripted_rng.rolls = [0.9]
    eat(game, place_items, apple=APPLE_TILE, bomb=(15, 15))
    assert game.item_spawner.bomb is None


def test_bomb_moves_when_next_apple_is_eaten_and_roll_succeeds(
    game, place_items, scripted_rng
):
    scripted_rng.choices = [(12, 12), (1, 1)]
    scripted_rng.rolls = [0.1]
    eat(game, place_items, apple=APPLE_TILE, bomb=(15, 15))
    assert game.item_spawner.bomb.pos == Vector2(1, 1)


def test_items_stay_put_while_nothing_is_eaten(game, place_items, scripted_rng):
    place_items(game, apple=(12, 12), bomb=(15, 15))
    game.snake.direction = Vector2(1, 0)
    for _ in range(3):
        game.update()
    assert game.item_spawner.apple.pos == Vector2(12, 12)
    assert game.item_spawner.bomb.pos == Vector2(15, 15)
    assert scripted_rng.choice_calls == []  # the spawner was never asked for anything


def test_eating_the_last_free_tile_wins(game, place_items):
    # the snake covers every tile except the blocked top right one,
    # and its head sits on the apple
    cells = [(6, 10), *board_cells(exclude=[(19, 0), (6, 10)])]
    game.snake.body = vectors(cells)
    game.snake.direction = Vector2(1, 0)
    place_items(game, apple=(6, 10))

    game.check_collision()

    assert game.state == game_module.GAME_OVER
    assert game.game_over_title == game_module.WIN_TITLE


# --- eating a bomb --------------------------------------------------------------------


def test_eating_bomb_plays_explosion_and_starts_explosion_state(game, place_items):
    eat(game, place_items, bomb=APPLE_TILE)

    game.item_spawner.explosion_sound.play.assert_called_once_with()
    assert game.state == game_module.EXPLODING
    game.snake.crunch_sound.play.assert_not_called()


def test_eating_bomb_does_not_grow_the_snake(game, place_items):
    eat(game, place_items, bomb=APPLE_TILE)
    assert game.snake.new_block is False
    assert len(game.snake.body) == 3


def test_eating_bomb_does_not_respawn_items(game, place_items, scripted_rng):
    eat(game, place_items, apple=(12, 12), bomb=APPLE_TILE)
    assert game.item_spawner.apple.pos == Vector2(12, 12)
    assert scripted_rng.choice_calls == []


def test_snake_is_frozen_after_hitting_a_bomb(game, place_items):
    eat(game, place_items, bomb=APPLE_TILE)
    frozen = [block.copy() for block in game.snake.body]
    game.update()
    assert game.snake.body == frozen


# --- polymorphism: one loop, item decides what happens --------------------------------


@pytest.mark.parametrize(
    "scenario,apple,bomb,expected_state,grows",
    [
        ("apple_ahead", APPLE_TILE, (15, 15), game_module.PLAYING, True),
        ("bomb_ahead", (12, 12), APPLE_TILE, game_module.EXPLODING, False),
        ("nothing_ahead", (12, 12), (15, 15), game_module.PLAYING, False),
        ("no_bomb_on_board", (12, 12), None, game_module.PLAYING, False),
    ],
)
def test_check_collision_dispatches_to_the_item_under_the_head(
    game, place_items, scenario, apple, bomb, expected_state, grows
):
    eat(game, place_items, apple=apple, bomb=bomb)
    assert game.state == expected_state
    assert game.snake.new_block is grows


def test_check_collision_calls_on_eaten_of_whatever_item_is_there(game):
    eaten = []

    class Probe(game_module.Item):
        def on_eaten(self, main):
            eaten.append(main)

    probe = Probe(pygame.Surface((1, 1)))
    probe.pos = Vector2(5, 10)  # the snake's head
    game.item_spawner.items = lambda: [probe]

    game.check_collision()

    assert eaten == [game]
