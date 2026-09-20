"""Snake with bombs: eat apples to grow, avoid bombs, walls and your own tail."""

from __future__ import annotations

import random
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from enum import Enum
from typing import Protocol

import pygame
from pygame.math import Vector2

Color = tuple[int, int, int]
Cell = tuple[int, int]

CELL_SIZE = 40
CELL_NUMBER = 20
TICK_MS = 150

# head first; the snake waits for the first key press before moving
START_BODY: tuple[Cell, ...] = ((5, 10), (4, 10), (3, 10))
INITIAL_LENGTH = len(START_BODY)

# optional, falls back to a scaled-up built-in font
PIXEL_FONT_PATH = "Font/PressStart2P-Regular.ttf"
GAME_OVER_TITLE = "GAME OVER"
GAME_OVER_HINT = "PRESS ANY KEY TO RESTART"
WIN_TITLE = "YOU WIN!"
PAUSE_HINT = "PRESS P OR CLICK TO RESUME"

EXPLOSION_FLASH_MS = 600
COUNTDOWN_STEPS = 3
COUNTDOWN_STEP_MS = 1000

BACKGROUND_COLOR: Color = (175, 215, 70)
GRASS_COLOR: Color = (167, 209, 61)
GRASS_HOVER_COLOR: Color = (187, 229, 81)
DARK_GREEN: Color = (56, 74, 12)
BLACK: Color = (0, 0, 0)
WHITE: Color = (255, 255, 255)
HINT_COLOR: Color = (255, 220, 80)
GAME_OVER_TEXT_COLOR: Color = (255, 80, 80)
GAME_OVER_OVERLAY_COLOR: Color = (60, 0, 0)
FLASH_COLOR: Color = (220, 20, 20)

DIM_ALPHA = 140
GAME_OVER_ALPHA = 190
FLASH_ALPHA_START = 200
FLASH_ALPHA_END = 100

# offset from a block to its neighbour -> the sprite that fits (see Snake.sprite_for)
HEAD_SPRITES: dict[tuple[float, float], str] = {
    (1, 0): "head_left",
    (-1, 0): "head_right",
    (0, 1): "head_up",
    (0, -1): "head_down",
}
TAIL_SPRITES: dict[tuple[float, float], str] = {
    (1, 0): "tail_left",
    (-1, 0): "tail_right",
    (0, 1): "tail_up",
    (0, -1): "tail_down",
}
# the set of both neighbours' offsets -> straight piece or corner
BODY_SPRITES: dict[frozenset[tuple[float, float]], str] = {
    frozenset({(0, -1), (0, 1)}): "body_vertical",
    frozenset({(-1, 0), (1, 0)}): "body_horizontal",
    frozenset({(-1, 0), (0, -1)}): "body_tl",
    frozenset({(-1, 0), (0, 1)}): "body_bl",
    frozenset({(1, 0), (0, -1)}): "body_tr",
    frozenset({(1, 0), (0, 1)}): "body_br",
}
SPRITE_NAMES = (
    *HEAD_SPRITES.values(),
    *TAIL_SPRITES.values(),
    *BODY_SPRITES.values(),
)

KEY_TO_DIRECTION = {
    pygame.K_UP: Vector2(0, -1),
    pygame.K_RIGHT: Vector2(1, 0),
    pygame.K_DOWN: Vector2(0, 1),
    pygame.K_LEFT: Vector2(-1, 0),
}


class GameState(Enum):
    """The phases of the game; only PLAYING moves the snake."""

    PLAYING = "playing"
    PAUSED = "paused"
    RESUMING = "resuming"  # the 3-2-1 countdown after a pause
    EXPLODING = "exploding"  # the red flash after eating a bomb
    GAME_OVER = "game_over"


PLAYING = GameState.PLAYING
PAUSED = GameState.PAUSED
RESUMING = GameState.RESUMING
EXPLODING = GameState.EXPLODING
GAME_OVER = GameState.GAME_OVER

# set up by the __main__ block below (or by the tests) before anything is drawn
screen: pygame.Surface
game_font: pygame.font.Font


class Playable(Protocol):
    """Anything with a play() method: a pygame Sound or a SilentSound."""

    def play(self) -> object:
        """Play the sound."""


class RandomSource(Protocol):
    """The part of the random module the spawner uses, so tests can script it."""

    def random(self) -> float:
        """Return a float in [0, 1)."""

    def choice(self, seq: Sequence[Cell]) -> Cell:
        """Return one element of a non-empty sequence."""


class AssetError(Exception):
    """A required image or font could not be loaded."""


class SilentSound:
    """Stand-in for a sound that could not be loaded."""

    def play(self) -> None:
        """Do nothing."""


def load_image(path: str) -> pygame.Surface:
    """Load an image with transparency; raise AssetError if it is missing."""
    try:
        return pygame.image.load(path).convert_alpha()
    except (OSError, pygame.error) as error:
        raise AssetError(f'Could not load image "{path}": {error}') from error


def load_font(path: str, size: int) -> pygame.font.Font:
    """Load a font file; raise AssetError if it is missing."""
    try:
        return pygame.font.Font(path, size)
    except (OSError, pygame.error) as error:
        raise AssetError(f'Could not load font "{path}": {error}') from error


def load_sound(path: str) -> Playable:
    """Load a sound, or a SilentSound if that fails (the game can run without audio)."""
    try:
        return pygame.mixer.Sound(path)
    except (OSError, pygame.error) as error:
        print(f'Warning: could not load sound "{path}" ({error}), playing without it')
        return SilentSound()


def step(origin: Vector2, target: Vector2) -> tuple[float, float]:
    """Return the offset from origin to target as a hashable pair."""
    return (target.x - origin.x, target.y - origin.y)


def initial_body() -> list[Vector2]:
    """Return a fresh list of blocks in the snake's starting position."""
    return [Vector2(cell) for cell in START_BODY]


def blit_centered(surface: pygame.Surface, offset_y: int = 0) -> None:
    """Draw a surface in the middle of the screen, shifted down by offset_y pixels."""
    center_x, center_y = screen.get_rect().center
    screen.blit(surface, surface.get_rect(center=(center_x, center_y + offset_y)))


def render_grass() -> pygame.Surface:
    """Draw the checkerboard background once; every frame then only blits it."""
    grass = pygame.Surface(screen.get_size())
    grass.fill(BACKGROUND_COLOR)
    for row in range(CELL_NUMBER):
        for col in range(row % 2, CELL_NUMBER, 2):
            tile = (col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            grass.fill(GRASS_COLOR, tile)
    return grass


class PixelText:
    """Renders text in a pixel font, or in a scaled-up built-in font as fallback."""

    def __init__(self, size: int, fallback_size: int, fallback_scale: int) -> None:
        self.scale = 1
        try:
            self.font = pygame.font.Font(PIXEL_FONT_PATH, size)
        except (OSError, pygame.error):
            self.font = pygame.font.Font(None, fallback_size)
            self.scale = fallback_scale

    def render(self, text: str, color: Color) -> pygame.Surface:
        """Render text without anti-aliasing, so the pixels stay crisp."""
        surface = self.font.render(text, False, color)
        if self.scale != 1:
            size = (surface.get_width() * self.scale, surface.get_height() * self.scale)
            surface = pygame.transform.scale(surface, size)
        return surface


class Snake:
    """The snake: its blocks, heading, sprites and eating sound."""

    def __init__(self) -> None:
        self.body = initial_body()
        self.direction = Vector2(0, 0)
        self.new_block = False
        self.sprites = {
            name: load_image(f"Graphics/{name}.png") for name in SPRITE_NAMES
        }
        self.crunch_sound = load_sound("Sound/crunch.wav")

    @property
    def score(self) -> int:
        """Apples eaten so far."""
        return len(self.body) - INITIAL_LENGTH

    def sprite_for(self, index: int) -> pygame.Surface:
        """Pick the sprite for the block at index from where its neighbours are."""
        body = self.body
        block = body[index]
        if index == 0:
            name = HEAD_SPRITES.get(step(block, body[1]), "head_right")
        elif index == len(body) - 1:
            name = TAIL_SPRITES.get(step(block, body[-2]), "tail_left")
        else:
            neighbours = frozenset(
                {step(block, body[index + 1]), step(block, body[index - 1])}
            )
            name = BODY_SPRITES.get(neighbours, "body_vertical")
        return self.sprites[name]

    def draw_snake(self) -> None:
        """Draw every block on its grid tile."""
        for index, block in enumerate(self.body):
            rect = pygame.Rect(
                int(block.x * CELL_SIZE), int(block.y * CELL_SIZE), CELL_SIZE, CELL_SIZE
            )
            screen.blit(self.sprite_for(index), rect)

    def move_snake(self) -> None:
        """Advance one tile; keep the tail if an apple was just eaten."""
        new_head = self.body[0] + self.direction
        kept_blocks = self.body if self.new_block else self.body[:-1]
        self.body = [new_head, *kept_blocks]
        self.new_block = False

    def set_direction(self, new_direction: Vector2) -> None:
        """Turn the snake, unless that would send the head straight into its neck."""
        if self.body[0] + new_direction != self.body[1]:
            self.direction = new_direction

    def add_block(self) -> None:
        """Grow by one block on the next move."""
        self.new_block = True

    def play_crunch_sound(self) -> None:
        """Play the eating sound."""
        self.crunch_sound.play()

    def cell_ahead(self) -> Vector2:
        """Return the tile the head is about to enter."""
        # before the first key press there is no direction, so use the way it faces
        facing = self.body[0] - self.body[1]
        return self.body[0] + (self.direction if self.direction else facing)

    def reset(self) -> None:
        """Go back to the starting position and wait for a key press."""
        self.body = initial_body()
        self.direction = Vector2(0, 0)
        self.new_block = False


class Item(ABC):
    """Something on the board that the snake can run into."""

    def __init__(self, sprite: pygame.Surface) -> None:
        self.sprite = sprite
        self.pos = Vector2(0, 0)

    def draw(self) -> None:
        """Draw the item on its grid tile."""
        rect = pygame.Rect(
            int(self.pos.x * CELL_SIZE),
            int(self.pos.y * CELL_SIZE),
            CELL_SIZE,
            CELL_SIZE,
        )
        screen.blit(self.sprite, rect)

    @abstractmethod
    def on_eaten(self, game: Game) -> None:
        """React to the snake's head reaching this item."""


class Apple(Item):
    """Grows the snake and moves to a new tile when eaten."""

    def on_eaten(self, game: Game) -> None:
        """Grow, crunch, and respawn the items."""
        game.snake.add_block()
        game.snake.play_crunch_sound()
        if not game.item_spawner.respawn(game.snake):
            game.game_over(WIN_TITLE)  # no free tile left, the board is full


class Bomb(Item):
    """Ends the game with an explosion when eaten."""

    def __init__(self, sprite: pygame.Surface, explosion_sound: Playable) -> None:
        super().__init__(sprite)
        self.explosion_sound = explosion_sound

    def on_eaten(self, game: Game) -> None:
        """Explode."""
        self.explosion_sound.play()
        game.start_explosion()


class ItemSpawner:
    """Owns the apple and the bomb, and decides where they appear."""

    def __init__(
        self,
        grid_size: int,
        bomb_chance: float = 0.5,
        rng: RandomSource = random,
        blocked_cells: Iterable[Cell] = (),
    ) -> None:
        if not 0 <= bomb_chance <= 1:
            msg = f"bomb_chance must be between 0 and 1, got {bomb_chance}"
            raise ValueError(msg)
        self.grid_size = grid_size
        self.bomb_chance = bomb_chance
        self.rng = rng
        self.blocked_cells = set(blocked_cells)

        self.apple = Apple(load_image("Graphics/apple.png"))
        self.bomb: Bomb | None = None
        self.bomb_sprite = load_image("Graphics/bomb.png")
        self.explosion_sound = load_sound("Sound/explosion.wav")

    def items(self) -> list[Item]:
        """Return the apple, plus the bomb if there is one."""
        return [self.apple] if self.bomb is None else [self.apple, self.bomb]

    def draw_items(self) -> None:
        """Draw every item."""
        for item in self.items():
            item.draw()

    def respawn(self, snake: Snake, allow_bomb: bool = True) -> bool:
        """Move the apple, drop the old bomb and roll for a new one.

        Called only when an apple is eaten (or on a fresh start).
        Returns False when there is no free tile for the apple.
        """
        self.bomb = None
        free_cells = self.free_cells(snake)
        if not free_cells:
            return False

        apple_cell = self.rng.choice(free_cells)
        self.apple.pos = Vector2(apple_cell)
        free_cells.remove(apple_cell)

        if allow_bomb and free_cells and self.rng.random() < self.bomb_chance:
            self.bomb = Bomb(self.bomb_sprite, self.explosion_sound)
            self.bomb.pos = Vector2(self.rng.choice(free_cells))
        return True

    def free_cells(self, snake: Snake) -> list[Cell]:
        """Return the tiles items may use: not the snake, blocked tiles or its path."""
        occupied = {self.cell(block) for block in snake.body} | self.blocked_cells
        free_cells = [
            (x, y)
            for x in range(self.grid_size)
            for y in range(self.grid_size)
            if (x, y) not in occupied
        ]
        # keep items off the tile in front of the head, unless nothing else is left
        ahead = self.cell(snake.cell_ahead())
        return [cell for cell in free_cells if cell != ahead] or free_cells

    @staticmethod
    def cell(position: Vector2) -> Cell:
        """Convert a position vector to a grid tile."""
        return (int(position.x), int(position.y))


class Button(ABC):
    """A clickable rectangle that calls on_click while it is enabled."""

    def __init__(
        self,
        rect: pygame.Rect,
        on_click: Callable[[], None],
        is_enabled: Callable[[], bool] = lambda: True,
    ) -> None:
        self.rect = rect
        self.on_click = on_click
        self.is_enabled = is_enabled

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Call on_click for a left click inside the button; return whether it did."""
        clicked = (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.is_enabled()
            and self.rect.collidepoint(event.pos)
        )
        if clicked:
            self.on_click()
        return clicked

    def draw(self) -> None:
        """Draw the button, highlighted while the mouse is over it."""
        hovered = self.is_enabled() and self.rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(
            screen, GRASS_HOVER_COLOR if hovered else GRASS_COLOR, self.rect
        )
        icon = self.get_icon()
        screen.blit(icon, icon.get_rect(center=self.rect.center))
        pygame.draw.rect(screen, DARK_GREEN, self.rect, 2)

    @abstractmethod
    def get_icon(self) -> pygame.Surface:
        """Return the icon to draw right now."""


class PauseButton(Button):
    """The pause/resume button on the top right tile."""

    def __init__(self, game: Game) -> None:
        # the tile is out of play, see Game.blocked_cells
        rect = pygame.Rect((CELL_NUMBER - 1) * CELL_SIZE, 0, CELL_SIZE, CELL_SIZE)
        super().__init__(
            rect, game.toggle_pause, lambda: game.state in (PLAYING, PAUSED, RESUMING)
        )
        self.game = game
        icon_size = (CELL_SIZE - 12, CELL_SIZE - 12)
        self.pause_icon = pygame.transform.smoothscale(
            load_image("Graphics/pause.png"), icon_size
        )
        self.play_icon = pygame.transform.smoothscale(
            load_image("Graphics/play.png"), icon_size
        )

    def get_icon(self) -> pygame.Surface:
        """Show play while paused, pause otherwise."""
        return self.play_icon if self.game.state == PAUSED else self.pause_icon


class Game:
    """Ties the snake, items, pause button and game states together."""

    def __init__(self) -> None:
        self.snake = Snake()
        # under the pause button: no items spawn there and the snake dies on it
        self.blocked_cells = {(CELL_NUMBER - 1, 0)}
        self.item_spawner = ItemSpawner(CELL_NUMBER, blocked_cells=self.blocked_cells)
        self.pause_button = PauseButton(self)
        self.title_text = PixelText(32, 16, 4)
        self.body_text = PixelText(16, 16, 2)
        self.countdown_text = PixelText(96, 16, 10)
        self.grass = render_grass()
        self.overlay = pygame.Surface(screen.get_size())
        self.state = PLAYING
        self.state_start = 0
        self.game_over_title = GAME_OVER_TITLE
        self.final_score = 0
        self.start_new_round()

    def start_new_round(self) -> None:
        """Reset the snake and place a first apple (never with a bomb)."""
        self.snake.reset()
        self.item_spawner.respawn(self.snake, allow_bomb=False)
        self.state = PLAYING

    def update(self) -> None:
        """Advance the game by one tick."""
        # the snake stays put until the first key press of a round
        if self.state != PLAYING or not self.snake.direction:
            return
        self.snake.move_snake()
        self.check_collision()
        if self.state == PLAYING:
            self.check_fail()

    def update_state(self) -> None:
        """Move on from the timed states (explosion flash, countdown) when due."""
        elapsed = pygame.time.get_ticks() - self.state_start
        if self.state == EXPLODING and elapsed >= EXPLOSION_FLASH_MS:
            self.game_over()
        elif self.state == RESUMING and elapsed >= COUNTDOWN_STEPS * COUNTDOWN_STEP_MS:
            self.state = PLAYING

    def toggle_pause(self) -> None:
        """Pause, or start the resume countdown (ignored while exploding/game over)."""
        # toggling during the countdown pauses again
        if self.state in (PLAYING, RESUMING):
            self.state = PAUSED
        elif self.state == PAUSED:
            self.state = RESUMING
            self.state_start = pygame.time.get_ticks()

    def handle_click(self, event: pygame.event.Event) -> None:
        """Pass a mouse click on to the pause button."""
        self.pause_button.handle_event(event)

    def handle_key(self, key: int) -> None:
        """Restart, pause or steer, depending on the state and the key."""
        if self.state == GAME_OVER:
            self.start_new_round()
        elif key == pygame.K_p:
            self.toggle_pause()
        elif self.state == PLAYING and key in KEY_TO_DIRECTION:
            self.snake.set_direction(KEY_TO_DIRECTION[key])

    def draw_elements(self) -> None:
        """Draw the whole frame."""
        self.draw_grass()
        self.item_spawner.draw_items()
        self.snake.draw_snake()
        self.draw_score()
        if self.state == PAUSED:
            self.draw_paused()
        elif self.state == RESUMING:
            self.draw_countdown()
        # above the pause/countdown overlay so it stays clickable,
        # below the flash and game over ones
        self.pause_button.draw()
        if self.state == EXPLODING:
            self.draw_explosion_flash()
        elif self.state == GAME_OVER:
            self.draw_game_over()

    def check_collision(self) -> None:
        """Let the item under the snake's head react."""
        for item in self.item_spawner.items():
            if item.pos == self.snake.body[0]:
                item.on_eaten(self)
                break

    def check_fail(self) -> None:
        """End the game if the head hit a wall, the blocked tile or the body."""
        head = self.snake.body[0]
        hit_wall = not (0 <= head.x < CELL_NUMBER and 0 <= head.y < CELL_NUMBER)
        hit_blocked_tile = self.item_spawner.cell(head) in self.blocked_cells
        hit_itself = head in self.snake.body[1:]
        if hit_wall or hit_blocked_tile or hit_itself:
            self.game_over()

    def start_explosion(self) -> None:
        """Start the red flash; the game is frozen until it ends."""
        self.state = EXPLODING
        self.state_start = pygame.time.get_ticks()

    def game_over(self, title: str = GAME_OVER_TITLE) -> None:
        """Freeze on the game over screen, remembering the score."""
        self.state = GAME_OVER
        self.game_over_title = title
        self.final_score = self.snake.score

    def draw_overlay(self, color: Color, alpha: int) -> None:
        """Tint the whole screen with a translucent colour."""
        self.overlay.fill(color)
        self.overlay.set_alpha(alpha)
        screen.blit(self.overlay, (0, 0))

    def draw_explosion_flash(self) -> None:
        """Draw the red flash, fading out over EXPLOSION_FLASH_MS."""
        elapsed = pygame.time.get_ticks() - self.state_start
        progress = min(1, elapsed / EXPLOSION_FLASH_MS)
        alpha = FLASH_ALPHA_START + (FLASH_ALPHA_END - FLASH_ALPHA_START) * progress
        self.draw_overlay(FLASH_COLOR, int(alpha))

    def draw_paused(self) -> None:
        """Draw the pause screen."""
        self.draw_overlay(BLACK, DIM_ALPHA)
        blit_centered(self.title_text.render("PAUSED", WHITE), -20)
        blit_centered(self.body_text.render(PAUSE_HINT, HINT_COLOR), 40)

    def draw_countdown(self) -> None:
        """Draw the 3-2-1 countdown."""
        self.draw_overlay(BLACK, DIM_ALPHA)
        elapsed = pygame.time.get_ticks() - self.state_start
        number = max(1, COUNTDOWN_STEPS - elapsed // COUNTDOWN_STEP_MS)
        blit_centered(self.countdown_text.render(str(number), WHITE))

    def draw_game_over(self) -> None:
        """Draw the game over screen with the score and a blinking hint."""
        self.draw_overlay(GAME_OVER_OVERLAY_COLOR, GAME_OVER_ALPHA)
        blit_centered(
            self.title_text.render(self.game_over_title, GAME_OVER_TEXT_COLOR), -60
        )
        blit_centered(self.body_text.render(f"SCORE: {self.final_score}", WHITE), 10)
        if pygame.time.get_ticks() // 500 % 2 == 0:  # blinking hint
            blit_centered(self.body_text.render(GAME_OVER_HINT, HINT_COLOR), 70)

    def draw_grass(self) -> None:
        """Draw the background (a single blit of the pre-rendered checkerboard)."""
        screen.blit(self.grass, (0, 0))

    def draw_score(self) -> None:
        """Draw the apple counter in the bottom right corner."""
        score_surface = game_font.render(str(self.snake.score), True, DARK_GREEN)
        score_x = int(CELL_SIZE * CELL_NUMBER - 60)
        score_y = int(CELL_SIZE * CELL_NUMBER - 40)
        score_rect = score_surface.get_rect(center=(score_x, score_y))
        apple_sprite = self.item_spawner.apple.sprite
        apple_rect = apple_sprite.get_rect(
            midright=(score_rect.left, score_rect.centery)
        )
        bg_rect = pygame.Rect(
            apple_rect.left,
            apple_rect.top,
            apple_rect.width + score_rect.width + 6,
            apple_rect.height,
        )

        pygame.draw.rect(screen, GRASS_COLOR, bg_rect)
        screen.blit(score_surface, score_rect)
        screen.blit(apple_sprite, apple_rect)
        pygame.draw.rect(screen, DARK_GREEN, bg_rect, 2)


if __name__ == "__main__":
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    screen = pygame.display.set_mode((CELL_NUMBER * CELL_SIZE, CELL_NUMBER * CELL_SIZE))
    clock = pygame.time.Clock()

    try:
        game_font = load_font("Font/PoetsenOne-Regular.ttf", 25)
        main_game = Game()
    except AssetError as error:
        print(f"Error: {error}")
        pygame.quit()
        sys.exit(1)

    SCREEN_UPDATE = pygame.USEREVENT
    pygame.time.set_timer(SCREEN_UPDATE, TICK_MS)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == SCREEN_UPDATE:
                main_game.update()
            if event.type == pygame.KEYDOWN:
                main_game.handle_key(event.key)
            if event.type == pygame.MOUSEBUTTONDOWN:
                main_game.handle_click(event)

        main_game.update_state()
        main_game.draw_elements()  # the pre-rendered grass covers the whole window
        pygame.display.update()
        clock.tick(60)
