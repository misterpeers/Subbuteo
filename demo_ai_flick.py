"""Interactive demo for testing AI-controlled player-piece flick power."""

from pathlib import Path

import pygame

from sim_ai_flick import (
    AimMode,
    aim_target_position,
    distance_between_mm,
    flick_toward_target,
)
from sim_ai_brain import estimate_contact_strength
from sim_physics import (
    BALL_FRICTION_MM_S2,
    BALL_RADIUS_MM,
    HOME,
    PIECE_RADIUS_MM,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    Body,
    PhysicsWorld,
    Vector2,
)
from sim_pitch import (
    FRAME_BORDER_MM,
    PITCH_LENGTH_MM as RENDER_PITCH_LENGTH_MM,
    draw_pitch,
)


WINDOW_SIZE = (1280, 900)
MIN_WINDOW_SIZE = (640, 480)

HOME_COLOR = (57, 126, 224)
HOME_BORDER = (245, 245, 245)
PIECE_OUTLINE = (24, 35, 29)
BALL_COLOR = (248, 248, 240)
TARGET_COLOR = (255, 205, 63)
BUTTON_GREEN = (27, 145, 75)
BUTTON_ACTIVE_GREEN = (35, 162, 85)
TEXT_COLOR = (242, 245, 229)
DEFAULT_PIECE_POSITION = Vector2(0.27, 0.5)
DEFAULT_BALL_POSITION = Vector2(0.5, 0.5)
DEFAULT_TARGET_POSITION = Vector2(0.78, 0.5)
DEFAULT_STRENGTH = 50
STRENGTH_STEP = 5
DEFAULT_AIM_MODE: AimMode = "marker"
UI_FONT_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "fonts"
    / "BarlowCondensed-Medium.ttf"
)


def _create_world() -> PhysicsWorld:
    """Create a physics world containing one player piece and one ball."""
    piece = Body(
        body_id="ai-piece",
        position=DEFAULT_PIECE_POSITION,
        radius_mm=PIECE_RADIUS_MM,
        mass=22.0,
        team=HOME,
    )
    ball = Body(
        body_id="ball",
        position=DEFAULT_BALL_POSITION,
        radius_mm=BALL_RADIUS_MM,
        mass=2.7,
        kind="ball",
        friction_mm_s2=BALL_FRICTION_MM_S2,
    )
    return PhysicsWorld([piece], ball)


def _pitch_point(field: pygame.Rect, position: Vector2) -> tuple[int, int]:
    """Convert a normalized pitch position to a screen coordinate."""
    return (
        field.left + round(position.x * field.width),
        field.top + round(position.y * field.height),
    )


def _draw_world(
    surface: pygame.Surface,
    field: pygame.Rect,
    world: PhysicsWorld,
    target_position: Vector2,
) -> None:
    """Render the player piece, ball, and AI target marker."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    piece_radius = max(2, round(PIECE_RADIUS_MM * scale))
    piece = world.pieces[0]
    piece_center = _pitch_point(field, piece.position)
    pygame.draw.circle(surface, PIECE_OUTLINE, piece_center, piece_radius + 1)
    pygame.draw.circle(surface, HOME_BORDER, piece_center, piece_radius)
    pygame.draw.circle(
        surface,
        HOME_COLOR,
        piece_center,
        max(1, round(piece_radius * 16 / 21)),
    )

    ball_center = _pitch_point(field, world.ball.position)
    ball_radius = max(3, round(BALL_RADIUS_MM * scale))
    pygame.draw.circle(surface, PIECE_OUTLINE, ball_center, ball_radius + 1)
    pygame.draw.circle(surface, BALL_COLOR, ball_center, ball_radius)

    target_center = _pitch_point(field, target_position)
    target_radius = max(7, round(15 * scale))
    pygame.draw.circle(
        surface,
        PIECE_OUTLINE,
        target_center,
        target_radius + 2,
        max(2, round(3 * scale)),
    )
    pygame.draw.circle(
        surface,
        TARGET_COLOR,
        target_center,
        target_radius,
        max(2, round(3 * scale)),
    )
    arm = max(5, round(9 * scale))
    pygame.draw.line(
        surface,
        TARGET_COLOR,
        (target_center[0] - arm, target_center[1]),
        (target_center[0] + arm, target_center[1]),
        max(2, round(3 * scale)),
    )
    pygame.draw.line(
        surface,
        TARGET_COLOR,
        (target_center[0], target_center[1] - arm),
        (target_center[0], target_center[1] + arm),
        max(2, round(3 * scale)),
    )


def _draw_ruler(surface: pygame.Surface, field: pygame.Rect) -> None:
    """Draw a millimeter ruler along the lower touchline."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    baseline_y = field.bottom - 2
    tick_width = max(1, round(scale * 1.5))
    font_size = max(10, min(14, round(12 * scale)))
    font = pygame.font.Font(str(UI_FONT_PATH), font_size)

    for distance_mm in range(0, RENDER_PITCH_LENGTH_MM + 1, 50):
        x = min(
            field.right - 1,
            field.left + round(distance_mm * scale),
        )
        is_major_tick = distance_mm % 100 == 0
        tick_height = max(
            7 if is_major_tick else 4,
            round((11 if is_major_tick else 6) * scale),
        )
        pygame.draw.line(
            surface,
            TEXT_COLOR,
            (x, baseline_y),
            (x, baseline_y - tick_height),
            tick_width,
        )

        if distance_mm % 200 == 0:
            label = font.render(f"{distance_mm}mm", True, TEXT_COLOR)
            label_rect = label.get_rect(
                center=(x, baseline_y - tick_height - label.get_height() // 2 - 2)
            )
            label_rect.left = min(
                max(field.left + 4, label_rect.left),
                field.right - label_rect.width - 4,
            )
            background = label_rect.inflate(6, 2)
            pygame.draw.rect(
                surface,
                PIECE_OUTLINE,
                background,
                border_radius=2,
            )
            surface.blit(label, label_rect)


def _control_rects(
    field: pygame.Rect,
) -> tuple[
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
]:
    """Calculate the aim mode, power scale, and action button bounds."""
    frame_height = round(
        FRAME_BORDER_MM * field.width / RENDER_PITCH_LENGTH_MM
    )
    center_y = field.bottom + frame_height // 2
    ui_scale = min(1.0, field.width / 700)
    mode_width = max(76, round(110 * ui_scale))
    label_width = round(45 * ui_scale)
    step_button_width = max(24, round(32 * ui_scale))
    slider_width = max(100, round(180 * ui_scale))
    value_width = round(42 * ui_scale)
    flick_width = max(62, round(92 * ui_scale))
    reset_width = max(54, round(76 * ui_scale))
    gap = max(4, round(8 * ui_scale))
    total_width = (
        mode_width + label_width + step_button_width * 2 + slider_width
        + value_width + flick_width + reset_width + gap * 7
    )
    left = field.centerx - total_width // 2
    button_height = min(34, max(22, frame_height - 8))
    mode_rect = pygame.Rect(
        left,
        center_y - button_height // 2,
        mode_width,
        button_height,
    )
    label_rect = pygame.Rect(
        mode_rect.right + gap,
        center_y - button_height // 2,
        label_width,
        button_height,
    )
    minus_rect = pygame.Rect(
        label_rect.right + gap,
        center_y - button_height // 2,
        step_button_width,
        button_height,
    )
    slider_x = minus_rect.right + gap
    slider_rect = pygame.Rect(
        slider_x,
        center_y - max(12, button_height // 2),
        slider_width,
        max(24, button_height),
    )
    plus_rect = pygame.Rect(
        slider_rect.right + gap,
        center_y - button_height // 2,
        step_button_width,
        button_height,
    )
    value_rect = pygame.Rect(
        plus_rect.right + gap,
        center_y - button_height // 2,
        value_width,
        button_height,
    )
    flick_rect = pygame.Rect(
        value_rect.right + gap,
        center_y - button_height // 2,
        flick_width,
        button_height,
    )
    reset_rect = pygame.Rect(
        flick_rect.right + gap,
        center_y - button_height // 2,
        reset_width,
        button_height,
    )
    return (
        mode_rect,
        label_rect,
        minus_rect,
        slider_rect,
        plus_rect,
        value_rect,
        flick_rect,
        reset_rect,
    )


def _draw_controls(
    surface: pygame.Surface,
    field: pygame.Rect,
    strength: int,
    aim_mode: AimMode,
) -> tuple[
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
    pygame.Rect,
]:
    """Draw the aim mode, power scale, and buttons and return their bounds."""
    (
        mode_rect,
        label_rect,
        minus_rect,
        slider_rect,
        plus_rect,
        value_rect,
        flick_rect,
        reset_rect,
    ) = _control_rects(field)
    frame_height = round(
        FRAME_BORDER_MM * field.width / RENDER_PITCH_LENGTH_MM
    )
    center_y = field.bottom + frame_height // 2
    font_size = max(14, min(20, round(18 * min(1.0, field.width / 700))))
    font = pygame.font.Font(str(UI_FONT_PATH), font_size)
    small_font = pygame.font.Font(str(UI_FONT_PATH), max(13, font_size - 2))

    label = small_font.render("POWER", True, TEXT_COLOR)
    surface.blit(label, label.get_rect(center=label_rect.center))

    for rect, label_text in ((minus_rect, "-"), (plus_rect, "+")):
        pygame.draw.rect(
            surface,
            BUTTON_GREEN,
            rect,
            border_radius=rect.height // 2,
        )
        step_label = font.render(label_text, True, TEXT_COLOR)
        surface.blit(step_label, step_label.get_rect(center=rect.center))

    track = pygame.Rect(
        slider_rect.left,
        center_y - 3,
        slider_rect.width,
        6,
    )
    pygame.draw.rect(surface, PIECE_OUTLINE, track, border_radius=3)
    fill_width = round(track.width * strength / 100)
    if fill_width:
        fill = pygame.Rect(track.left, track.top, fill_width, track.height)
        pygame.draw.rect(surface, TARGET_COLOR, fill, border_radius=3)
    handle_x = track.left + fill_width
    pygame.draw.circle(surface, TEXT_COLOR, (handle_x, center_y), max(5, font_size // 2))
    pygame.draw.circle(
        surface,
        PIECE_OUTLINE,
        (handle_x, center_y),
        max(5, font_size // 2),
        1,
    )

    value_label = font.render(f"{strength:3d}%", True, TEXT_COLOR)
    surface.blit(value_label, value_label.get_rect(center=value_rect.center))

    mode_label = font.render(f"AIM: {aim_mode.upper()}", True, TEXT_COLOR)
    pygame.draw.rect(
        surface,
        BUTTON_GREEN,
        mode_rect,
        border_radius=mode_rect.height // 2,
    )
    surface.blit(mode_label, mode_label.get_rect(center=mode_rect.center))

    for rect, label_text in ((flick_rect, "FLICK"), (reset_rect, "RESET")):
        pygame.draw.rect(
            surface,
            BUTTON_ACTIVE_GREEN if label_text == "FLICK" else BUTTON_GREEN,
            rect,
            border_radius=rect.height // 2,
        )
        button_label = font.render(label_text, True, TEXT_COLOR)
        surface.blit(button_label, button_label.get_rect(center=rect.center))
    return (
        mode_rect,
        label_rect,
        minus_rect,
        slider_rect,
        plus_rect,
        value_rect,
        flick_rect,
        reset_rect,
    )


def _set_strength_from_mouse(
    slider_rect: pygame.Rect,
    mouse_x: int,
) -> int:
    """Map a mouse coordinate on the slider to an integer percentage."""
    fraction = (mouse_x - slider_rect.left) / slider_rect.width
    return round(min(1.0, max(0.0, fraction)) * 100)


def _draggable_at(
    field: pygame.Rect,
    world: PhysicsWorld,
    target_position: Vector2,
    mouse_position: tuple[int, int],
) -> str | None:
    """Return the draggable object under the cursor, if any."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    mouse = pygame.Vector2(mouse_position)
    target_hit_radius = max(12, round(20 * scale))
    if mouse.distance_to(_pitch_point(field, target_position)) <= target_hit_radius:
        return "target"

    ball_hit_radius = max(9, round((BALL_RADIUS_MM + 5) * scale))
    if mouse.distance_to(_pitch_point(field, world.ball.position)) <= ball_hit_radius:
        return "ball"

    piece_hit_radius = max(9, round((PIECE_RADIUS_MM + 5) * scale))
    if mouse.distance_to(
        _pitch_point(field, world.pieces[0].position)
    ) <= piece_hit_radius:
        return "piece"
    return None


def _move_object_to_cursor(
    field: pygame.Rect,
    world: PhysicsWorld,
    target_position: Vector2,
    object_name: str,
    mouse_position: tuple[int, int],
) -> Vector2:
    """Move a dragged pitch object and return the updated target position."""
    x = (mouse_position[0] - field.left) / field.width
    y = (mouse_position[1] - field.top) / field.height
    if object_name == "target":
        return Vector2(min(1.0, max(0.0, x)), min(1.0, max(0.0, y)))

    body = world.ball if object_name == "ball" else world.pieces[0]
    radius_x = body.radius_mm / PITCH_LENGTH_MM
    radius_y = body.radius_mm / PITCH_WIDTH_MM
    body.position = Vector2(
        min(1.0 - radius_x, max(radius_x, x)),
        min(1.0 - radius_y, max(radius_y, y)),
    )
    body.velocity = Vector2(0.0, 0.0)
    return target_position


def _distance_message(piece_mm: float, ball_mm: float) -> str:
    """Format fixed-width piece and ball travel distances for the top hint."""
    return f"Piece: {piece_mm:5.0f} mm | Ball: {ball_mm:5.0f} mm"


def _distance_to_button_rect(field: pygame.Rect) -> pygame.Rect:
    """Calculate the top-frame bounds for the contact-strength estimate button."""
    frame_height = round(
        FRAME_BORDER_MM * field.width / RENDER_PITCH_LENGTH_MM
    )
    ui_scale = min(1.0, field.width / 700)
    button_width = max(84, round(110 * ui_scale))
    button_height = min(30, max(22, frame_height - 8))
    return pygame.Rect(
        field.left + max(4, round(8 * ui_scale)),
        field.top - frame_height + (frame_height - button_height) // 2,
        button_width,
        button_height,
    )


def _draw_hint(surface: pygame.Surface, field: pygame.Rect, message: str) -> None:
    """Render the contact-estimate button and status in the upper frame."""
    frame_height = round(
        FRAME_BORDER_MM * field.width / RENDER_PITCH_LENGTH_MM
    )
    button_rect = _distance_to_button_rect(field)
    button_font = pygame.font.Font(
        str(UI_FONT_PATH),
        max(12, min(15, frame_height // 2)),
    )
    pygame.draw.rect(
        surface,
        BUTTON_GREEN,
        button_rect,
        border_radius=button_rect.height // 2,
    )
    button_label = button_font.render("Distance to", True, TEXT_COLOR)
    surface.blit(button_label, button_label.get_rect(center=button_rect.center))

    font = pygame.font.Font(
        str(UI_FONT_PATH),
        max(14, min(19, frame_height // 2)),
    )
    hint = font.render(message, True, TEXT_COLOR)
    message_left = button_rect.right + 10
    message_right = field.right - 8
    surface.blit(
        hint,
        hint.get_rect(
            center=(
                (message_left + message_right) // 2,
                field.top - frame_height // 2,
            )
        ),
    )


def main() -> None:
    """Run the interactive AI flick-power tester."""
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption("Subbuteo AI Flick Power Tester")
    clock = pygame.time.Clock()
    world = _create_world()
    target_position = DEFAULT_TARGET_POSITION
    strength = DEFAULT_STRENGTH
    aim_mode = DEFAULT_AIM_MODE
    piece_distance_mm = 0.0
    ball_distance_mm = 0.0
    measuring_distances = False
    dragged_object: str | None = None
    dragging_slider = False
    hint_message = "Drag the player piece, ball, and target marker"
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
                field = draw_pitch(screen)
                distance_button_rect = _distance_to_button_rect(field)
                (
                    mode_rect,
                    _,
                    minus_rect,
                    slider_rect,
                    plus_rect,
                    _,
                    flick_rect,
                    reset_rect,
                ) = _control_rects(field)
                if distance_button_rect.collidepoint(event.pos):
                    estimate = estimate_contact_strength(world, "ai-piece")
                    if estimate.strength_percent is None:
                        hint_message = (
                            f"Gap to contact: {estimate.gap_mm:.0f} mm | "
                            "Needs >100% (out of range)"
                        )
                    elif estimate.gap_mm == 0.0:
                        hint_message = "Already touching the ball (0 mm gap)"
                    else:
                        hint_message = (
                            f"Gap to contact: {estimate.gap_mm:.0f} mm | "
                            f"Strength: {estimate.strength_percent:.1f}%"
                        )
                elif slider_rect.inflate(0, 12).collidepoint(event.pos):
                    dragging_slider = True
                    strength = _set_strength_from_mouse(slider_rect, event.pos[0])
                elif mode_rect.collidepoint(event.pos):
                    aim_mode = "ball" if aim_mode == "marker" else "marker"
                elif minus_rect.collidepoint(event.pos):
                    strength = max(0, strength - STRENGTH_STEP)
                elif plus_rect.collidepoint(event.pos):
                    strength = min(100, strength + STRENGTH_STEP)
                elif flick_rect.collidepoint(event.pos):
                    active_target = aim_target_position(
                        world,
                        target_position,
                        aim_mode,
                    )
                    applied = flick_toward_target(
                        world,
                        "ai-piece",
                        active_target,
                        strength / 100.0,
                    )
                    hint_message = (
                        _distance_message(0.0, 0.0)
                        if applied
                        else "Move the aim target away and set power above 0"
                    )
                    if applied:
                        piece_distance_mm = 0.0
                        ball_distance_mm = 0.0
                        measuring_distances = True
                elif reset_rect.collidepoint(event.pos):
                    world.reset_pieces_and_ball()
                    target_position = DEFAULT_TARGET_POSITION
                    strength = DEFAULT_STRENGTH
                    aim_mode = DEFAULT_AIM_MODE
                    piece_distance_mm = 0.0
                    ball_distance_mm = 0.0
                    measuring_distances = False
                    hint_message = "Drag the player piece, ball, and target marker"
                else:
                    dragged_object = _draggable_at(
                        field,
                        world,
                        target_position,
                        event.pos,
                    )
                    if dragged_object is not None:
                        target_position = _move_object_to_cursor(
                            field,
                            world,
                            target_position,
                            dragged_object,
                            event.pos,
                        )
                        if dragged_object in ("piece", "ball"):
                            measuring_distances = False
            elif event.type == pygame.MOUSEMOTION:
                if dragging_slider:
                    field = draw_pitch(screen)
                    _, _, _, slider_rect, _, _, _, _ = _control_rects(field)
                    strength = _set_strength_from_mouse(slider_rect, event.pos[0])
                elif dragged_object is not None:
                    field = draw_pitch(screen)
                    target_position = _move_object_to_cursor(
                        field,
                        world,
                        target_position,
                        dragged_object,
                        event.pos,
                    )
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if dragging_slider:
                    field = draw_pitch(screen)
                    _, _, _, slider_rect, _, _, _, _ = _control_rects(field)
                    strength = _set_strength_from_mouse(slider_rect, event.pos[0])
                elif dragged_object is not None:
                    field = draw_pitch(screen)
                    target_position = _move_object_to_cursor(
                        field,
                        world,
                        target_position,
                        dragged_object,
                        event.pos,
                    )
                dragging_slider = False
                dragged_object = None

        if dragged_object is None:
            piece_position_before = world.pieces[0].position
            ball_position_before = world.ball.position
            world.step(elapsed)
            if measuring_distances:
                piece_distance_mm += distance_between_mm(
                    piece_position_before,
                    world.pieces[0].position,
                )
                ball_distance_mm += distance_between_mm(
                    ball_position_before,
                    world.ball.position,
                )
                hint_message = _distance_message(
                    piece_distance_mm,
                    ball_distance_mm,
                )
                if (
                    world.pieces[0].velocity.length == 0.0
                    and world.ball.velocity.length == 0.0
                ):
                    measuring_distances = False

        field = draw_pitch(screen)
        _draw_world(screen, field, world, target_position)
        _draw_ruler(screen, field)
        _draw_hint(screen, field, hint_message)
        _draw_controls(screen, field, strength, aim_mode)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
