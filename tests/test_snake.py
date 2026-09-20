import pygame
import pytest
from pygame.math import Vector2 as V

import snake as game_module
from helpers import SNAKE_LAYOUTS,TURN_LAYOUTS,vectors

DIRECTIONS = {'right': (1,0),'left': (-1,0),'down': (0,1),'up': (0,-1)}


def test_initial_state(snake_obj):
	assert snake_obj.body == [V(5,10),V(4,10),V(3,10)]
	assert snake_obj.direction == V(0,0)
	assert snake_obj.new_block is False


@pytest.mark.parametrize('direction',DIRECTIONS.values(),ids = DIRECTIONS.keys())
def test_move_advances_head_and_keeps_length(snake_obj,direction):
	snake_obj.direction = V(direction)
	before = [block.copy() for block in snake_obj.body]

	snake_obj.move_snake()

	assert snake_obj.body[0] == before[0] + V(direction)
	assert snake_obj.body[1:] == before[:-1] # the tail block was dropped
	assert len(snake_obj.body) == 3


def test_move_after_add_block_grows_by_one_and_keeps_tail(snake_obj):
	snake_obj.direction = V(1,0)
	before = [block.copy() for block in snake_obj.body]

	snake_obj.add_block()
	snake_obj.move_snake()

	assert len(snake_obj.body) == 4
	assert snake_obj.body[1:] == before
	assert snake_obj.new_block is False


def test_growth_happens_only_once(snake_obj):
	snake_obj.direction = V(1,0)
	snake_obj.add_block()
	snake_obj.move_snake()
	snake_obj.move_snake()
	assert len(snake_obj.body) == 4


def test_reset_restores_start_position_and_pending_growth(snake_obj):
	snake_obj.direction = V(0,-1)
	snake_obj.add_block()
	snake_obj.move_snake()

	snake_obj.reset()

	assert snake_obj.body == [V(5,10),V(4,10),V(3,10)]
	assert snake_obj.direction == V(0,0)
	assert snake_obj.new_block is False


@pytest.mark.parametrize('layout',SNAKE_LAYOUTS.keys())
def test_cell_ahead_follows_direction_or_facing(snake_obj,set_snake,layout):
	cells,direction = SNAKE_LAYOUTS[layout]
	set_snake(snake_obj,cells,direction)
	head,neck = V(cells[0]),V(cells[1])

	expected = head + (V(direction) if V(direction) != V(0,0) else head - neck)

	assert snake_obj.cell_ahead() == expected


def test_crunch_sound_is_played(snake_obj):
	snake_obj.play_crunch_sound()
	snake_obj.crunch_sound.play.assert_called_once_with()


@pytest.mark.parametrize('cells,head_sprite',[
	([(5,5),(6,5),(7,5)],'head_left'), # body to the right -> looking left
	([(5,5),(4,5),(3,5)],'head_right'),
	([(5,5),(5,6),(5,7)],'head_up'),
	([(5,5),(5,4),(5,3)],'head_down'),
])
def test_head_sprite_follows_neck_position(snake_obj,set_snake,cells,head_sprite):
	set_snake(snake_obj,cells)
	snake_obj.update_head_graphics()
	assert snake_obj.head is getattr(snake_obj,head_sprite)


@pytest.mark.parametrize('cells,tail_sprite',[
	([(7,5),(6,5),(5,5)],'tail_left'), # the rest of the snake is to the right of the tail -> tail points left
	([(5,5),(6,5),(7,5)],'tail_right'),
	([(5,7),(5,6),(5,5)],'tail_up'),
	([(5,5),(5,6),(5,7)],'tail_down'),
])
def test_tail_sprite_follows_previous_block(snake_obj,set_snake,cells,tail_sprite):
	set_snake(snake_obj,cells)
	snake_obj.update_tail_graphics()
	assert snake_obj.tail is getattr(snake_obj,tail_sprite)


@pytest.mark.parametrize('layout',TURN_LAYOUTS.keys())
def test_body_sprite_matches_the_turn(snake_obj,set_snake,mock_screen,layout):
	cells,sprite_name = TURN_LAYOUTS[layout]
	set_snake(snake_obj,cells)

	snake_obj.draw_snake()

	assert mock_screen.blit.call_count == len(cells)
	middle_sprite = mock_screen.blit.call_args_list[1].args[0]
	assert middle_sprite is getattr(snake_obj,sprite_name)


def test_draw_snake_places_blocks_on_the_grid(snake_obj,mock_screen):
	snake_obj.draw_snake()
	rects = [call.args[1] for call in mock_screen.blit.call_args_list]
	size = game_module.cell_size
	assert rects == [pygame.Rect(x * size,10 * size,size,size) for x in (5,4,3)]


def test_snake_needs_its_sprites(monkeypatch):
	def missing(path):
		raise game_module.ASSET_ERROR(path)
	monkeypatch.setattr(game_module,'load_image',missing)
	with pytest.raises(game_module.ASSET_ERROR):
		game_module.SNAKE()
