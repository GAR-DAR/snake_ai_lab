import os
import random
import sys
from abc import ABC, abstractmethod

import pygame
from pygame.math import Vector2

# Constant dictionary for directional input mapping
KEY_DIRECTIONS: dict[int, Vector2] = {
    pygame.K_UP: Vector2(0, -1),
    pygame.K_DOWN: Vector2(0, 1),
    pygame.K_LEFT: Vector2(-1, 0),
    pygame.K_RIGHT: Vector2(1, 0),
}


# Helper functions for robust asset loading with fallback error handling
def load_image_safe(
    file_path: str, size: tuple[int, int] | None = None
) -> pygame.Surface:
    if not os.path.exists(file_path):
        alt_path = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(alt_path):
            file_path = alt_path
    try:
        img = pygame.image.load(file_path).convert_alpha()
        if size:
            img = pygame.transform.scale(img, size)
        return img
    except (pygame.error, FileNotFoundError, OSError) as e:
        print(f"Warning: Could not load image from '{file_path}': {e}")
        w, h = size if size else (40, 40)
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (200, 50, 50), (0, 0, w, h))
        return surf


def load_sound_safe(file_path: str) -> object:
    if not os.path.exists(file_path):
        alt_path = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(alt_path):
            file_path = alt_path
    try:
        return pygame.mixer.Sound(file_path)
    except (pygame.error, FileNotFoundError, OSError) as e:
        print(f"Warning: Could not load sound from '{file_path}': {e}")

        class DummySound:
            def play(self) -> None:
                pass

        return DummySound()


# Base abstract class for items
class Item(ABC):
    def __init__(self, pos: Vector2 | None = None) -> None:
        self.pos: Vector2 = pos if pos is not None else Vector2(0, 0)

    @abstractmethod
    def draw(self, screen: pygame.Surface | None, cell_size: int) -> None:
        pass

    def randomize(self, occupied_positions: list[Vector2], cell_number: int) -> bool:
        max_attempts = cell_number * cell_number * 2
        occupied_set = {(p.x, p.y) for p in occupied_positions}
        if len(occupied_set) >= cell_number * cell_number:
            return False
        for _ in range(max_attempts):
            x = random.randint(0, cell_number - 1)
            y = random.randint(0, cell_number - 1)
            if (x, y) not in occupied_set:
                self.pos = Vector2(x, y)
                return True
        # Fallback search if grid is almost completely full
        all_positions = [
            Vector2(x, y)
            for x in range(cell_number)
            for y in range(cell_number)
            if (x, y) not in occupied_set
        ]
        if all_positions:
            self.pos = random.choice(all_positions)
            return True
        return False


# Fruit subclass
class Fruit(Item):
    def __init__(self, image: pygame.Surface, pos: Vector2 | None = None) -> None:
        super().__init__(pos)
        self.image: pygame.Surface = image

    def draw(self, screen: pygame.Surface | None, cell_size: int) -> None:
        if screen is None:
            screen = pygame.display.get_surface()
        if not screen:
            return
        fruit_rect = pygame.Rect(
            int(self.pos.x * cell_size),
            int(self.pos.y * cell_size),
            cell_size,
            cell_size,
        )
        screen.blit(self.image, fruit_rect)


# Bomb subclass
class Bomb(Item):
    def __init__(
        self,
        image: pygame.Surface,
        explosion_sound: object,
        pos: Vector2 | None = None,
    ) -> None:
        super().__init__(pos)
        self.image: pygame.Surface = image
        self.explosion_sound: object = explosion_sound

    def draw(self, screen: pygame.Surface | None, cell_size: int) -> None:
        if screen is None:
            screen = pygame.display.get_surface()
        if not screen:
            return
        bomb_rect = pygame.Rect(
            int(self.pos.x * cell_size),
            int(self.pos.y * cell_size),
            cell_size,
            cell_size,
        )
        screen.blit(self.image, bomb_rect)

    def play_explosion_sound(self) -> None:
        if hasattr(self.explosion_sound, "play"):
            self.explosion_sound.play()


# Item Manager for non-overlapping tile selection and spawn lifecycle
class ItemManager:
    def __init__(
        self,
        fruit_image: pygame.Surface,
        bomb_image: pygame.Surface,
        explosion_sound: object,
        cell_number: int,
    ) -> None:
        self.cell_number: int = cell_number
        self.fruit_image: pygame.Surface = fruit_image
        self.bomb_image: pygame.Surface = bomb_image
        self.explosion_sound: object = explosion_sound
        self.fruit: Fruit = Fruit(self.fruit_image)
        self.bomb: Bomb | None = None

    def spawn_initial_items(self, snake_body: list[Vector2]) -> None:
        self.fruit.randomize(snake_body, self.cell_number)
        self.bomb = None

    def update_items_on_apple_eaten(self, snake_body: list[Vector2]) -> None:
        # 1. Update fruit position ensuring empty tile
        occupied = list(snake_body)
        self.fruit.randomize(occupied, self.cell_number)
        occupied.append(self.fruit.pos)

        # 2. 50% chance to spawn a bomb
        if random.random() < 0.5:
            new_bomb = Bomb(self.bomb_image, self.explosion_sound)
            if new_bomb.randomize(occupied, self.cell_number):
                self.bomb = new_bomb
            else:
                self.bomb = None
        else:
            self.bomb = None

    def draw_items(self, screen: pygame.Surface | None, cell_size: int) -> None:
        if self.fruit:
            self.fruit.draw(screen, cell_size)
        if self.bomb:
            self.bomb.draw(screen, cell_size)


# Pause/Resume UI Button component
class PauseButton:
    def __init__(
        self,
        pause_image: pygame.Surface,
        play_image: pygame.Surface,
        screen_width: int,
        margin: int = 15,
    ) -> None:
        self.pause_image: pygame.Surface = pause_image
        self.play_image: pygame.Surface = play_image
        w = pause_image.get_width()
        h = pause_image.get_height()
        x = screen_width - w - margin
        y = margin
        self.rect: pygame.Rect = pygame.Rect(x, y, w, h)

    def draw(self, screen: pygame.Surface | None, is_paused: bool) -> None:
        if screen is None:
            screen = pygame.display.get_surface()
        if not screen:
            return
        img = self.play_image if is_paused else self.pause_image
        screen.blit(img, self.rect)

    def is_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(mouse_pos)


class Snake:
    def __init__(self) -> None:
        self.body: list[Vector2] = [
            Vector2(5, 10),
            Vector2(4, 10),
            Vector2(3, 10),
        ]
        self.direction: Vector2 = Vector2(0, 0)
        self.new_block: bool = False

        self.head_up = load_image_safe("Graphics/head_up.png")
        self.head_down = load_image_safe("Graphics/head_down.png")
        self.head_right = load_image_safe("Graphics/head_right.png")
        self.head_left = load_image_safe("Graphics/head_left.png")

        self.tail_up = load_image_safe("Graphics/tail_up.png")
        self.tail_down = load_image_safe("Graphics/tail_down.png")
        self.tail_right = load_image_safe("Graphics/tail_right.png")
        self.tail_left = load_image_safe("Graphics/tail_left.png")

        self.body_vertical = load_image_safe("Graphics/body_vertical.png")
        self.body_horizontal = load_image_safe("Graphics/body_horizontal.png")

        self.body_tr = load_image_safe("Graphics/body_tr.png")
        self.body_tl = load_image_safe("Graphics/body_tl.png")
        self.body_br = load_image_safe("Graphics/body_br.png")
        self.body_bl = load_image_safe("Graphics/body_bl.png")
        self.crunch_sound = load_sound_safe("Sound/crunch.wav")
        self.head: pygame.Surface = self.head_right
        self.tail: pygame.Surface = self.tail_left

    def draw_snake(self, screen: pygame.Surface | None = None) -> None:
        if screen is None:
            screen = pygame.display.get_surface()
        if not screen:
            return
        self.update_head_graphics()
        self.update_tail_graphics()

        for index, block in enumerate(self.body):
            x_pos = int(block.x * cell_size)
            y_pos = int(block.y * cell_size)
            block_rect = pygame.Rect(x_pos, y_pos, cell_size, cell_size)

            if index == 0:
                screen.blit(self.head, block_rect)
            elif index == len(self.body) - 1:
                screen.blit(self.tail, block_rect)
            else:
                previous_block = self.body[index + 1] - block
                next_block = self.body[index - 1] - block
                if previous_block.x == next_block.x:
                    screen.blit(self.body_vertical, block_rect)
                elif previous_block.y == next_block.y:
                    screen.blit(self.body_horizontal, block_rect)
                else:
                    if (
                        previous_block.x == -1
                        and next_block.y == -1
                        or previous_block.y == -1
                        and next_block.x == -1
                    ):
                        screen.blit(self.body_tl, block_rect)
                    elif (
                        previous_block.x == -1
                        and next_block.y == 1
                        or previous_block.y == 1
                        and next_block.x == -1
                    ):
                        screen.blit(self.body_bl, block_rect)
                    elif (
                        previous_block.x == 1
                        and next_block.y == -1
                        or previous_block.y == -1
                        and next_block.x == 1
                    ):
                        screen.blit(self.body_tr, block_rect)
                    elif (
                        previous_block.x == 1
                        and next_block.y == 1
                        or previous_block.y == 1
                        and next_block.x == 1
                    ):
                        screen.blit(self.body_br, block_rect)

    def update_head_graphics(self) -> None:
        head_relation = self.body[1] - self.body[0]
        if head_relation == Vector2(1, 0):
            self.head = self.head_left
        elif head_relation == Vector2(-1, 0):
            self.head = self.head_right
        elif head_relation == Vector2(0, 1):
            self.head = self.head_up
        elif head_relation == Vector2(0, -1):
            self.head = self.head_down

    def update_tail_graphics(self) -> None:
        tail_relation = self.body[-2] - self.body[-1]
        if tail_relation == Vector2(1, 0):
            self.tail = self.tail_left
        elif tail_relation == Vector2(-1, 0):
            self.tail = self.tail_right
        elif tail_relation == Vector2(0, 1):
            self.tail = self.tail_up
        elif tail_relation == Vector2(0, -1):
            self.tail = self.tail_down

    def move_snake(self) -> None:
        if self.direction == Vector2(0, 0):
            return
        if self.new_block:
            body_copy = self.body[:]
            body_copy.insert(0, body_copy[0] + self.direction)
            self.body = body_copy[:]
            self.new_block = False
        else:
            body_copy = self.body[:-1]
            body_copy.insert(0, body_copy[0] + self.direction)
            self.body = body_copy[:]

    def add_block(self) -> None:
        self.new_block = True

    def play_crunch_sound(self) -> None:
        if hasattr(self.crunch_sound, "play"):
            self.crunch_sound.play()

    def reset(self) -> None:
        self.body = [Vector2(5, 10), Vector2(4, 10), Vector2(3, 10)]
        self.direction = Vector2(0, 0)


# Backward compatibility alias
SNAKE = Snake


class MainGame:
    def __init__(
        self,
        apple_surf: pygame.Surface | None = None,
        bomb_surf: pygame.Surface | None = None,
        pause_surf: pygame.Surface | None = None,
        play_surf: pygame.Surface | None = None,
        sound: object | None = None,
    ) -> None:
        self.snake: Snake = Snake()
        apple_img = (
            apple_surf
            if apple_surf is not None
            else load_image_safe("Graphics/apple.png")
        )
        b_img = (
            bomb_surf if bomb_surf is not None else load_image_safe("Graphics/bomb.png")
        )
        p_img = (
            pause_surf
            if pause_surf is not None
            else load_image_safe("Graphics/pause.png", (36, 36))
        )
        pl_img = (
            play_surf
            if play_surf is not None
            else load_image_safe("Graphics/play.png", (36, 36))
        )
        snd = sound if sound is not None else load_sound_safe("Sound/explosion.wav")
        self.apple_img: pygame.Surface = apple_img

        self.item_manager: ItemManager = ItemManager(apple_img, b_img, snd, cell_number)
        self.item_manager.spawn_initial_items(self.snake.body)
        self.pause_button: PauseButton = PauseButton(
            p_img, pl_img, cell_number * cell_size
        )
        self.is_paused: bool = False

    def update(self) -> None:
        if self.is_paused:
            return
        self.snake.move_snake()
        self.check_collision()
        self.check_fail()

    def toggle_pause(self) -> None:
        self.is_paused = not self.is_paused

    def handle_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.pause_button.is_clicked(mouse_pos):
            self.toggle_pause()

    def change_direction(self, new_dir: Vector2) -> None:
        if self.snake.direction + new_dir != Vector2(0, 0):
            self.snake.direction = new_dir

    def draw_elements(self, screen: pygame.Surface | None = None) -> None:
        if screen is None:
            screen = pygame.display.get_surface()
        if not screen:
            return
        self.draw_grass(screen)
        self.item_manager.draw_items(screen, cell_size)
        self.snake.draw_snake(screen)
        self.draw_score(screen)
        self.pause_button.draw(screen, self.is_paused)

    def check_collision(self) -> None:
        # Fruit collision
        if (
            self.item_manager.fruit
            and self.item_manager.fruit.pos == self.snake.body[0]
        ):
            self.snake.add_block()
            self.snake.play_crunch_sound()
            self.item_manager.update_items_on_apple_eaten(self.snake.body)

        # Bomb collision
        if self.item_manager.bomb and self.item_manager.bomb.pos == self.snake.body[0]:
            self.item_manager.bomb.play_explosion_sound()
            self.trigger_red_flash()
            self.game_over()

    def trigger_red_flash(self, screen: pygame.Surface | None = None) -> None:
        if screen is None:
            screen = pygame.display.get_surface()
        if screen:
            screen.fill((255, 0, 0))
            pygame.display.update()
            pygame.time.delay(300)

    def check_fail(self) -> None:
        if (
            not 0 <= self.snake.body[0].x < cell_number
            or not 0 <= self.snake.body[0].y < cell_number
        ):
            self.game_over()

        for block in self.snake.body[1:]:
            if block == self.snake.body[0]:
                self.game_over()

    def game_over(self) -> None:
        self.snake.reset()
        self.item_manager.spawn_initial_items(self.snake.body)

    def draw_grass(self, screen: pygame.Surface | None = None) -> None:
        if screen is None:
            screen = pygame.display.get_surface()
        if not screen:
            return
        grass_color = (167, 209, 61)
        for row in range(cell_number):
            for col in range(cell_number):
                if (row + col) % 2 == 0:
                    grass_rect = pygame.Rect(
                        col * cell_size, row * cell_size, cell_size, cell_size
                    )
                    pygame.draw.rect(screen, grass_color, grass_rect)

    def draw_score(self, screen: pygame.Surface | None = None) -> None:
        if screen is None:
            screen = pygame.display.get_surface()
        if not screen:
            return
        score_text = str(len(self.snake.body) - 3)
        if "game_font" in globals():
            score_surface = game_font.render(score_text, True, (56, 74, 12))
        else:
            score_surface = pygame.font.SysFont("Arial", 25).render(
                score_text, True, (56, 74, 12)
            )
        score_x = int(cell_size * cell_number - 60)
        score_y = int(cell_size * cell_number - 40)
        score_rect = score_surface.get_rect(center=(score_x, score_y))
        apple_rect = self.apple_img.get_rect(
            midright=(score_rect.left, score_rect.centery)
        )
        bg_rect = pygame.Rect(
            apple_rect.left,
            apple_rect.top,
            apple_rect.width + score_rect.width + 6,
            apple_rect.height,
        )

        pygame.draw.rect(screen, (167, 209, 61), bg_rect)
        screen.blit(score_surface, score_rect)
        screen.blit(self.apple_img, apple_rect)
        pygame.draw.rect(screen, (56, 74, 12), bg_rect, 2)


# Backward compatibility alias
MAIN = MainGame

cell_size = 40
cell_number = 20

if __name__ == "__main__":
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    screen = pygame.display.set_mode((cell_number * cell_size, cell_number * cell_size))
    clock = pygame.time.Clock()
    apple = load_image_safe("Graphics/apple.png")
    bomb_img = load_image_safe("Graphics/bomb.png")
    pause_img = load_image_safe("Graphics/pause.png", (36, 36))
    play_img = load_image_safe("Graphics/play.png", (36, 36))
    explosion_sound = load_sound_safe("Sound/explosion.wav")
    try:
        game_font = pygame.font.Font("Font/PoetsenOne-Regular.ttf", 25)
    except (pygame.error, FileNotFoundError, OSError):
        game_font = pygame.font.SysFont("Arial", 25)

    SCREEN_UPDATE = pygame.USEREVENT
    pygame.time.set_timer(SCREEN_UPDATE, 150)

    main_game = MainGame()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == SCREEN_UPDATE:
                main_game.update()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                main_game.handle_click(event.pos)
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_p, pygame.K_SPACE):
                    main_game.toggle_pause()
                elif not main_game.is_paused and event.key in KEY_DIRECTIONS:
                    main_game.change_direction(KEY_DIRECTIONS[event.key])

        screen.fill((175, 215, 70))
        main_game.draw_elements()
        pygame.display.update()
        clock.tick(60)
