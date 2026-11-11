"""Pygame score bug and match timer rendering utilities.

The score bug draws the live score, team names, and piece badges in a compact HUD
layout suitable for overlaying on the pitch preview.
"""

from functools import lru_cache
from pathlib import Path

import pygame


Color = tuple[int, int, int]
PANEL_WHITE = (255, 255, 255)
TEXT_GREEN = (7, 82, 43)
TEXT_WHITE = (255, 255, 255)
SCORE_FONT_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "fonts"
    / "Barlow-Black.ttf"
)
TEAM_FONT_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "fonts"
    / "BarlowCondensed-Medium.ttf"
)


@lru_cache(maxsize=16)
def _score_font(size: int) -> pygame.font.Font:
    """Load or reuse the score font for a given size.

    Args:
        size: The requested font size in pixels.

    Returns:
        pygame.font.Font: A cached font instance configured with the score font.
    """
    return pygame.font.Font(str(SCORE_FONT_PATH), size)


@lru_cache(maxsize=16)
def _team_font(size: int) -> pygame.font.Font:
    """Load or reuse the team-label font for a given size.

    Args:
        size: The requested font size in pixels.

    Returns:
        pygame.font.Font: A cached font instance configured with the team label
        face.
    """
    return pygame.font.Font(str(TEAM_FONT_PATH), size)


def _render_tabular_text(font: pygame.font.Font, text: str) -> pygame.Surface:
    """Render text using a monospaced digit layout to keep numeric columns aligned.

    Args:
        font: The font used to render the text.
        text: The string to draw, typically a score or timer value.

    Returns:
        pygame.Surface: A surfaced text render sized so digits share a uniform
        tabular width.
    """
    digit_count = sum(character.isdigit() for character in text)
    cell_count = max(2, digit_count)
    cell_width = max(font.size(digit)[0] for digit in "0123456789")
    text_width = cell_width * cell_count + sum(
        font.size(character)[0]
        for character in text
        if not character.isdigit()
    )
    surface = pygame.Surface((text_width, font.get_height()), pygame.SRCALPHA)
    if digit_count == 1:
        glyph = font.render(text, True, TEXT_GREEN)
        surface.blit(glyph, ((surface.get_width() - glyph.get_width()) // 2, 0))
        return surface

    x = 0
    for character in text:
        glyph = font.render(character, True, TEXT_GREEN)
        character_width = cell_width if character.isdigit() else glyph.get_width()
        surface.blit(
            glyph,
            (
                x + (character_width - glyph.get_width()) // 2,
                (font.get_height() - glyph.get_height()) // 2,
            ),
        )
        x += character_width
    return surface


def _render_tabular_score(font: pygame.font.Font, score: int) -> pygame.Surface:
    """Render a numeric score using the tabular text layout.

    Args:
        font: The font used for the score glyphs.
        score: The integer score value to display.

    Returns:
        pygame.Surface: A rendered score surface with numerals aligned in a fixed
        width style.
    """
    return _render_tabular_text(font, str(score))


def _fit_text(text: str, font: pygame.font.Font, max_width: int) -> str:
    """Trim a team name to a maximum pixel width, appending an ellipsis when needed.

    Args:
        text: The original team label to fit.
        font: The font used to measure the label width.
        max_width: The largest allowed pixel width for the label.

    Returns:
        str: A shortened label that fits inside ``max_width`` while preserving the
        most relevant text.
    """
    if font.size(text)[0] <= max_width:
        return text

    fitted = text
    while fitted and font.size(f"{fitted}...")[0] > max_width:
        fitted = fitted[:-1]
    return f"{fitted}..." if fitted else ""


def draw_scorebug(
    surface: pygame.Surface,
    *,
    home_name: str,
    home_score: int,
    home_piece_color: Color,
    away_score: int,
    away_piece_color: Color,
    away_name: str,
    center_x: int,
    top: int,
    height: int,
) -> pygame.Rect:
    """Draw the match score bug and return the combined bounds of the HUD elements.

    Args:
        surface: The surface on which the score bug is rendered.
        home_name: Display name for the home team.
        home_score: Current home-team score value.
        home_piece_color: RGB color used for the home team's badge.
        away_score: Current away-team score value.
        away_piece_color: RGB color used for the away team's badge.
        away_name: Display name for the away team.
        center_x: Horizontal center used to position the pill within the surface.
        top: Top-most Y coordinate of the score bug.
        height: Height budget available for the score bug.

    Returns:
        pygame.Rect: The union rectangle covering the score pill, badges, and team
        labels. If the available space is too small, an empty rect is returned.
    """
    max_width = max(0, surface.get_width() - 48)
    if max_width < 112 or height < 16:
        return pygame.Rect(center_x, top, 0, 0)

    home_name = home_name.title()
    away_name = away_name.title()
    row_height = min(height, 38)
    padding_y = max(2, round(row_height * 0.16))
    content_height = row_height - padding_y * 2
    score_font = _score_font(max(12, min(28, round(content_height * 0.92))))
    team_font_size = max(12, round(score_font.get_height() * 0.82))
    team_font = _team_font(team_font_size)
    badge_size = max(14, min(24, content_height - 2))
    badge_radius = badge_size // 2
    badge_inner_radius = max(1, badge_radius - max(2, badge_size // 7))
    score_gap = max(6, round(row_height * 0.2))
    badge_gap = max(5, round(row_height * 0.16))

    home_score_surface = _render_tabular_score(score_font, home_score)
    away_score_surface = _render_tabular_score(score_font, away_score)
    dash_surface = team_font.render("-", True, TEXT_GREEN)

    pill_content_width = (
        home_score_surface.get_width()
        + away_score_surface.get_width()
        + dash_surface.get_width()
        + score_gap * 2
    )
    pill_padding_x = max(10, round(row_height * 0.32))
    pill_width = pill_content_width + pill_padding_x * 2
    fixed_width = pill_width + badge_size * 2 + badge_gap * 2
    if fixed_width > max_width:
        return pygame.Rect(center_x, top, 0, 0)

    side_gap = max(6, round(row_height * 0.16))
    side_width = max(0, (max_width - fixed_width - side_gap * 2) // 2)
    home_name = _fit_text(home_name, team_font, side_width)
    away_name = _fit_text(away_name, team_font, side_width)
    home_name_surface = team_font.render(home_name, True, TEXT_WHITE)
    away_name_surface = team_font.render(away_name, True, TEXT_WHITE)

    pill = pygame.Rect(
        center_x - pill_width // 2,
        top,
        pill_width,
        row_height,
    )
    pygame.draw.rect(
        surface,
        PANEL_WHITE,
        pill,
        border_radius=row_height // 2,
    )
    center_y = pill.centery

    def draw_piece_badge(color: Color, center: tuple[int, int]) -> pygame.Rect:
        pygame.draw.circle(surface, TEXT_GREEN, center, badge_radius)
        pygame.draw.circle(surface, color, center, badge_inner_radius)
        return pygame.Rect(
            center[0] - badge_radius,
            center[1] - badge_radius,
            badge_size,
            badge_size,
        )

    x = pill.centerx - pill_content_width // 2
    home_score_rect = home_score_surface.get_rect(midleft=(x, center_y))
    surface.blit(home_score_surface, home_score_rect)
    x = home_score_rect.right + score_gap

    dash_rect = dash_surface.get_rect(midleft=(x, center_y))
    surface.blit(dash_surface, dash_rect)
    x = dash_rect.right + score_gap

    away_score_rect = away_score_surface.get_rect(midleft=(x, center_y))
    surface.blit(away_score_surface, away_score_rect)
    home_badge_rect = draw_piece_badge(
        home_piece_color,
        (pill.left - badge_gap - badge_radius, center_y),
    )
    away_badge_rect = draw_piece_badge(
        away_piece_color,
        (pill.right + badge_gap + badge_radius, center_y),
    )

    left_name_rect = home_name_surface.get_rect(
        midright=(home_badge_rect.left - side_gap, center_y)
    )
    right_name_rect = away_name_surface.get_rect(
        midleft=(away_badge_rect.right + side_gap, center_y)
    )
    surface.blit(home_name_surface, left_name_rect)
    surface.blit(away_name_surface, right_name_rect)

    return (
        left_name_rect.union(home_badge_rect)
        .union(pill)
        .union(away_badge_rect)
        .union(right_name_rect)
    )


def draw_match_timer(
    surface: pygame.Surface,
    *,
    seconds_remaining: int,
    left: int,
    top: int,
    height: int,
) -> pygame.Rect:
    """Draw a padded countdown timer pill and return its rendered bounds.

    Args:
        surface: The surface on which the timer is drawn.
        seconds_remaining: The remaining match time, expressed in seconds.
        left: The horizontal pixel origin of the timer.
        top: The vertical pixel origin of the timer.
        height: The maximum height available for the timer pill.

    Returns:
        pygame.Rect: The bounding rectangle for the timer pill, or an empty rect
        when the requested space is too small or the pill would exceed the surface.
    """
    if height < 16:
        return pygame.Rect(left, top, 0, 0)

    row_height = min(height, 38)
    padding_y = max(2, round(row_height * 0.16))
    content_height = row_height - padding_y * 2
    timer_font = _score_font(max(12, min(28, round(content_height * 0.92))))
    minutes, seconds = divmod(max(0, seconds_remaining), 60)
    timer_surface = _render_tabular_text(
        timer_font,
        f"{minutes:02d}:{seconds:02d}",
    )
    padding_x = max(10, round(row_height * 0.32))
    pill = pygame.Rect(
        left,
        top,
        timer_surface.get_width() + padding_x * 2,
        row_height,
    )
    if pill.left < 0 or pill.right > surface.get_width():
        return pygame.Rect(left, top, 0, 0)

    pygame.draw.rect(
        surface,
        PANEL_WHITE,
        pill,
        border_radius=row_height // 2,
    )
    surface.blit(timer_surface, timer_surface.get_rect(center=pill.center))
    return pill
