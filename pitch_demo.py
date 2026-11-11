"""Pitch preview demo showing both the empty board and live match setup view.

The module renders a full pitch layout, overlays a score bug, and lets the user
switch between the stadium design preview and a mock match setup composition.
"""

import pygame

from sim_pitch import (
    FRAME_BORDER_MM,
    MARKING,
    PITCH_LENGTH_MM,
    SHOOTING_AREA_DEPTH_MM,
    draw_pitch,
)
from sim_scorebug import draw_match_timer, draw_scorebug

PLAYER_PIECE_DIAMETER_MM = 21
PLAYER_PIECE_INNER_DIAMETER_MM = 16
GOALKEEPER_THICKNESS_MM = 8
GOALKEEPER_WIDTH_MM = 21
PIECE_BORDER_MM = (PLAYER_PIECE_DIAMETER_MM - PLAYER_PIECE_INNER_DIAMETER_MM) / 2
BALL_RADIUS_MM = 11

HOME_TEAM = (57, 126, 224)
HOME_PIECE_BORDER = (245, 245, 245)
AWAY_TEAM = (218, 74, 62)
AWAY_PIECE_BORDER = (20, 20, 20)
PIECE_OUTLINE = (24, 35, 29)
BALL_COLOR = (248, 248, 240)

HOME_SCORE = 2
AWAY_SCORE = 1
HOME_NAME = "Team A"
AWAY_NAME = "Team B"

WINDOW_SIZE = (1280, 900)
MIN_WINDOW_SIZE = (640, 480)


def draw_match_setup(surface: pygame.Surface) -> pygame.Rect:
    """Draw the match setup view and return the field bounds for the pitch.

    Args:
        surface: The Pygame surface that receives the rendered pitch and pieces.

    Returns:
        pygame.Rect: The rectangle describing the playing field location inside the
        current surface after scaling for the window size.
    """
    field = draw_pitch(surface)
    scale = field.width / PITCH_LENGTH_MM
    piece_outer_radius = max(1, round(PLAYER_PIECE_DIAMETER_MM * scale / 2))
    piece_inner_radius = max(1, round(PLAYER_PIECE_INNER_DIAMETER_MM * scale / 2))
    border_width = max(1, round(PIECE_BORDER_MM * scale))

    def pitch_point(x: float, y: float) -> tuple[int, int]:
        """Convert normalized field coordinates to pixel coordinates.

        Args:
            x: Horizontal pitch position normalized from 0.0 to 1.0.
            y: Vertical pitch position normalized from 0.0 to 1.0.

        Returns:
            tuple[int, int]: The pixel coordinate pair in the surface space.
        """
        return (
            field.left + round(x * field.width),
            field.top + round(y * field.height),
        )

    def draw_piece(
        position: tuple[float, float],
        fill_color: tuple[int, int, int],
        border_color: tuple[int, int, int],
    ) -> None:
        """Render one player piece on the pitch.

        Args:
            position: Normalized ``(x, y)`` position on the field.
            fill_color: RGB color used for the central body of the piece.
            border_color: RGB color used for the outer ring.

        Returns:
            None. The figure is drawn directly onto the provided surface.
        """
        center = pitch_point(*position)
        pygame.draw.circle(
            surface,
            border_color,
            center,
            piece_outer_radius,
        )
        pygame.draw.circle(surface, fill_color, center, piece_inner_radius)

    def draw_goalkeeper(
        x: float,
        fill_color: tuple[int, int, int],
        border_color: tuple[int, int, int],
    ) -> None:
        """Render a goalkeeper-shaped rod piece at the goal line.

        Args:
            x: Normalized horizontal position along the pitch.
            fill_color: RGB color used for the keeper body.
            border_color: RGB color used for the keeper outline.

        Returns:
            None. The goalkeeper is drawn to the target surface in place.
        """
        center = pitch_point(x, 0.5)
        thickness = max(1, round(GOALKEEPER_THICKNESS_MM * scale))
        width = max(1, round(GOALKEEPER_WIDTH_MM * scale))
        keeper = pygame.Rect(
            center[0] - thickness // 2,
            center[1] - width // 2,
            thickness,
            width,
        )
        pygame.draw.rect(surface, border_color, keeper)
        keeper_inner = keeper.inflate(-border_width * 2, -border_width * 2)
        if keeper_inner.width > 0 and keeper_inner.height > 0:
            pygame.draw.rect(surface, fill_color, keeper_inner)

    shooting_line_offset = (
        SHOOTING_AREA_DEPTH_MM + PLAYER_PIECE_DIAMETER_MM / 2
    ) / PITCH_LENGTH_MM
    for index in range(10):
        y = 0.10 + index * (0.80 / 9)
        draw_piece(
            (shooting_line_offset, y),
            HOME_TEAM,
            HOME_PIECE_BORDER,
        )
        draw_piece(
            (1 - shooting_line_offset, y),
            AWAY_TEAM,
            AWAY_PIECE_BORDER,
        )

    goalkeeper_offset = 22 / PITCH_LENGTH_MM
    draw_goalkeeper(goalkeeper_offset, HOME_TEAM, HOME_PIECE_BORDER)
    draw_goalkeeper(1 - goalkeeper_offset, AWAY_TEAM, AWAY_PIECE_BORDER)

    ball_center = pitch_point(0.5, 0.5)
    ball_radius = max(3, round(BALL_RADIUS_MM * scale))
    ball_border_width = max(1, round(scale))
    pygame.draw.circle(
        surface,
        PIECE_OUTLINE,
        ball_center,
        ball_radius + ball_border_width,
    )
    pygame.draw.circle(surface, BALL_COLOR, ball_center, ball_radius)

    return field


def draw_mode_hint(surface: pygame.Surface) -> None:
    """Render a small hint telling the user how to switch views.

    Args:
        surface: The surface on which the hint should be drawn.

    Returns:
        None. The preview text is painted directly to the given surface.
    """
    hint_font = pygame.font.Font(None, 18)
    hint = hint_font.render("Press M to switch between views", True, MARKING)
    surface.blit(
        hint,
        hint.get_rect(center=(surface.get_width() // 2, surface.get_height() - 12)),
    )


def draw_match_scorebug(surface: pygame.Surface, field: pygame.Rect) -> None:
    """Overlay the match timer and score bug on the active pitch view.

    Args:
        surface: The window surface to update.
        field: The pitch field rectangle used to place the score bug relative to the
            board.

    Returns:
        None. The timer and score elements are drawn directly onto the surface.
    """
    scale = field.width / PITCH_LENGTH_MM
    frame_height = round(FRAME_BORDER_MM * scale)
    board_top = field.top - frame_height
    scorebug_height = min(38, max(16, frame_height - 6))
    scorebug_top = board_top + (frame_height - scorebug_height) // 2

    draw_match_timer(
        surface,
        seconds_remaining=15 * 60,
        left=field.left,
        top=scorebug_top,
        height=scorebug_height,
    )
    draw_scorebug(
        surface,
        home_name=HOME_NAME,
        home_score=HOME_SCORE,
        home_piece_color=HOME_TEAM,
        away_score=AWAY_SCORE,
        away_piece_color=AWAY_TEAM,
        away_name=AWAY_NAME,
        center_x=field.centerx,
        top=scorebug_top,
        height=scorebug_height,
    )


def main() -> None:
    """Run the pitch preview demo loop and handle user interaction.

    Args:
        None.

    Returns:
        None. The function manages the Pygame event loop until the window closes.
    """
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption("Subbuteo Pitch - Design Preview")
    clock = pygame.time.Clock()
    running = True
    show_match_setup = False

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                show_match_setup = not show_match_setup
                view_name = "Match Setup" if show_match_setup else "Design Preview"
                pygame.display.set_caption(f"Subbuteo Pitch - {view_name}")
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (
                        max(event.w, MIN_WINDOW_SIZE[0]),
                        max(event.h, MIN_WINDOW_SIZE[1]),
                    ),
                    pygame.RESIZABLE,
                )

        if show_match_setup:
            field = draw_match_setup(screen)
            draw_match_scorebug(screen, field)
        else:
            draw_pitch(screen)
        draw_mode_hint(screen)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
