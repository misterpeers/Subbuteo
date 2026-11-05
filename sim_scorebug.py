import pygame


Color = tuple[int, int, int]
PANEL_WHITE = (255, 255, 255)
TEXT_GREEN = (7, 82, 43)
TEXT_WHITE = (255, 255, 255)


def _fit_text(text: str, font: pygame.font.Font, max_width: int) -> str:
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
    max_width = max(0, surface.get_width() - 48)
    if max_width < 112 or height < 16:
        return pygame.Rect(center_x, top, 0, 0)

    home_name = home_name.title()
    away_name = away_name.title()
    row_height = min(height, 30)
    padding_y = max(2, (row_height - 22) // 2)
    content_height = row_height - padding_y * 2
    score_font = pygame.font.SysFont(
        "Segoe UI",
        max(15, min(22, round(content_height * 0.72))),
        bold=True,
    )
    team_font_size = max(10, round(score_font.get_height() * 0.62))
    team_font = pygame.font.SysFont("Segoe UI", team_font_size, bold=True)
    dash_font = pygame.font.SysFont("Segoe UI", team_font_size, bold=True)
    badge_size = max(14, min(18, content_height - 2))
    badge_radius = badge_size // 2
    badge_inner_radius = max(1, badge_radius - max(2, badge_size // 7))
    gap = 5

    home_score_surface = score_font.render(str(home_score), True, TEXT_GREEN)
    away_score_surface = score_font.render(str(away_score), True, TEXT_GREEN)
    dash_surface = dash_font.render("-", True, TEXT_GREEN)

    pill_content_width = (
        badge_size * 2
        + home_score_surface.get_width()
        + away_score_surface.get_width()
        + dash_surface.get_width()
        + gap * 5
    )
    pill_padding_x = 8
    pill_width = pill_content_width + pill_padding_x * 2
    if pill_width > max_width:
        return pygame.Rect(center_x, top, 0, 0)

    side_gap = max(6, gap)
    side_width = max(0, (max_width - pill_width - side_gap * 2) // 2)
    team_font_size = min(team_font_size, max(10, row_height - 4))
    team_font = pygame.font.SysFont("Segoe UI", team_font_size, bold=True)
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

    def draw_piece_badge(color: Color, badge_x: int) -> None:
        center = (badge_x + badge_radius, center_y)
        pygame.draw.circle(surface, TEXT_GREEN, center, badge_radius)
        pygame.draw.circle(surface, color, center, badge_inner_radius)

    x = pill.left + pill_padding_x
    draw_piece_badge(home_piece_color, x)
    x += badge_size + gap

    home_score_rect = home_score_surface.get_rect(midleft=(x, center_y))
    surface.blit(home_score_surface, home_score_rect)
    x = home_score_rect.right + gap

    dash_rect = dash_surface.get_rect(midleft=(x, center_y))
    surface.blit(dash_surface, dash_rect)
    x = dash_rect.right + gap

    away_score_rect = away_score_surface.get_rect(midleft=(x, center_y))
    surface.blit(away_score_surface, away_score_rect)
    x = away_score_rect.right + gap
    draw_piece_badge(away_piece_color, x)

    left_name_rect = home_name_surface.get_rect(
        midright=(pill.left - side_gap, center_y)
    )
    right_name_rect = away_name_surface.get_rect(
        midleft=(pill.right + side_gap, center_y)
    )
    surface.blit(home_name_surface, left_name_rect)
    surface.blit(away_name_surface, right_name_rect)

    return left_name_rect.union(pill).union(right_name_rect)
