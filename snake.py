import pygame,sys,random
from abc import ABC,abstractmethod
from pygame.math import Vector2

PIXEL_FONT_PATH = 'Font/PressStart2P-Regular.ttf' # optional, falls back to a scaled-up built-in font
GAME_OVER_TITLE = 'GAME OVER'
GAME_OVER_HINT = 'PRESS ANY KEY TO RESTART'
WIN_TITLE = 'YOU WIN!'
EXPLOSION_FLASH_MS = 600

PLAYING,EXPLODING,GAME_OVER = 'playing','exploding','game_over'

class ASSET_ERROR(Exception):
	pass

class SILENT_SOUND:
	def play(self):
		pass

def load_image(path):
	try:
		return pygame.image.load(path).convert_alpha()
	except (OSError,pygame.error) as error:
		raise ASSET_ERROR(f'Could not load image "{path}": {error}') from error

def load_font(path,size):
	try:
		return pygame.font.Font(path,size)
	except (OSError,pygame.error) as error:
		raise ASSET_ERROR(f'Could not load font "{path}": {error}') from error

def load_sound(path):
	# a missing sound or a missing audio device should not stop the game
	try:
		return pygame.mixer.Sound(path)
	except (OSError,pygame.error) as error:
		print(f'Warning: could not load sound "{path}" ({error}), playing without it')
		return SILENT_SOUND()

class PIXEL_TEXT:
	def __init__(self,size,fallback_size,fallback_scale):
		self.scale = 1
		try:
			self.font = pygame.font.Font(PIXEL_FONT_PATH,size)
		except (OSError,pygame.error):
			self.font = pygame.font.Font(None,fallback_size)
			self.scale = fallback_scale

	def render(self,text,color):
		surface = self.font.render(text,False,color)
		if self.scale != 1:
			surface = pygame.transform.scale(surface,(surface.get_width() * self.scale,surface.get_height() * self.scale))
		return surface

class SNAKE:
	def __init__(self):
		self.body = [Vector2(5,10),Vector2(4,10),Vector2(3,10)]
		self.direction = Vector2(0,0)
		self.new_block = False

		self.head_up = load_image('Graphics/head_up.png')
		self.head_down = load_image('Graphics/head_down.png')
		self.head_right = load_image('Graphics/head_right.png')
		self.head_left = load_image('Graphics/head_left.png')

		self.tail_up = load_image('Graphics/tail_up.png')
		self.tail_down = load_image('Graphics/tail_down.png')
		self.tail_right = load_image('Graphics/tail_right.png')
		self.tail_left = load_image('Graphics/tail_left.png')

		self.body_vertical = load_image('Graphics/body_vertical.png')
		self.body_horizontal = load_image('Graphics/body_horizontal.png')

		self.body_tr = load_image('Graphics/body_tr.png')
		self.body_tl = load_image('Graphics/body_tl.png')
		self.body_br = load_image('Graphics/body_br.png')
		self.body_bl = load_image('Graphics/body_bl.png')
		self.crunch_sound = load_sound('Sound/crunch.wav')

	def draw_snake(self):
		self.update_head_graphics()
		self.update_tail_graphics()

		for index,block in enumerate(self.body):
			x_pos = int(block.x * cell_size)
			y_pos = int(block.y * cell_size)
			block_rect = pygame.Rect(x_pos,y_pos,cell_size,cell_size)

			if index == 0:
				screen.blit(self.head,block_rect)
			elif index == len(self.body) - 1:
				screen.blit(self.tail,block_rect)
			else:
				previous_block = self.body[index + 1] - block
				next_block = self.body[index - 1] - block
				if previous_block.x == next_block.x:
					screen.blit(self.body_vertical,block_rect)
				elif previous_block.y == next_block.y:
					screen.blit(self.body_horizontal,block_rect)
				else:
					if previous_block.x == -1 and next_block.y == -1 or previous_block.y == -1 and next_block.x == -1:
						screen.blit(self.body_tl,block_rect)
					elif previous_block.x == -1 and next_block.y == 1 or previous_block.y == 1 and next_block.x == -1:
						screen.blit(self.body_bl,block_rect)
					elif previous_block.x == 1 and next_block.y == -1 or previous_block.y == -1 and next_block.x == 1:
						screen.blit(self.body_tr,block_rect)
					elif previous_block.x == 1 and next_block.y == 1 or previous_block.y == 1 and next_block.x == 1:
						screen.blit(self.body_br,block_rect)

	def update_head_graphics(self):
		head_relation = self.body[1] - self.body[0]
		if head_relation == Vector2(1,0): self.head = self.head_left
		elif head_relation == Vector2(-1,0): self.head = self.head_right
		elif head_relation == Vector2(0,1): self.head = self.head_up
		elif head_relation == Vector2(0,-1): self.head = self.head_down

	def update_tail_graphics(self):
		tail_relation = self.body[-2] - self.body[-1]
		if tail_relation == Vector2(1,0): self.tail = self.tail_left
		elif tail_relation == Vector2(-1,0): self.tail = self.tail_right
		elif tail_relation == Vector2(0,1): self.tail = self.tail_up
		elif tail_relation == Vector2(0,-1): self.tail = self.tail_down

	def move_snake(self):
		if self.new_block == True:
			body_copy = self.body[:]
			body_copy.insert(0,body_copy[0] + self.direction)
			self.body = body_copy[:]
			self.new_block = False
		else:
			body_copy = self.body[:-1]
			body_copy.insert(0,body_copy[0] + self.direction)
			self.body = body_copy[:]

	def add_block(self):
		self.new_block = True

	def play_crunch_sound(self):
		self.crunch_sound.play()

	def cell_ahead(self):
		# before the first key press the snake has no direction, so use the way it is facing
		direction = self.direction if self.direction != Vector2(0,0) else self.body[0] - self.body[1]
		return self.body[0] + direction

	def reset(self):
		self.body = [Vector2(5,10),Vector2(4,10),Vector2(3,10)]
		self.direction = Vector2(0,0)
		self.new_block = False


class ITEM(ABC):
	def __init__(self,sprite):
		self.sprite = sprite
		self.pos = Vector2(0,0)

	def draw(self):
		item_rect = pygame.Rect(int(self.pos.x * cell_size),int(self.pos.y * cell_size),cell_size,cell_size)
		screen.blit(self.sprite,item_rect)

	@abstractmethod
	def on_eaten(self,game):
		pass

class APPLE(ITEM):
	def on_eaten(self,game):
		game.snake.add_block()
		game.snake.play_crunch_sound()
		if not game.item_spawner.respawn(game.snake):
			game.game_over(WIN_TITLE) # no free tile left, the board is full

class BOMB(ITEM):
	def __init__(self,sprite,explosion_sound):
		super().__init__(sprite)
		self.explosion_sound = explosion_sound

	def on_eaten(self,game):
		self.explosion_sound.play()
		game.start_explosion()

class ITEM_SPAWNER:
	def __init__(self,grid_size,bomb_chance = 0.5,rng = random):
		if not 0 <= bomb_chance <= 1:
			raise ValueError(f'bomb_chance must be between 0 and 1, got {bomb_chance}')
		self.grid_size = grid_size
		self.bomb_chance = bomb_chance
		self.rng = rng

		self.apple = APPLE(load_image('Graphics/apple.png'))
		self.bomb = None
		self.bomb_sprite = load_image('Graphics/bomb.png')
		self.explosion_sound = load_sound('Sound/explosion.wav')

	def items(self):
		return [self.apple] if self.bomb is None else [self.apple,self.bomb]

	def draw_items(self):
		for item in self.items():
			item.draw()

	def respawn(self,snake,allow_bomb = True):
		# called only when an apple is eaten (or on a fresh start): the old bomb goes away
		# and gets re-rolled. Returns False when there is no free tile for the apple.
		self.bomb = None
		free_cells = self.free_cells(snake)
		if not free_cells:
			return False

		apple_cell = self.rng.choice(free_cells)
		self.apple.pos = Vector2(apple_cell)
		free_cells.remove(apple_cell)

		if allow_bomb and free_cells and self.rng.random() < self.bomb_chance:
			self.bomb = BOMB(self.bomb_sprite,self.explosion_sound)
			self.bomb.pos = Vector2(self.rng.choice(free_cells))
		return True

	def free_cells(self,snake):
		occupied = {self.cell(block) for block in snake.body}
		free_cells = [(x,y) for x in range(self.grid_size) for y in range(self.grid_size) if (x,y) not in occupied]
		# keep items off the tile right in front of the snake's head, unless nothing else is left
		ahead = self.cell(snake.cell_ahead())
		return [cell for cell in free_cells if cell != ahead] or free_cells

	@staticmethod
	def cell(position):
		return (int(position.x),int(position.y))

class MAIN:
	def __init__(self):
		self.snake = SNAKE()
		self.item_spawner = ITEM_SPAWNER(cell_number)
		self.title_text = PIXEL_TEXT(32,16,4)
		self.body_text = PIXEL_TEXT(16,16,2)
		self.overlay = pygame.Surface(screen.get_size())
		self.state = PLAYING
		self.state_start = 0
		self.game_over_title = GAME_OVER_TITLE
		self.final_score = 0
		self.start_new_round()

	def start_new_round(self):
		self.snake.reset()
		self.item_spawner.respawn(self.snake,allow_bomb = False)
		self.state = PLAYING

	def update(self):
		# the snake stays put until the first key press of a round
		if self.state != PLAYING or self.snake.direction == Vector2(0,0):
			return
		self.snake.move_snake()
		self.check_collision()
		if self.state == PLAYING:
			self.check_fail()

	def update_state(self):
		if self.state == EXPLODING and pygame.time.get_ticks() - self.state_start >= EXPLOSION_FLASH_MS:
			self.game_over()

	def handle_key(self,key):
		if self.state == GAME_OVER:
			self.start_new_round()
		elif self.state == PLAYING:
			if key == pygame.K_UP:
				if self.snake.direction.y != 1:
					self.snake.direction = Vector2(0,-1)
			if key == pygame.K_RIGHT:
				if self.snake.direction.x != -1:
					self.snake.direction = Vector2(1,0)
			if key == pygame.K_DOWN:
				if self.snake.direction.y != -1:
					self.snake.direction = Vector2(0,1)
			if key == pygame.K_LEFT:
				if self.snake.direction.x != 1:
					self.snake.direction = Vector2(-1,0)

	def draw_elements(self):
		self.draw_grass()
		self.item_spawner.draw_items()
		self.snake.draw_snake()
		self.draw_score()
		if self.state == EXPLODING:
			self.draw_explosion_flash()
		elif self.state == GAME_OVER:
			self.draw_game_over()

	def check_collision(self):
		for item in self.item_spawner.items():
			if item.pos == self.snake.body[0]:
				item.on_eaten(self)
				break

	def check_fail(self):
		if not 0 <= self.snake.body[0].x < cell_number or not 0 <= self.snake.body[0].y < cell_number:
			self.game_over()
			return

		for block in self.snake.body[1:]:
			if block == self.snake.body[0]:
				self.game_over()
				return

	def start_explosion(self):
		self.state = EXPLODING
		self.state_start = pygame.time.get_ticks()

	def game_over(self,title = GAME_OVER_TITLE):
		self.state = GAME_OVER
		self.game_over_title = title
		self.final_score = len(self.snake.body) - 3

	def draw_explosion_flash(self):
		progress = min(1,(pygame.time.get_ticks() - self.state_start) / EXPLOSION_FLASH_MS)
		self.overlay.fill((220,20,20))
		self.overlay.set_alpha(int(200 - 100 * progress))
		screen.blit(self.overlay,(0,0))

	def draw_game_over(self):
		self.overlay.fill((60,0,0))
		self.overlay.set_alpha(190)
		screen.blit(self.overlay,(0,0))

		center_x = screen.get_width() // 2
		center_y = screen.get_height() // 2
		title_surface = self.title_text.render(self.game_over_title,(255,80,80))
		screen.blit(title_surface,title_surface.get_rect(center = (center_x,center_y - 60)))

		score_surface = self.body_text.render(f'SCORE: {self.final_score}',(255,255,255))
		screen.blit(score_surface,score_surface.get_rect(center = (center_x,center_y + 10)))

		if pygame.time.get_ticks() // 500 % 2 == 0: # blinking hint
			hint_surface = self.body_text.render(GAME_OVER_HINT,(255,220,80))
			screen.blit(hint_surface,hint_surface.get_rect(center = (center_x,center_y + 70)))

	def draw_grass(self):
		grass_color = (167,209,61)
		for row in range(cell_number):
			if row % 2 == 0: 
				for col in range(cell_number):
					if col % 2 == 0:
						grass_rect = pygame.Rect(col * cell_size,row * cell_size,cell_size,cell_size)
						pygame.draw.rect(screen,grass_color,grass_rect)
			else:
				for col in range(cell_number):
					if col % 2 != 0:
						grass_rect = pygame.Rect(col * cell_size,row * cell_size,cell_size,cell_size)
						pygame.draw.rect(screen,grass_color,grass_rect)			

	def draw_score(self):
		score_text = str(len(self.snake.body) - 3)
		score_surface = game_font.render(score_text,True,(56,74,12))
		score_x = int(cell_size * cell_number - 60)
		score_y = int(cell_size * cell_number - 40)
		score_rect = score_surface.get_rect(center = (score_x,score_y))
		apple_sprite = self.item_spawner.apple.sprite
		apple_rect = apple_sprite.get_rect(midright = (score_rect.left,score_rect.centery))
		bg_rect = pygame.Rect(apple_rect.left,apple_rect.top,apple_rect.width + score_rect.width + 6,apple_rect.height)

		pygame.draw.rect(screen,(167,209,61),bg_rect)
		screen.blit(score_surface,score_rect)
		screen.blit(apple_sprite,apple_rect)
		pygame.draw.rect(screen,(56,74,12),bg_rect,2)

pygame.mixer.pre_init(44100,-16,2,512)
pygame.init()
cell_size = 40
cell_number = 20
screen = pygame.display.set_mode((cell_number * cell_size,cell_number * cell_size))
clock = pygame.time.Clock()

try:
	game_font = load_font('Font/PoetsenOne-Regular.ttf',25)
	main_game = MAIN()
except ASSET_ERROR as error:
	print(f'Error: {error}')
	pygame.quit()
	sys.exit(1)

SCREEN_UPDATE = pygame.USEREVENT
pygame.time.set_timer(SCREEN_UPDATE,150)

while True:
	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			pygame.quit()
			sys.exit()
		if event.type == SCREEN_UPDATE:
			main_game.update()
		if event.type == pygame.KEYDOWN:
			main_game.handle_key(event.key)

	main_game.update_state()
	screen.fill((175,215,70))
	main_game.draw_elements()
	pygame.display.update()
	clock.tick(60)