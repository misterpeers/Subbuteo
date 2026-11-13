"""Rendering helpers for the Subbuteo simulator's start menu."""

from pathlib import Path

import pygame


BACKGROUND = (19, 31, 25)
BUTTON_GREEN = (27, 145, 75)
BUTTON_HOVER_GREEN = (35, 162, 85)
TEXT_COLOR = (242, 245, 229)
FONT_PATH = Path(__file__).resolve().parent / "assets" / "fonts" / "Barlow-Black.ttf"


def start_button_rect(surface: pygame.Surface) -> pygame.Rect:
    """Return the centered start-button bounds for the current surface."""
    width = min(280, max(180, surface.get_width() // 3))
    return pygame.Rect(
        (surface.get_width() - width) // 2,
        surface.get_height() // 2 + 24,
        width,
        60,
    )


def draw_menu(
    surface: pygame.Surface,
    mouse_position: tuple[int, int] | None = None,
) -> pygame.Rect:
    """Draw the title screen and return the start-button bounds."""
    surface.fill(BACKGROUND)
    title_font = pygame.font.Font(str(FONT_PATH), min(56, max(30, surface.get_width() // 18)))
    subtitle_font = pygame.font.Font(None, 26)
    button_font = pygame.font.Font(str(FONT_PATH), 28)
    title = title_font.render("SUBBUTEO SIMULATOR", True, TEXT_COLOR)
    subtitle = subtitle_font.render("Physics test match", True, TEXT_COLOR)
    surface.blit(title, title.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 - 100)))
    surface.blit(
        subtitle,
        subtitle.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 - 48)),
    )

    button = start_button_rect(surface)
    hovered = mouse_position is not None and button.collidepoint(mouse_position)
    color = BUTTON_HOVER_GREEN if hovered else BUTTON_GREEN
    pygame.draw.rect(surface, color, button, border_radius=10)
    label = button_font.render("START", True, TEXT_COLOR)
    surface.blit(label, label.get_rect(center=button.center))
    return button
