import pygame
import pytest
from unittest.mock import MagicMock

import snake as game_module
from snake import PLAYING,PAUSED,RESUMING,EXPLODING,GAME_OVER

BUTTON_RECT = pygame.Rect(100,50,40,40)
NORMAL_COLOR = (167,209,61)
HOVER_COLOR = (187,229,81)


class DummyButton(game_module.BUTTON):
	def get_icon(self):
		return pygame.Surface((10,10),pygame.SRCALPHA)


def mouse_event(pos,button = 1,kind = pygame.MOUSEBUTTONDOWN):
	return pygame.event.Event(kind,pos = pos,button = button)


# --- BUTTON ----------------------------------------------------------------------------------

def test_button_is_abstract():
	with pytest.raises(TypeError):
		game_module.BUTTON(BUTTON_RECT,lambda: None)


CLICKS = {
	# name: (event, enabled, callback expected)
	'left_click_inside': (mouse_event((110,60)),True,True),
	'left_click_top_left_corner': (mouse_event((100,50)),True,True),
	'left_click_outside': (mouse_event((99,60)),True,False),
	'left_click_just_past_the_edge': (mouse_event((140,60)),True,False),
	'right_click_inside': (mouse_event((110,60),button = 3),True,False),
	'middle_click_inside': (mouse_event((110,60),button = 2),True,False),
	'scroll_wheel_inside': (mouse_event((110,60),button = 4),True,False),
	'mouse_release_inside': (mouse_event((110,60),kind = pygame.MOUSEBUTTONUP),True,False),
	'key_press': (pygame.event.Event(pygame.KEYDOWN,key = pygame.K_p),True,False),
	'click_while_disabled': (mouse_event((110,60)),False,False),
}


@pytest.mark.parametrize('name',CLICKS.keys())
def test_button_click_handling(name):
	event,enabled,expect_call = CLICKS[name]
	callback = MagicMock()
	button = DummyButton(BUTTON_RECT,callback,lambda: enabled)

	handled = button.handle_event(event)

	assert handled is expect_call
	assert callback.called is expect_call


def test_button_is_enabled_by_default():
	callback = MagicMock()
	assert DummyButton(BUTTON_RECT,callback).handle_event(mouse_event((110,60))) is True


@pytest.mark.parametrize('mouse_pos,color',[((110,60),HOVER_COLOR),((300,300),NORMAL_COLOR)],ids = ['hovered','not_hovered'])
def test_button_highlights_on_hover(monkeypatch,mouse_pos,color):
	monkeypatch.setattr(pygame.mouse,'get_pos',lambda: mouse_pos)
	game_module.screen.fill((0,0,0))

	DummyButton(BUTTON_RECT,lambda: None).draw()

	# a pixel inside the border, away from the centred icon
	assert tuple(game_module.screen.get_at((104,54)))[:3] == color


def test_disabled_button_does_not_highlight(monkeypatch):
	monkeypatch.setattr(pygame.mouse,'get_pos',lambda: (110,60))
	game_module.screen.fill((0,0,0))
	DummyButton(BUTTON_RECT,lambda: None,lambda: False).draw()
	assert tuple(game_module.screen.get_at((104,54)))[:3] == NORMAL_COLOR


# --- PAUSE_BUTTON ----------------------------------------------------------------------------

def test_pause_button_sits_on_the_top_right_tile(game):
	size = game_module.cell_size
	assert game.pause_button.rect == pygame.Rect((game_module.cell_number - 1) * size,0,size,size)


def test_pause_button_rect_matches_the_blocked_tile(game):
	x,y = next(iter(game.blocked_cells))
	size = game_module.cell_size
	assert game.pause_button.rect.topleft == (x * size,y * size)


@pytest.mark.parametrize('state,expect_play_icon',[
	(PLAYING,False),(PAUSED,True),(RESUMING,False),(EXPLODING,False),(GAME_OVER,False),
])
def test_icon_reflects_the_game_state(game,state,expect_play_icon):
	game.state = state
	button = game.pause_button
	expected = button.play_icon if expect_play_icon else button.pause_icon
	assert button.get_icon() is expected


def test_icons_are_scaled_to_fit_inside_the_tile(game):
	inner = game_module.cell_size - 12
	assert game.pause_button.pause_icon.get_size() == (inner,inner)
	assert game.pause_button.play_icon.get_size() == (inner,inner)


@pytest.mark.parametrize('state,clickable',[
	(PLAYING,True),(PAUSED,True),(RESUMING,True),(EXPLODING,False),(GAME_OVER,False),
])
def test_button_is_clickable_only_in_pausable_states(game,state,clickable):
	game.state = state
	assert game.pause_button.is_enabled() is clickable


@pytest.mark.parametrize('pos,inside',[
	((760,0),True),((799,39),True),((780,20),True),
	((759,20),False),((780,40),False),((0,0),False),
])
def test_pause_button_hit_area(game,pos,inside):
	handled = game.pause_button.handle_event(mouse_event(pos))
	assert handled is inside
	assert (game.state == PAUSED) is inside


@pytest.mark.parametrize('state',[EXPLODING,GAME_OVER])
def test_clicking_does_nothing_while_exploding_or_game_over(game,state):
	game.state = state
	game.pause_button.handle_event(mouse_event((780,20)))
	assert game.state == state


def test_two_clicks_pause_then_start_the_countdown(game):
	game.pause_button.handle_event(mouse_event((780,20)))
	game.pause_button.handle_event(mouse_event((780,20)))
	assert game.state == RESUMING
