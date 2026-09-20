import os
import random

import pygame
import pytest
from pygame.math import Vector2


# Initialize headless Pygame for testing
@pytest.fixture(scope="session", autouse=True)
def setup_headless_pygame():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.mixer.init()
    pygame.display.set_mode((800, 800))
    yield
    pygame.quit()


from snake_ai_lab.snake import (
    MAIN,
    SNAKE,
    Bomb,
    Fruit,
    ItemManager,
    PauseButton,
    load_image_safe,
    load_sound_safe,
)

# --- Fixtures ---


@pytest.fixture
def sample_surface():
    return pygame.Surface((40, 40))


@pytest.fixture
def dummy_sound():
    return load_sound_safe("invalid_path_to_sound.wav")


@pytest.fixture
def snake_obj():
    return SNAKE()


@pytest.fixture
def item_manager(sample_surface, dummy_sound):
    return ItemManager(sample_surface, sample_surface, dummy_sound, cell_number=20)


@pytest.fixture
def pause_button(sample_surface):
    return PauseButton(sample_surface, sample_surface, screen_width=800, margin=15)


@pytest.fixture
def main_game(sample_surface, dummy_sound):
    return MAIN(
        apple_surf=sample_surface,
        bomb_surf=sample_surface,
        pause_surf=sample_surface,
        play_surf=sample_surface,
        sound=dummy_sound,
    )


# --- Helper Functions Tests ---


def test_load_image_safe_valid(tmp_path):
    img_path = tmp_path / "test.png"
    surf = pygame.Surface((20, 20))
    pygame.image.save(surf, str(img_path))
    loaded = load_image_safe(str(img_path), size=(30, 30))
    assert isinstance(loaded, pygame.Surface)
    assert loaded.get_width() == 30
    assert loaded.get_height() == 30


def test_load_image_safe_invalid():
    fallback = load_image_safe("non_existent_file.png", size=(40, 40))
    assert isinstance(fallback, pygame.Surface)
    assert fallback.get_width() == 40
    assert fallback.get_height() == 40


def test_load_sound_safe_invalid():
    snd = load_sound_safe("non_existent_sound.wav")
    assert hasattr(snd, "play")
    snd.play()


# --- SNAKE Class Tests ---


def test_snake_initialization(snake_obj):
    assert len(snake_obj.body) == 3
    assert snake_obj.body[0] == Vector2(5, 10)
    assert snake_obj.direction == Vector2(0, 0)
    assert snake_obj.new_block is False


def test_snake_movement_stationary(snake_obj):
    initial_body = list(snake_obj.body)
    snake_obj.move_snake()
    assert snake_obj.body == initial_body


def test_snake_movement_active(snake_obj):
    snake_obj.direction = Vector2(1, 0)
    snake_obj.move_snake()
    assert snake_obj.body[0] == Vector2(6, 10)
    assert len(snake_obj.body) == 3


def test_snake_growth(snake_obj):
    snake_obj.direction = Vector2(1, 0)
    snake_obj.add_block()
    assert snake_obj.new_block is True
    snake_obj.move_snake()
    assert len(snake_obj.body) == 4
    assert snake_obj.new_block is False


def test_snake_reset(snake_obj):
    snake_obj.direction = Vector2(0, 1)
    snake_obj.add_block()
    snake_obj.move_snake()
    snake_obj.reset()
    assert len(snake_obj.body) == 3
    assert snake_obj.direction == Vector2(0, 0)


def test_snake_graphics_updates(snake_obj):
    snake_obj.direction = Vector2(1, 0)
    snake_obj.move_snake()
    snake_obj.draw_snake()


# --- Item, Fruit, Bomb Tests ---


def test_fruit_initialization_and_drawing(sample_surface):
    fruit = Fruit(sample_surface, Vector2(2, 3))
    assert fruit.pos == Vector2(2, 3)
    screen = pygame.display.get_surface()
    fruit.draw(screen, cell_size=40)


def test_bomb_initialization_drawing_and_sound(sample_surface, dummy_sound):
    bomb = Bomb(sample_surface, dummy_sound, Vector2(4, 5))
    assert bomb.pos == Vector2(4, 5)
    screen = pygame.display.get_surface()
    bomb.draw(screen, cell_size=40)
    bomb.play_explosion_sound()


def test_item_randomize_empty_tiles(sample_surface):
    fruit = Fruit(sample_surface)
    occupied = [
        Vector2(x, y) for x in range(20) for y in range(20) if not (x == 5 and y == 5)
    ]
    success = fruit.randomize(occupied, cell_number=20)
    assert success is True
    assert fruit.pos == Vector2(5, 5)


def test_item_randomize_grid_full(sample_surface):
    fruit = Fruit(sample_surface)
    all_occupied = [Vector2(x, y) for x in range(20) for y in range(20)]
    success = fruit.randomize(all_occupied, cell_number=20)
    assert success is False


# --- ItemManager Tests ---


def test_item_manager_initial_spawn(item_manager, snake_obj):
    item_manager.spawn_initial_items(snake_obj.body)
    assert item_manager.fruit.pos not in snake_obj.body
    assert item_manager.bomb is None


def test_item_manager_update_apple_eaten_bomb_spawn(
    item_manager, snake_obj, monkeypatch
):
    monkeypatch.setattr(random, "random", lambda: 0.1)
    item_manager.update_items_on_apple_eaten(snake_obj.body)

    assert item_manager.fruit.pos not in snake_obj.body
    assert item_manager.bomb is not None
    assert item_manager.bomb.pos not in snake_obj.body
    assert item_manager.bomb.pos != item_manager.fruit.pos


def test_item_manager_update_apple_eaten_no_bomb(item_manager, snake_obj, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.9)
    item_manager.update_items_on_apple_eaten(snake_body=snake_obj.body)

    assert item_manager.fruit.pos not in snake_obj.body
    assert item_manager.bomb is None


def test_item_manager_draw(item_manager, sample_surface):
    screen = pygame.display.get_surface()
    item_manager.fruit = Fruit(sample_surface, Vector2(1, 1))
    item_manager.bomb = Bomb(sample_surface, load_sound_safe("fake.wav"), Vector2(2, 2))
    item_manager.draw_items(screen, cell_size=40)


# --- PauseButton Tests ---


def test_pause_button_positioning(pause_button):
    assert pause_button.rect.x == 745
    assert pause_button.rect.y == 15


def test_pause_button_is_clicked(pause_button):
    assert pause_button.is_clicked((750, 20)) is True
    assert pause_button.is_clicked((10, 10)) is False


def test_pause_button_draw(pause_button):
    screen = pygame.display.get_surface()
    pause_button.draw(screen, is_paused=False)
    pause_button.draw(screen, is_paused=True)


# --- MAIN Class Game Logic & Pause Transitions Tests ---


def test_main_initial_state(main_game):
    assert main_game.is_paused is False
    assert main_game.snake.direction == Vector2(0, 0)


def test_main_toggle_pause(main_game):
    assert main_game.is_paused is False
    main_game.toggle_pause()
    assert main_game.is_paused is True
    main_game.toggle_pause()
    assert main_game.is_paused is False


def test_main_handle_click_pause_button(main_game):
    button_pos = (
        main_game.pause_button.rect.centerx,
        main_game.pause_button.rect.centery,
    )
    main_game.handle_click(button_pos)
    assert main_game.is_paused is True


def test_main_update_paused(main_game):
    main_game.toggle_pause()
    main_game.snake.direction = Vector2(1, 0)
    initial_body = list(main_game.snake.body)
    main_game.update()
    assert main_game.snake.body == initial_body


def test_main_apple_collision(main_game):
    main_game.snake.direction = Vector2(1, 0)
    main_game.item_manager.fruit.pos = Vector2(6, 10)

    main_game.update()
    assert main_game.snake.new_block is True

    main_game.snake.move_snake()
    assert len(main_game.snake.body) == 4


def test_main_bomb_collision(main_game):
    main_game.snake.direction = Vector2(1, 0)
    main_game.item_manager.bomb = Bomb(
        main_game.item_manager.bomb_image,
        main_game.item_manager.explosion_sound,
        Vector2(6, 10),
    )

    main_game.update()
    assert main_game.snake.direction == Vector2(0, 0)
    assert len(main_game.snake.body) == 3


def test_main_wall_collision(main_game):
    main_game.snake.body[0] = Vector2(-1, 0)
    main_game.update()
    assert main_game.snake.body[0] == Vector2(5, 10)


def test_main_draw_elements(main_game):
    main_game.draw_elements()
