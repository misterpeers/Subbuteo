"""Interactive, untimed physics demo using the headless physics engine."""

import pygame

from sim_menu import draw_menu
from sim_physics import (
    AWAY,
    BALL_RADIUS_MM,
    HOME,
    PIECE_RADIUS_MM,
    PITCH_WIDTH_MM,
    PhysicsWorld,
    Vector2,
)
from sim_pitch import (
    FRAME_BORDER_MM,
    PITCH_LENGTH_MM as RENDER_PITCH_LENGTH_MM,
    draw_pitch,
)
from sim_scorebug import draw_scorebug


WINDOW_SIZE = (1280, 900)
MIN_WINDOW_SIZE = (640, 480)
GOAL_RESET_TIMEOUT_SECONDS = 4.0

HOME_COLOR = (57, 126, 224)
HOME_BORDER = (245, 245, 245)
AWAY_COLOR = (218, 74, 62)
AWAY_BORDER = (20, 20, 20)
PIECE_OUTLINE = (24, 35, 29)
BALL_COLOR = (248, 248, 240)
BUTTON_GREEN = (27, 145, 75)
BUTTON_ACTIVE_GREEN = (35, 162, 85)
TEXT_COLOR = (242, 245, 229)


def _pitch_point(field: pygame.Rect, position: Vector2) -> tuple[int, int]:
    """Convert a normalized physics position to a screen coordinate."""
    return (
        field.left + round(position.x * field.width),
        field.top + round(position.y * field.height),
    )


def _draw_world(
    surface: pygame.Surface,
    field: pygame.Rect,
    world: PhysicsWorld,
) -> None:
    """Render the physical pieces and ball on the pitch."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    piece_radius = max(2, round(PIECE_RADIUS_MM * scale))
    for piece in world.pieces:
        center = _pitch_point(field, piece.position)
        fill = HOME_COLOR if piece.team == HOME else AWAY_COLOR
        border = HOME_BORDER if piece.team == HOME else AWAY_BORDER
        if piece.kind == "goalkeeper":
            keeper_width = max(3, round(21 * scale))
            keeper_height = max(3, round(8 * scale))
            rect = pygame.Rect(0, 0, keeper_height, keeper_width)
            rect.center = center
            pygame.draw.rect(surface, border, rect)
            inner = rect.inflate(-max(1, round(5 * scale)), -max(1, round(5 * scale)))
            if inner.width > 0 and inner.height > 0:
                pygame.draw.rect(surface, fill, inner)
        else:
            pygame.draw.circle(surface, PIECE_OUTLINE, center, piece_radius + 1)
            pygame.draw.circle(surface, border, center, piece_radius)
            pygame.draw.circle(
                surface,
                fill,
                center,
                max(1, round(piece_radius * 16 / 21)),
            )

    ball_center = _pitch_point(field, world.ball.position)
    ball_radius = max(3, round(BALL_RADIUS_MM * scale))
    pygame.draw.circle(surface, PIECE_OUTLINE, ball_center, ball_radius + 1)
    pygame.draw.circle(surface, BALL_COLOR, ball_center, ball_radius)


def _draw_scorebug(
    surface: pygame.Surface,
    field: pygame.Rect,
    world: PhysicsWorld,
) -> None:
    """Render the score in the top frame around the pitch."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    frame_height = round(FRAME_BORDER_MM * scale)
    board_top = field.top - frame_height
    height = min(38, max(16, frame_height - 6))
    top = board_top + (frame_height - height) // 2
    draw_scorebug(
        surface,
        home_name="Team A",
        home_score=world.home_score,
        home_piece_color=HOME_COLOR,
        away_score=world.away_score,
        away_piece_color=AWAY_COLOR,
        away_name="Team B",
        center_x=field.centerx,
        top=top,
        height=height,
    )


def _draw_controls_hint(surface: pygame.Surface, free_movement: bool) -> None:
    """Render a concise hint for the active piece-control mode."""
    font = pygame.font.Font(None, 18)
    if free_movement:
        message = "Drag field pieces to reposition  |  Esc: quit"
    else:
        message = "Drag a piece back, then release to flick  |  Esc: quit"
    hint = font.render(message, True, TEXT_COLOR)
    surface.blit(
        hint,
        hint.get_rect(
            center=(surface.get_width() // 2, surface.get_height() - 12)
        ),
    )


def _control_button_rects(field: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect]:
    """Return the reset and free-movement button bounds in the lower frame."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    frame_height = round(FRAME_BORDER_MM * scale)
    button_height = min(36, max(24, frame_height - 8))
    reset_width = 150
    movement_width = 220
    gap = 12
    total_width = reset_width + movement_width + gap
    left = field.centerx - total_width // 2
    top = field.bottom + (frame_height - button_height) // 2
    return (
        pygame.Rect(left, top, reset_width, button_height),
        pygame.Rect(left + reset_width + gap, top, movement_width, button_height),
    )


def _draw_controls(
    surface: pygame.Surface,
    field: pygame.Rect,
    free_movement: bool,
) -> tuple[pygame.Rect, pygame.Rect]:
    """Draw the reset and free-movement controls and return their bounds."""
    reset_rect, movement_rect = _control_button_rects(field)
    pygame.draw.rect(
        surface,
        BUTTON_GREEN,
        reset_rect,
        border_radius=reset_rect.height // 2,
    )
    pygame.draw.rect(
        surface,
        BUTTON_ACTIVE_GREEN if free_movement else BUTTON_GREEN,
        movement_rect,
        border_radius=movement_rect.height // 2,
    )
    font_size = max(16, min(22, reset_rect.height - 4))
    font = pygame.font.Font(None, font_size)
    reset_label = font.render("RESET PIECES", True, TEXT_COLOR)
    movement_label = font.render(
        f"FREE MOVEMENT: {'ON' if free_movement else 'OFF'}",
        True,
        TEXT_COLOR,
    )
    surface.blit(reset_label, reset_label.get_rect(center=reset_rect.center))
    surface.blit(
        movement_label,
        movement_label.get_rect(center=movement_rect.center),
    )
    return reset_rect, movement_rect


def _piece_at(
    world: PhysicsWorld,
    field: pygame.Rect,
    mouse_position: tuple[int, int],
) -> str | None:
    """Return the movable field piece under the mouse, if there is one."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    hit_radius = max(8, round((PIECE_RADIUS_MM + 4) * scale))
    mouse = pygame.Vector2(mouse_position)
    for piece in reversed(world.pieces):
        if not piece.movable:
            continue
        if mouse.distance_to(_pitch_point(field, piece.position)) <= hit_radius:
            return piece.body_id
    return None


def _move_piece_to_cursor(
    world: PhysicsWorld,
    field: pygame.Rect,
    piece_id: str,
    mouse_position: tuple[int, int],
) -> None:
    """Move a field piece to the cursor while keeping it inside the pitch."""
    piece = next(body for body in world.pieces if body.body_id == piece_id)
    x = (mouse_position[0] - field.left) / field.width
    y = (mouse_position[1] - field.top) / field.height
    radius_x = piece.radius_mm / RENDER_PITCH_LENGTH_MM
    radius_y = piece.radius_mm / PITCH_WIDTH_MM
    piece.position = Vector2(
        min(1.0 - radius_x, max(radius_x, x)),
        min(1.0 - radius_y, max(radius_y, y)),
    )
    piece.velocity = Vector2(0.0, 0.0)


def _draw_flick_aim(
    surface: pygame.Surface,
    field: pygame.Rect,
    world: PhysicsWorld,
    piece_id: str,
    mouse_position: tuple[int, int],
) -> None:
    """Show the direction and approximate strength of the pending flick."""
    piece = next(body for body in world.pieces if body.body_id == piece_id)
    center = pygame.Vector2(_pitch_point(field, piece.position))
    pull = pygame.Vector2(mouse_position) - center
    end = center - pull
    if pull.length() < 3:
        return
    pygame.draw.line(surface, TEXT_COLOR, center, end, 3)
    direction = (end - center).normalize()
    left = end - direction.rotate(145) * 12
    right = end - direction.rotate(-145) * 12
    pygame.draw.polygon(surface, TEXT_COLOR, (end, left, right))


def main() -> None:
    """Run the menu and untimed interactive physics demo."""
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption("Subbuteo Physics Demo")
    clock = pygame.time.Clock()
    mode = "menu"
    world: PhysicsWorld | None = None
    goal_reset_elapsed: float | None = None
    dragging_piece: str | None = None
    dragging_for_free_movement = False
    free_movement = False
    drag_mouse_position = (0, 0)

    running = True
    while running:
        elapsed = clock.tick(60) / 1000.0
        mouse_position = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (
                        max(event.w, MIN_WINDOW_SIZE[0]),
                        max(event.h, MIN_WINDOW_SIZE[1]),
                    ),
                    pygame.RESIZABLE,
                )
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if mode == "menu":
                    button = draw_menu(screen, event.pos)
                    if button.collidepoint(event.pos):
                        world = PhysicsWorld.demo_match()
                        free_movement = False
                        goal_reset_elapsed = None
                        mode = "playing"
                elif mode == "playing" and world is not None:
                    field = draw_pitch(screen)
                    reset_rect, movement_rect = _control_button_rects(field)
                    if reset_rect.collidepoint(event.pos):
                        world.reset_pieces_and_ball()
                    elif movement_rect.collidepoint(event.pos):
                        free_movement = not free_movement
                    else:
                        dragging_piece = _piece_at(world, field, event.pos)
                        dragging_for_free_movement = free_movement
                        drag_mouse_position = event.pos
            elif event.type == pygame.MOUSEMOTION:
                drag_mouse_position = event.pos
                if (
                    mode == "playing"
                    and world is not None
                    and dragging_piece is not None
                    and dragging_for_free_movement
                ):
                    field = draw_pitch(screen)
                    _move_piece_to_cursor(
                        world,
                        field,
                        dragging_piece,
                        event.pos,
                    )
            elif (
                event.type == pygame.MOUSEBUTTONUP
                and event.button == 1
                and dragging_piece is not None
                and world is not None
                and mode == "playing"
            ):
                field = draw_pitch(screen)
                if dragging_for_free_movement:
                    _move_piece_to_cursor(
                        world,
                        field,
                        dragging_piece,
                        event.pos,
                    )
                else:
                    piece = next(
                        body
                        for body in world.pieces
                        if body.body_id == dragging_piece
                    )
                    center = _pitch_point(field, piece.position)
                    scale = field.width / RENDER_PITCH_LENGTH_MM
                    pull = Vector2(
                        (event.pos[0] - center[0]) / scale,
                        (event.pos[1] - center[1]) / scale,
                    )
                    world.flick(dragging_piece, pull)
                dragging_piece = None

        if mode == "playing" and world is not None:
            if dragging_piece is None:
                world.step(elapsed)
                if world.last_goal is not None:
                    goal_reset_elapsed = 0.0
                if goal_reset_elapsed is not None:
                    goal_reset_elapsed += elapsed
                    if (
                        world.ball.velocity.length < 20.0
                        or goal_reset_elapsed >= GOAL_RESET_TIMEOUT_SECONDS
                    ):
                        world.reset_ball()
                        goal_reset_elapsed = None

        if mode == "menu":
            draw_menu(screen, mouse_position)
        else:
            field = draw_pitch(screen)
            if world is not None:
                _draw_world(screen, field, world)
                _draw_scorebug(screen, field, world)
                _draw_controls(screen, field, free_movement)
                _draw_controls_hint(screen, free_movement)
                if dragging_piece is not None and not dragging_for_free_movement:
                    _draw_flick_aim(
                        screen,
                        field,
                        world,
                        dragging_piece,
                        drag_mouse_position,
                    )

            pygame.display.flip()

        if mode == "menu":
            pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
