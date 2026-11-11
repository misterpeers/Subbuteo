"""Rendering helpers for the Subbuteo pitch design preview.

This module defines the board geometry, turf pattern, and pitch markings used by
both the standalone pitch preview and match setup displays.
"""

import pygame


PITCH_LENGTH_MM = 1200
PITCH_WIDTH_MM = 800
SHOOTING_AREA_DEPTH_MM = 280
SPOT_RADIUS_MM = 6
PENALTY_SPOT_DEPTH_MM = 90
PENALTY_AREA_WIDTH_MM = 390
PENALTY_AREA_DEPTH_MM = 150
GOAL_AREA_WIDTH_MM = 240
GOAL_AREA_DEPTH_MM = 60
FRAME_BORDER_MM = 80

BACKGROUND = (19, 31, 25)
FRAME_GREEN = (7, 82, 43)
GRASS_LIGHT = (27, 145, 75)
GRASS_DARK = (19, 126, 64)
MARKING = (242, 245, 229)
WINDOW_MARGIN_PX = 24


def _dashed_line(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    start: tuple[int, int],
    end: tuple[int, int],
    dash_length: int,
    gap_length: int,
    width: int,
) -> None:
    """Draw a dashed line segment between two points.

    Args:
        surface: The surface to draw on.
        color: RGB tuple used for the dash stroke color.
        start: The starting pixel coordinate of the line as ``(x, y)``.
        end: The ending pixel coordinate of the line as ``(x, y)``.
        dash_length: The visible length of each dash in pixels.
        gap_length: The gap between consecutive dashes in pixels.
        width: The stroke thickness in pixels.

    Returns:
        None. The dashed line is rendered directly to the supplied surface.
    """
    start_vector = pygame.Vector2(start)
    end_vector = pygame.Vector2(end)
    segment = end_vector - start_vector
    distance = segment.length()
    if distance == 0:
        return

    direction = segment.normalize()
    position = 0.0
    while position < distance:
        end_position = min(position + dash_length, distance)
        pygame.draw.line(
            surface,
            color,
            start_vector + direction * position,
            start_vector + direction * end_position,
            width,
        )
        position = end_position + gap_length


def draw_pitch(surface: pygame.Surface) -> pygame.Rect:
    """Render the empty Subbuteo pitch and return its field rectangle.

    Args:
        surface: The destination surface used for the pitch preview.

    Returns:
        pygame.Rect: The rectangle describing the playable field area within the
        surface, after scaling to fit the current window size.
    """
    surface.fill(BACKGROUND)
    surface_width, surface_height = surface.get_size()
    scale = min(
        (surface_width - 2 * WINDOW_MARGIN_PX)
        / (PITCH_LENGTH_MM + 2 * FRAME_BORDER_MM),
        (surface_height - 2 * WINDOW_MARGIN_PX)
        / (PITCH_WIDTH_MM + 2 * FRAME_BORDER_MM),
    )

    field_width = round(PITCH_LENGTH_MM * scale)
    field_height = round(PITCH_WIDTH_MM * scale)
    frame_width = round(FRAME_BORDER_MM * scale)
    board_width = field_width + frame_width * 2
    board_height = field_height + frame_width * 2
    board = pygame.Rect(
        (surface_width - board_width) // 2,
        (surface_height - board_height) // 2,
        board_width,
        board_height,
    )
    field = pygame.Rect(
        board.left + frame_width,
        board.top + frame_width,
        field_width,
        field_height,
    )

    pygame.draw.rect(
        surface,
        FRAME_GREEN,
        board,
        border_radius=max(2, frame_width // 5),
    )

    shooting_stripe_boundaries = [
        SHOOTING_AREA_DEPTH_MM * stripe / 3
        for stripe in range(4)
    ]
    middle_length_mm = PITCH_LENGTH_MM - 2 * SHOOTING_AREA_DEPTH_MM
    shooting_stripe_boundaries.extend(
        SHOOTING_AREA_DEPTH_MM + middle_length_mm * stripe / 6
        for stripe in range(1, 7)
    )
    shooting_stripe_boundaries.extend(
        PITCH_LENGTH_MM
        - SHOOTING_AREA_DEPTH_MM
        + SHOOTING_AREA_DEPTH_MM * stripe / 3
        for stripe in range(1, 4)
    )

    for stripe, (start_mm, end_mm) in enumerate(
        zip(shooting_stripe_boundaries, shooting_stripe_boundaries[1:])
    ):
        x_start = field.left + round(start_mm * scale)
        x_end = field.left + round(end_mm * scale)
        color = GRASS_LIGHT if stripe % 2 == 0 else GRASS_DARK
        pygame.draw.rect(
            surface,
            color,
            pygame.Rect(x_start, field.top, x_end - x_start, field.height),
        )

    line_width = max(2, round(2.5 * scale))
    center_y = field.centery
    goal_half_width = round(120 * scale / 2)

    pygame.draw.line(
        surface,
        MARKING,
        field.topleft,
        (field.left, center_y - goal_half_width),
        line_width,
    )
    pygame.draw.line(
        surface,
        MARKING,
        (field.left, center_y + goal_half_width),
        field.bottomleft,
        line_width,
    )
    pygame.draw.line(
        surface,
        MARKING,
        field.topright,
        (field.right, center_y - goal_half_width),
        line_width,
    )
    pygame.draw.line(
        surface,
        MARKING,
        (field.right, center_y + goal_half_width),
        field.bottomright,
        line_width,
    )
    pygame.draw.line(surface, MARKING, field.topleft, field.topright, line_width)
    pygame.draw.line(surface, MARKING, field.bottomleft, field.bottomright, line_width)

    pygame.draw.line(
        surface,
        MARKING,
        (field.centerx, field.top),
        (field.centerx, field.bottom),
        line_width,
    )
    pygame.draw.circle(
        surface,
        MARKING,
        field.center,
        round(120 * scale),
        line_width,
    )
    spot_radius = max(3, round(SPOT_RADIUS_MM * scale))
    pygame.draw.circle(surface, MARKING, field.center, spot_radius)

    for side in (0, 1):
        goal_line_x = field.left if side == 0 else field.right
        inward = 1 if side == 0 else -1

        for box_width_mm, box_depth_mm in (
            (PENALTY_AREA_WIDTH_MM, PENALTY_AREA_DEPTH_MM),
            (GOAL_AREA_WIDTH_MM, GOAL_AREA_DEPTH_MM),
        ):
            box_top = center_y - round(box_width_mm * scale / 2)
            box_bottom = center_y + round(box_width_mm * scale / 2)
            inner_x = goal_line_x + inward * round(box_depth_mm * scale)
            pygame.draw.line(
                surface,
                MARKING,
                (goal_line_x, box_top),
                (inner_x, box_top),
                line_width,
            )
            pygame.draw.line(
                surface,
                MARKING,
                (inner_x, box_top),
                (inner_x, box_bottom),
                line_width,
            )
            pygame.draw.line(
                surface,
                MARKING,
                (inner_x, box_bottom),
                (goal_line_x, box_bottom),
                line_width,
            )
            if box_depth_mm == PENALTY_AREA_DEPTH_MM:
                penalty_spot = (
                    goal_line_x + inward * round(PENALTY_SPOT_DEPTH_MM * scale),
                    center_y,
                )
                pygame.draw.circle(surface, MARKING, penalty_spot, spot_radius)

        shooting_line_x = goal_line_x + inward * round(SHOOTING_AREA_DEPTH_MM * scale)
        pygame.draw.line(
            surface,
            MARKING,
            (shooting_line_x, field.top),
            (shooting_line_x, field.bottom),
            line_width,
        )

        goal_depth = round(60 * scale)
        goal_left = goal_line_x - goal_depth if side == 0 else goal_line_x
        goal = pygame.Rect(
            goal_left,
            center_y - goal_half_width,
            goal_depth,
            goal_half_width * 2,
        )
        dash_length = max(3, round(8 * scale))
        gap_length = max(2, round(5 * scale))
        corners = (
            (goal.topleft, goal.topright),
            (goal.topright, goal.bottomright),
            (goal.bottomright, goal.bottomleft),
            (goal.bottomleft, goal.topleft),
        )
        for start, end in corners:
            _dashed_line(
                surface,
                MARKING,
                start,
                end,
                dash_length,
                gap_length,
                line_width,
            )

    return field
