import re

import pygame
import pytest
from conftest import ROOT

import snake as game_module

# --- images ---------------------------------------------------------------------------


def test_load_image_reads_a_real_sprite(real_loaders):
    image = real_loaders.image(str(ROOT / "Graphics" / "bomb.png"))
    assert image.get_size() == (40, 40)


def test_missing_image_raises_a_clear_error(real_loaders):
    with pytest.raises(game_module.AssetError, match=re.escape("nope.png")):
        real_loaders.image("Graphics/nope.png")


def test_corrupt_image_raises_asset_error(real_loaders, tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"this is not a png")
    with pytest.raises(game_module.AssetError, match=re.escape("broken.png")):
        real_loaders.image(str(broken))


# --- fonts ----------------------------------------------------------------------------


def test_load_font_reads_the_game_font(real_loaders):
    font = real_loaders.font(str(ROOT / "Font" / "PoetsenOne-Regular.ttf"), 25)
    assert font.render("1", True, (0, 0, 0)).get_width() > 0


def test_missing_font_raises_a_clear_error(real_loaders):
    with pytest.raises(game_module.AssetError, match=re.escape("missing.ttf")):
        real_loaders.font("Font/missing.ttf", 25)


# --- sounds ---------------------------------------------------------------------------


def test_load_sound_reads_a_real_sound(real_loaders):
    if not pygame.mixer.get_init():
        pytest.skip("no mixer available")
    sound = real_loaders.sound(str(ROOT / "Sound" / "explosion.wav"))
    assert not isinstance(sound, game_module.SilentSound)


def test_missing_sound_falls_back_to_silence_with_a_warning(real_loaders, capsys):
    sound = real_loaders.sound("Sound/nope.wav")

    assert isinstance(sound, game_module.SilentSound)
    sound.play()  # must not raise
    assert "nope.wav" in capsys.readouterr().out


def test_silent_sound_matches_the_sound_interface():
    assert game_module.SilentSound().play() is None


# --- startup fails fast on a missing sprite -------------------------------------------


def test_game_refuses_to_start_without_its_sprites(monkeypatch):
    def missing(path):
        raise game_module.AssetError(f'Could not load image "{path}"')

    monkeypatch.setattr(game_module, "load_image", missing)
    with pytest.raises(game_module.AssetError):
        game_module.Game()


def test_game_still_starts_with_silent_sounds(monkeypatch):
    monkeypatch.setattr(
        game_module, "load_sound", lambda path: game_module.SilentSound()
    )
    main = game_module.Game()
    main.snake.play_crunch_sound()  # no-ops instead of failing
    assert main.state == game_module.PLAYING


# --- pixel text -----------------------------------------------------------------------


def test_pixel_text_falls_back_to_scaled_builtin_font(monkeypatch):
    monkeypatch.setattr(game_module, "PIXEL_FONT_PATH", "Font/does_not_exist.ttf")
    text = game_module.PixelText(32, 16, 4)

    unscaled = pygame.font.Font(None, 16).render("HI", False, (255, 255, 255))
    rendered = text.render("HI", (255, 255, 255))

    assert text.scale == 4
    assert rendered.get_size() == (unscaled.get_width() * 4, unscaled.get_height() * 4)


def test_pixel_text_uses_the_pixel_font_unscaled_when_present(monkeypatch):
    monkeypatch.setattr(
        game_module, "PIXEL_FONT_PATH", str(ROOT / "Font" / "PoetsenOne-Regular.ttf")
    )
    text = game_module.PixelText(32, 16, 4)

    assert text.scale == 1
    assert text.render("HI", (255, 255, 255)).get_height() > 0
