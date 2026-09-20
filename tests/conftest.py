import os

os.environ.setdefault(
    "SDL_VIDEODRIVER", "dummy"
)  # headless: no window, no audio device needed
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import random
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame
import pytest
from helpers import ScriptedRng, vectors
from pygame.math import Vector2

import snake as game_module

ROOT = Path(__file__).resolve().parent.parent

# the real asset loaders, captured before any test patches them
REAL_LOADERS = SimpleNamespace(
    image=game_module.load_image,
    font=game_module.load_font,
    sound=game_module.load_sound,
)


@pytest.fixture(scope="session", autouse=True)
def pygame_session():
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    size = game_module.CELL_NUMBER * game_module.CELL_SIZE
    game_module.screen = pygame.display.set_mode((size, size))
    game_module.game_font = pygame.font.Font(None, 25)
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def fake_assets(monkeypatch):
    """Swap file loading for blank sprites and mock sounds (no asset files needed)."""
    sounds = {}

    def fake_load_image(path):
        return pygame.Surface(
            (game_module.CELL_SIZE, game_module.CELL_SIZE), pygame.SRCALPHA
        )

    def fake_load_sound(path):
        return sounds.setdefault(path, MagicMock(name=path))

    monkeypatch.setattr(game_module, "load_image", fake_load_image)
    monkeypatch.setattr(game_module, "load_sound", fake_load_sound)
    return SimpleNamespace(sounds=sounds)


class FakeClock:
    def __init__(self):
        self.now = 10_000

    def __call__(self):
        return self.now

    def advance(self, milliseconds):
        self.now += milliseconds


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    """Deterministic pygame.time.get_ticks() that only moves when a test advances it."""
    fake_clock = FakeClock()
    monkeypatch.setattr(pygame.time, "get_ticks", fake_clock)
    return fake_clock


@pytest.fixture
def real_loaders():
    return REAL_LOADERS


@pytest.fixture
def mock_screen(monkeypatch):
    """A mock in place of the display surface, for tests that only check blit calls."""
    screen = MagicMock(name="screen")
    monkeypatch.setattr(game_module, "screen", screen)
    return screen


@pytest.fixture
def scripted_rng():
    return ScriptedRng()


@pytest.fixture
def spawner(scripted_rng):
    return game_module.ItemSpawner(
        game_module.CELL_NUMBER,
        rng=scripted_rng,
        blocked_cells={(game_module.CELL_NUMBER - 1, 0)},
    )


@pytest.fixture
def snake_obj():
    return game_module.Snake()


@pytest.fixture
def game(scripted_rng):
    """A Game in the PLAYING state with a scripted spawner RNG (no bomb by default)."""
    random.seed(1234)  # the very first apple is placed with the real RNG
    main = game_module.Game()
    main.item_spawner.rng = scripted_rng
    return main


@pytest.fixture
def set_snake():
    def _set_snake(target, cells, direction=(0, 0)):
        snake = target.snake if hasattr(target, "snake") else target
        snake.body = vectors(cells)
        snake.direction = Vector2(direction)
        return snake

    return _set_snake


@pytest.fixture
def place_items():
    """Put the apple (and optionally a bomb) on exact tiles."""

    def _place_items(main, apple, bomb=None):
        spawner = main.item_spawner
        spawner.apple.pos = Vector2(apple)
        spawner.bomb = None
        if bomb is not None:
            spawner.bomb = game_module.Bomb(
                spawner.bomb_sprite, spawner.explosion_sound
            )
            spawner.bomb.pos = Vector2(bomb)

    return _place_items
