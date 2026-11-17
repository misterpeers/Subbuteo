"""Interactive demo for testing AI-controlled player-piece flick power."""

from dataclasses import dataclass
from pathlib import Path

import pygame

from sim_ai_flick import (
    AimMode,
    aim_target_position,
    distance_between_mm,
    flick_toward_target,
)
from sim_ai_brain import (
    Obstacle,
    TargetArea,
    TrainingScenario,
    choose_training_waypoint,
    estimate_contact_strength,
    training_flick_strength,
    plan_training_team_ball_flick,
)
from sim_physics import (
    AWAY,
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
    PENALTY_AREA_WIDTH_MM,
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
DEFAULT_BALL_TRAINING_PIECE_X = 0.25
PENALTY_AREA_EDGE_Y = (
    PITCH_WIDTH_MM - PENALTY_AREA_WIDTH_MM
) / (2 * PITCH_WIDTH_MM)
DEFAULT_BALL_TRAINING_PIECE_POSITION = Vector2(
    DEFAULT_BALL_TRAINING_PIECE_X,
    0.5,
)
DEFAULT_TEAMMATE_POSITION = Vector2(
    DEFAULT_BALL_TRAINING_PIECE_X,
    PENALTY_AREA_EDGE_Y,
)
DEFAULT_THIRD_PIECE_POSITION = Vector2(
    DEFAULT_BALL_TRAINING_PIECE_X,
    1.0 - PENALTY_AREA_EDGE_Y,
)
DEFAULT_TARGET_POSITION = Vector2(0.78, 0.5)
DEFAULT_STRENGTH = 50
STRENGTH_STEP = 5
DEFAULT_MAX_TRAINING_TOUCHES = 3
MIN_TRAINING_TOUCHES = 1
MAX_TRAINING_TOUCHES = 10
TRAINING_FLICK_DELAY_SECONDS = 1.0
DEFAULT_AIM_MODE: AimMode = "marker"
TRAINING_MODE = "training"
FREE_PLAY_MODE = "free-play"
MENU_MODE = "menu"
UI_FONT_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "fonts"
    / "BarlowCondensed-Medium.ttf"
)


@dataclass
class DummyPiece:
    """A square editor object that bounces along one selected pitch axis."""

    center: Vector2
    axis: str
    size_mm: float = PIECE_RADIUS_MM * 2.0
    speed: float = 0.22
    direction: float = 1.0
    minimum: float = 0.0
    maximum: float = 1.0

    def reset_bounds(self) -> None:
        """Set a safe travel interval around the current center."""
        half_size = (
            self.size_mm / (2.0 * PITCH_LENGTH_MM)
            if self.axis == "x"
            else self.size_mm / (2.0 * PITCH_WIDTH_MM)
        )
        coordinate = self.center.x if self.axis == "x" else self.center.y
        self.minimum = max(half_size, coordinate - 0.16)
        self.maximum = min(1.0 - half_size, coordinate + 0.16)
        if self.minimum == self.maximum:
            self.minimum = half_size
            self.maximum = 1.0 - half_size

    def update(self, elapsed_seconds: float) -> Vector2:
        """Advance the dummy and return its normalized-position displacement."""
        previous = self.center
        coordinate = self.center.x if self.axis == "x" else self.center.y
        remaining = self.speed * elapsed_seconds
        while remaining > 0.0:
            boundary = self.maximum if self.direction > 0.0 else self.minimum
            distance = abs(boundary - coordinate)
            if remaining <= distance:
                coordinate += self.direction * remaining
                remaining = 0.0
            else:
                coordinate = boundary
                remaining -= distance
                self.direction *= -1.0
        if self.axis == "x":
            self.center = Vector2(coordinate, self.center.y)
        else:
            self.center = Vector2(self.center.x, coordinate)
        return Vector2(
            self.center.x - previous.x,
            self.center.y - previous.y,
        )


def _create_world(include_teammate: bool = False) -> PhysicsWorld:
    """Create a physics world containing player piece(s) and one ball."""
    piece = Body(
        body_id="ai-piece",
        position=DEFAULT_PIECE_POSITION,
        radius_mm=PIECE_RADIUS_MM,
        mass=22.0,
        team=HOME,
    )
    pieces = [piece]
    if include_teammate:
        for piece_id, position in (
            ("ai-piece-2", DEFAULT_TEAMMATE_POSITION),
            ("ai-piece-3", DEFAULT_THIRD_PIECE_POSITION),
        ):
            pieces.append(
                Body(
                    body_id=piece_id,
                    position=position,
                    radius_mm=PIECE_RADIUS_MM,
                    mass=22.0,
                    team=HOME,
                )
            )
    ball = Body(
        body_id="ball",
        position=DEFAULT_BALL_POSITION,
        radius_mm=BALL_RADIUS_MM,
        mass=2.7,
        kind="ball",
        friction_mm_s2=BALL_FRICTION_MM_S2,
    )
    return PhysicsWorld(pieces, ball)


def _create_training_world(include_ball: bool = False) -> PhysicsWorld:
    """Create a training world with an optional ball on the pitch."""
    world = _create_world(include_teammate=include_ball)
    world.pieces[0].position = (
        DEFAULT_BALL_TRAINING_PIECE_POSITION
        if include_ball
        else Vector2(0.2, 0.5)
    )
    world.ball.movable = include_ball
    if not include_ball:
        world.ball.position = Vector2(-1.0, -1.0)
    return world


def _training_player_pieces(world: PhysicsWorld) -> list[Body]:
    """Return the controllable training pieces, excluding moving dummies."""
    player_ids = {"ai-piece", "ai-piece-2", "ai-piece-3"}
    return [piece for piece in world.pieces if piece.body_id in player_ids]


def _add_dummy_body(world: PhysicsWorld, dummy: DummyPiece, index: int) -> None:
    """Add a stationary collision body for a moving training dummy."""
    world.pieces.append(
        Body(
            body_id=f"dummy-{index}",
            position=dummy.center,
            radius_mm=PIECE_RADIUS_MM,
            mass=22.0,
            movable=False,
            kind="dummy",
        )
    )


def _update_dummy_bodies(
    world: PhysicsWorld,
    dummy_pieces: list[DummyPiece],
    elapsed_seconds: float,
) -> None:
    """Move dummy collision bodies and preserve their bounce velocity."""
    for index, dummy in enumerate(dummy_pieces):
        body_id = f"dummy-{index}"
        body = next(body for body in world.pieces if body.body_id == body_id)
        displacement = dummy.update(elapsed_seconds)
        body.position = dummy.center
        if elapsed_seconds > 0.0:
            body.velocity = Vector2(
                displacement.x * PITCH_LENGTH_MM / elapsed_seconds,
                displacement.y * PITCH_WIDTH_MM / elapsed_seconds,
            )
        else:
            body.velocity = Vector2(0.0, 0.0)


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


def _draw_training_objects(
    surface: pygame.Surface,
    field: pygame.Rect,
    scenario: TrainingScenario,
    dummy_pieces: list[DummyPiece],
    show_target: bool = True,
) -> None:
    """Render the draggable rectangles, dummy pieces, and target area."""
    for obstacle in scenario.obstacles:
        rect_width = max(10, round(obstacle.size.x * field.width))
        rect_height = max(10, round(obstacle.size.y * field.height))
        rect = pygame.Rect(
            field.left + round(obstacle.center.x * field.width - rect_width / 2),
            field.top + round(obstacle.center.y * field.height - rect_height / 2),
            rect_width,
            rect_height,
        )
        pygame.draw.rect(surface, (58, 86, 71), rect)
        pygame.draw.rect(surface, (205, 223, 195), rect, width=2)
        handle_radius = 5
        handles = (
            rect.topleft,
            rect.midtop,
            rect.topright,
            rect.midleft,
            rect.midright,
            rect.bottomleft,
            rect.midbottom,
            rect.bottomright,
        )
        for handle in handles:
            pygame.draw.circle(surface, TEXT_COLOR, handle, handle_radius)
            pygame.draw.circle(surface, PIECE_OUTLINE, handle, handle_radius, 1)

    for dummy in dummy_pieces:
        width = max(2, round(dummy.size_mm * field.width / PITCH_LENGTH_MM))
        height = max(2, round(dummy.size_mm * field.height / PITCH_WIDTH_MM))
        center = _pitch_point(field, dummy.center)
        square = pygame.Rect(
            center[0] - width // 2,
            center[1] - height // 2,
            width,
            height,
        )
        pygame.draw.rect(surface, HOME_COLOR, square)
        pygame.draw.rect(surface, PIECE_OUTLINE, square, width=2)
        axis_font = pygame.font.Font(str(UI_FONT_PATH), max(8, height // 2))
        axis_label = axis_font.render(dummy.axis.upper(), True, TEXT_COLOR)
        surface.blit(axis_label, axis_label.get_rect(center=center))

    if show_target and scenario.target is not None:
        target_center = _pitch_point(field, scenario.target.center)
        target_radius = max(12, round(scenario.target.radius * field.width))
        target_layer = pygame.Surface(
            (target_radius * 2 + 1, target_radius * 2 + 1),
            pygame.SRCALPHA,
        )
        pygame.draw.circle(
            target_layer,
            (*TARGET_COLOR, 58),
            (target_radius, target_radius),
            target_radius,
        )
        surface.blit(
            target_layer,
            (target_center[0] - target_radius, target_center[1] - target_radius),
        )
        pygame.draw.circle(surface, PIECE_OUTLINE, target_center, target_radius, 2)
        pygame.draw.circle(surface, TARGET_COLOR, target_center, max(3, target_radius - 3), 1)


def _draw_training_player(
    surface: pygame.Surface,
    field: pygame.Rect,
    position: Vector2,
    active: bool = False,
) -> None:
    """Render the AI-controlled player piece without the free-play ball."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    radius = max(5, round(PIECE_RADIUS_MM * scale))
    center = _pitch_point(field, position)
    pygame.draw.circle(
        surface,
        TARGET_COLOR if active else PIECE_OUTLINE,
        center,
        radius + 2 if active else radius + 1,
    )
    pygame.draw.circle(surface, HOME_BORDER, center, radius)
    pygame.draw.circle(surface, HOME_COLOR, center, max(2, round(radius * 16 / 21)))


def _draw_training_ball(
    surface: pygame.Surface,
    field: pygame.Rect,
    position: Vector2,
) -> None:
    """Render the training ball."""
    scale = field.width / RENDER_PITCH_LENGTH_MM
    center = _pitch_point(field, position)
    radius = max(3, round(BALL_RADIUS_MM * scale))
    pygame.draw.circle(surface, PIECE_OUTLINE, center, radius + 1)
    pygame.draw.circle(surface, BALL_COLOR, center, radius)


def _menu_button_rects(surface: pygame.Surface) -> dict[str, pygame.Rect]:
    """Return centered mode-selection buttons for the startup menu."""
    width = min(360, surface.get_width() - 48)
    height = 58
    center_x = surface.get_width() // 2
    center_y = surface.get_height() // 2
    return {
        "free-play": pygame.Rect(center_x - width // 2, center_y - 4, width, height),
        "training": pygame.Rect(center_x - width // 2, center_y + 72, width, height),
    }


def _draw_main_menu(
    surface: pygame.Surface,
    mouse_position: tuple[int, int],
) -> dict[str, pygame.Rect]:
    """Draw the initial screen that lets the user choose a demo mode."""
    surface.fill((19, 31, 25))
    title_font = pygame.font.Font(str(UI_FONT_PATH), min(56, max(32, surface.get_width() // 16)))
    body_font = pygame.font.Font(str(UI_FONT_PATH), 22)
    title = title_font.render("SUBBUTEO AI FLICK", True, TEXT_COLOR)
    surface.blit(title, title.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 - 112)))
    subtitle = body_font.render("Choose a mode", True, TEXT_COLOR)
    surface.blit(subtitle, subtitle.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2 - 58)))

    labels = {"free-play": "FREE PLAY SANDBOX", "training": "TRAINING MODE"}
    rects = _menu_button_rects(surface)
    for key, rect in rects.items():
        color = BUTTON_ACTIVE_GREEN if rect.collidepoint(mouse_position) else BUTTON_GREEN
        pygame.draw.rect(surface, color, rect, border_radius=12)
        label = body_font.render(labels[key], True, TEXT_COLOR)
        surface.blit(label, label.get_rect(center=rect.center))
    return rects


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


def _training_button_rects(field: pygame.Rect) -> dict[str, pygame.Rect]:
    """Return menu, run, reset, and object-creation buttons for training."""
    frame_height = round(FRAME_BORDER_MM * field.width / RENDER_PITCH_LENGTH_MM)
    ui_scale = min(1.0, field.width / 650)
    button_height = min(28, max(17, (frame_height - 10) // 2))
    button_width = max(62, round(88 * ui_scale))
    gap = max(3, round(6 * ui_scale))
    start_x = field.left + 5
    top_y = field.top - frame_height + 4
    bottom_y = top_y + button_height + 2
    top_keys = ("menu", "start", "reset", "ball")
    tool_keys = ("obstacle", "dummy-x", "dummy-y", "target")
    rects = {
        key: pygame.Rect(start_x + index * (button_width + gap), top_y, button_width, button_height)
        for index, key in enumerate(top_keys)
    }
    rects.update({
        key: pygame.Rect(start_x + index * (button_width + gap), bottom_y, button_width, button_height)
        for index, key in enumerate(tool_keys)
    })
    return rects


def _draw_training_buttons(
    surface: pygame.Surface,
    field: pygame.Rect,
    selected_action: str | None,
    mouse_position: tuple[int, int],
    ball_enabled: bool,
) -> dict[str, pygame.Rect]:
    """Draw compact controls for the training editor."""
    rects = _training_button_rects(field)
    labels = {
        "menu": "MENU",
        "start": "START",
        "reset": "RESET",
        "ball": "BALL: ON" if ball_enabled else "BALL: OFF",
        "obstacle": "RECT",
        "dummy-x": "DUMMY X",
        "dummy-y": "DUMMY Y",
        "target": "GOAL" if ball_enabled else "TARGET",
    }
    font = pygame.font.Font(str(UI_FONT_PATH), 13)
    for key, rect in rects.items():
        selected = key == selected_action
        active = rect.collidepoint(mouse_position) or (
            key == "ball" and ball_enabled
        )
        color = (
            TARGET_COLOR
            if selected
            else BUTTON_ACTIVE_GREEN if active else BUTTON_GREEN
        )
        pygame.draw.rect(surface, color, rect, border_radius=rect.height // 2)
        label_color = PIECE_OUTLINE if selected else TEXT_COLOR
        label = font.render(labels[key], True, label_color)
        surface.blit(label, label.get_rect(center=rect.center))
    return rects


def _training_touch_control_rects(field: pygame.Rect) -> dict[str, pygame.Rect]:
    """Calculate bounds for the training touch-limit controls."""
    frame_height = round(FRAME_BORDER_MM * field.width / RENDER_PITCH_LENGTH_MM)
    ui_scale = min(1.0, field.width / 650)
    center_y = field.bottom + frame_height // 2
    button_height = min(28, max(17, frame_height - 8))
    gap = max(3, round(5 * ui_scale))
    label_width = max(76, round(90 * ui_scale))
    step_width = max(22, round(28 * ui_scale))
    value_width = max(34, round(42 * ui_scale))
    left = field.left + max(5, round(8 * ui_scale))
    top = center_y - button_height // 2
    label_rect = pygame.Rect(left, top, label_width, button_height)
    minus_rect = pygame.Rect(
        label_rect.right + gap,
        top,
        step_width,
        button_height,
    )
    value_rect = pygame.Rect(
        minus_rect.right + gap,
        top,
        value_width,
        button_height,
    )
    plus_rect = pygame.Rect(
        value_rect.right + gap,
        top,
        step_width,
        button_height,
    )
    return {
        "label": label_rect,
        "minus": minus_rect,
        "value": value_rect,
        "plus": plus_rect,
    }


def _draw_training_touch_controls(
    surface: pygame.Surface,
    field: pygame.Rect,
    max_touches: int,
    message: str,
    enabled: bool,
    ball_enabled: bool,
    piece_touches_used: int,
) -> dict[str, pygame.Rect]:
    """Draw the touch limit or the active figure's ball-mode touch count."""
    rects = _training_touch_control_rects(field)
    font = pygame.font.Font(str(UI_FONT_PATH), 14)
    button_color = BUTTON_GREEN if enabled and not ball_enabled else (58, 86, 71)
    control_labels = (
        (
            ("label", "FIGURE"),
            ("minus", "-"),
            ("value", f"{piece_touches_used}/3"),
            ("plus", "+"),
        )
        if ball_enabled
        else (
            ("label", "MAX TOUCHES"),
            ("minus", "-"),
            ("value", str(max_touches)),
            ("plus", "+"),
        )
    )
    for key, label in control_labels:
        rect = rects[key]
        pygame.draw.rect(surface, button_color, rect, border_radius=rect.height // 2)
        rendered_label = font.render(label, True, TEXT_COLOR)
        surface.blit(rendered_label, rendered_label.get_rect(center=rect.center))

    message_left = rects["plus"].right + 10
    message_width = max(1, field.right - 8 - message_left)
    message_font_size = 14
    message_font = pygame.font.Font(str(UI_FONT_PATH), message_font_size)
    while message_font.size(message)[0] > message_width and message_font_size > 10:
        message_font_size -= 1
        message_font = pygame.font.Font(str(UI_FONT_PATH), message_font_size)
    rendered_message = message_font.render(message, True, TEXT_COLOR)
    surface.blit(
        rendered_message,
        rendered_message.get_rect(
            center=(
                (message_left + field.right - 8) // 2,
                rects["value"].centery,
            )
        ),
    )
    return rects


def _training_object_at(
    field: pygame.Rect,
    scenario: TrainingScenario,
    dummy_pieces: list[DummyPiece],
    player_positions: list[Vector2],
    ball_position: Vector2,
    ball_enabled: bool,
    mouse_position: tuple[int, int],
) -> tuple[str, int, str | None] | None:
    """Find the topmost draggable scenario object under the cursor."""
    mouse = pygame.Vector2(mouse_position)
    if scenario.target is not None:
        target_center = _pitch_point(field, scenario.target.center)
        if mouse.distance_to(target_center) <= scenario.target.radius * field.width:
            return "target", 0, None
    for index in range(len(dummy_pieces) - 1, -1, -1):
        dummy = dummy_pieces[index]
        center = _pitch_point(field, dummy.center)
        width = dummy.size_mm * field.width / PITCH_LENGTH_MM
        height = dummy.size_mm * field.height / PITCH_WIDTH_MM
        if abs(mouse.x - center[0]) <= width / 2 and abs(mouse.y - center[1]) <= height / 2:
            return "dummy", index, None
    for index in range(len(scenario.obstacles) - 1, -1, -1):
        obstacle = scenario.obstacles[index]
        center = _pitch_point(field, obstacle.center)
        half_width_px = obstacle.size.x * field.width / 2
        half_height_px = obstacle.size.y * field.height / 2
        handles = {
            "nw": (center[0] - half_width_px, center[1] - half_height_px),
            "n": (center[0], center[1] - half_height_px),
            "ne": (center[0] + half_width_px, center[1] - half_height_px),
            "w": (center[0] - half_width_px, center[1]),
            "e": (center[0] + half_width_px, center[1]),
            "sw": (center[0] - half_width_px, center[1] + half_height_px),
            "s": (center[0], center[1] + half_height_px),
            "se": (center[0] + half_width_px, center[1] + half_height_px),
        }
        for corner, position in handles.items():
            if mouse.distance_to(position) <= 10:
                return "resize", index, corner
        if (
            abs(mouse.x - center[0]) <= half_width_px
            and abs(mouse.y - center[1]) <= half_height_px
        ):
            return "obstacle", index, None
    if ball_enabled:
        ball_center = _pitch_point(field, ball_position)
        ball_hit_radius = max(8, round(BALL_RADIUS_MM * field.width / PITCH_LENGTH_MM) + 5)
        if mouse.distance_to(ball_center) <= ball_hit_radius:
            return "ball", 0, None
    player_hit_radius = max(
        12,
        PIECE_RADIUS_MM * field.width / PITCH_LENGTH_MM + 6,
    )
    for index in range(len(player_positions) - 1, -1, -1):
        player_center = _pitch_point(field, player_positions[index])
        if mouse.distance_to(player_center) <= player_hit_radius:
            return "player", index, None
    return None


def _move_training_ball(
    field: pygame.Rect,
    mouse_position: tuple[int, int],
) -> Vector2:
    """Move the training ball to a pitch-clamped mouse position."""
    radius_x = BALL_RADIUS_MM / PITCH_LENGTH_MM
    radius_y = BALL_RADIUS_MM / PITCH_WIDTH_MM
    return Vector2(
        min(
            1.0 - radius_x,
            max(radius_x, (mouse_position[0] - field.left) / field.width),
        ),
        min(
            1.0 - radius_y,
            max(radius_y, (mouse_position[1] - field.top) / field.height),
        ),
    )


def _move_training_object(
    field: pygame.Rect,
    scenario: TrainingScenario,
    dummy_pieces: list[DummyPiece],
    piece_position: Vector2,
    object_ref: tuple[str, int, str | None],
    mouse_position: tuple[int, int],
) -> Vector2:
    """Move a selected editor object to the mouse position."""
    x = min(1.0, max(0.0, (mouse_position[0] - field.left) / field.width))
    y = min(1.0, max(0.0, (mouse_position[1] - field.top) / field.height))
    kind, index, corner = object_ref
    if kind == "player":
        radius_x = PIECE_RADIUS_MM / PITCH_LENGTH_MM
        radius_y = PIECE_RADIUS_MM / PITCH_WIDTH_MM
        return Vector2(
            min(1.0 - radius_x, max(radius_x, x)),
            min(1.0 - radius_y, max(radius_y, y)),
        )
    if kind == "target" and scenario.target is not None:
        radius = scenario.target.radius
        scenario.target = TargetArea(
            center=Vector2(
                min(1.0 - radius, max(radius, x)),
                min(1.0 - radius, max(radius, y)),
            ),
            radius=radius,
        )
    elif kind == "obstacle":
        obstacle = scenario.obstacles[index]
        half_width = obstacle.size.x / 2
        half_height = obstacle.size.y / 2
        scenario.obstacles[index] = Obstacle(
            center=Vector2(
                min(1.0 - half_width, max(half_width, x)),
                min(1.0 - half_height, max(half_height, y)),
            ),
            size=obstacle.size,
            padding=obstacle.padding,
        )
    elif kind == "resize":
        obstacle = scenario.obstacles[index]
        left = obstacle.center.x - obstacle.size.x / 2
        right = obstacle.center.x + obstacle.size.x / 2
        top = obstacle.center.y - obstacle.size.y / 2
        bottom = obstacle.center.y + obstacle.size.y / 2
        minimum_width = 0.04
        minimum_height = 0.04
        if corner is not None and "w" in corner:
            right = obstacle.center.x + obstacle.size.x / 2
            left = min(right - minimum_width, max(0.0, x))
        elif corner is not None and "e" in corner:
            left = obstacle.center.x - obstacle.size.x / 2
            right = max(left + minimum_width, min(1.0, x))
        if corner is not None and "n" in corner:
            bottom = obstacle.center.y + obstacle.size.y / 2
            top = min(bottom - minimum_height, max(0.0, y))
        elif corner is not None and "s" in corner:
            top = obstacle.center.y - obstacle.size.y / 2
            bottom = max(top + minimum_height, min(1.0, y))
        resize_x = corner is not None and ("w" in corner or "e" in corner)
        resize_y = corner is not None and ("n" in corner or "s" in corner)
        scenario.obstacles[index] = Obstacle(
            center=Vector2(
                (left + right) / 2 if resize_x else obstacle.center.x,
                (top + bottom) / 2 if resize_y else obstacle.center.y,
            ),
            size=Vector2(
                right - left if resize_x else obstacle.size.x,
                bottom - top if resize_y else obstacle.size.y,
            ),
            padding=obstacle.padding,
        )
    elif kind == "dummy":
        dummy = dummy_pieces[index]
        half_size_x = dummy.size_mm / (2 * PITCH_LENGTH_MM)
        half_size_y = dummy.size_mm / (2 * PITCH_WIDTH_MM)
        dummy.center = Vector2(
            min(1.0 - half_size_x, max(half_size_x, x)),
            min(1.0 - half_size_y, max(half_size_y, y)),
        )
        dummy.reset_bounds()
    return piece_position


def _move_training_selection(
    field: pygame.Rect,
    world: PhysicsWorld,
    scenario: TrainingScenario,
    dummy_pieces: list[DummyPiece],
    object_ref: tuple[str, int, str | None],
    mouse_position: tuple[int, int],
) -> None:
    """Move a selected player piece or scenario object."""
    kind, index, _ = object_ref
    player_pieces = _training_player_pieces(world)
    if kind == "ball":
        world.ball.position = _move_training_ball(field, mouse_position)
        world.ball.velocity = Vector2(0.0, 0.0)
    elif kind == "player":
        player_piece = player_pieces[index]
        player_piece.position = _move_training_object(
            field,
            scenario,
            dummy_pieces,
            player_piece.position,
            object_ref,
            mouse_position,
        )
    else:
        _move_training_object(
            field,
            scenario,
            dummy_pieces,
            player_pieces[0].position,
            object_ref,
            mouse_position,
        )
    if kind == "dummy":
        dummy = dummy_pieces[index]
        body_id = f"dummy-{index}"
        body = next(body for body in world.pieces if body.body_id == body_id)
        body.position = dummy.center
        body.velocity = Vector2(0.0, 0.0)


def main() -> None:
    """Run the interactive AI flick-power tester and scenario trainer."""
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
    mode = MENU_MODE
    selected_action: str | None = None
    training_scenario = TrainingScenario()
    dummy_pieces: list[DummyPiece] = []
    training_started = False
    max_training_touches = DEFAULT_MAX_TRAINING_TOUCHES
    ball_enabled = False
    training_touches_used = 0
    active_piece_id = "ai-piece"
    piece_touch_counts = {"ai-piece": 0}
    training_flick_in_progress = False
    training_delay_remaining = 0.0
    pending_flick_piece_id: str | None = None
    pending_flick_contacted = False
    pending_pass_receiver_id: str | None = None
    pending_pass_ball_start: Vector2 | None = None
    pending_pass_received = False
    pending_touch_reset_piece_id: str | None = None
    dragged_training_object: tuple[str, int, str | None] | None = None

    while running:
        elapsed = clock.tick(60) / 1000.0
        mouse_position = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if mode == MENU_MODE:
                    running = False
                else:
                    mode = MENU_MODE
                    training_started = False
                    dragged_training_object = None
                    hint_message = "Choose a mode"
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (
                        max(event.w, MIN_WINDOW_SIZE[0]),
                        max(event.h, MIN_WINDOW_SIZE[1]),
                    ),
                    pygame.RESIZABLE,
                )
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if mode == MENU_MODE:
                    menu_rects = _menu_button_rects(screen)
                    if menu_rects["free-play"].collidepoint(event.pos):
                        mode = FREE_PLAY_MODE
                        world = _create_world()
                        target_position = DEFAULT_TARGET_POSITION
                        hint_message = "Drag the player piece, ball, and target marker"
                    elif menu_rects["training"].collidepoint(event.pos):
                        mode = TRAINING_MODE
                        world = _create_training_world(ball_enabled)
                        training_scenario = TrainingScenario()
                        dummy_pieces = []
                        training_started = False
                        piece_touch_counts = {
                            piece.body_id: 0
                            for piece in _training_player_pieces(world)
                        }
                        selected_action = None
                        hint_message = "Add shapes, drag them into place, then Start"
                    continue

                field = draw_pitch(screen)
                if mode == TRAINING_MODE:
                    training_rects = _training_button_rects(field)
                    touch_control_rects = _training_touch_control_rects(field)
                    if training_rects["menu"].collidepoint(event.pos):
                        mode = MENU_MODE
                        training_started = False
                        dragged_training_object = None
                        continue
                    if training_rects["ball"].collidepoint(event.pos):
                        ball_enabled = not ball_enabled
                        old_player_positions = {
                            piece.body_id: piece.position
                            for piece in _training_player_pieces(world)
                        }
                        world = _create_training_world(ball_enabled)
                        for piece in _training_player_pieces(world):
                            old_position = old_player_positions.get(piece.body_id)
                            if old_position is None:
                                continue
                            if (
                                ball_enabled
                                and piece.body_id == "ai-piece"
                                and old_position == Vector2(0.2, 0.5)
                            ):
                                continue
                            piece.position = old_position
                        for index, dummy in enumerate(dummy_pieces):
                            _add_dummy_body(world, dummy, index)
                        training_started = False
                        training_touches_used = 0
                        active_piece_id = "ai-piece"
                        piece_touch_counts = {
                            piece.body_id: 0
                            for piece in _training_player_pieces(world)
                        }
                        training_flick_in_progress = False
                        training_delay_remaining = 0.0
                        pending_flick_piece_id = None
                        pending_flick_contacted = False
                        pending_pass_receiver_id = None
                        pending_pass_ball_start = None
                        pending_pass_received = False
                        pending_touch_reset_piece_id = None
                        selected_action = None
                        dragged_training_object = None
                        hint_message = (
                            "Ball included; AI will play toward the right-hand goal"
                            if ball_enabled
                            else "Ball removed; AI will navigate to the target area"
                        )
                        continue
                    if training_rects["start"].collidepoint(event.pos):
                        if ball_enabled and world.ball_in_net is not None:
                            hint_message = (
                                "Ball is in the net; reset the scenario before restarting"
                            )
                        elif not ball_enabled and training_scenario.target is None:
                            hint_message = "Add a target area before starting"
                        else:
                            if not training_started:
                                training_touches_used = 0
                                active_piece_id = "ai-piece"
                                piece_touch_counts = {
                                    player.body_id: 0
                                    for player in _training_player_pieces(world)
                                }
                                training_flick_in_progress = False
                                training_delay_remaining = 0.0
                                pending_flick_piece_id = None
                                pending_flick_contacted = False
                                pending_pass_receiver_id = None
                                pending_pass_ball_start = None
                                pending_pass_received = False
                                pending_touch_reset_piece_id = None
                            training_started = True
                            selected_action = None
                            hint_message = (
                                "AI player is navigating to the goal"
                                if ball_enabled
                                else "AI player is navigating to the target"
                            )
                        continue
                    if training_rects["reset"].collidepoint(event.pos):
                        training_scenario = TrainingScenario()
                        dummy_pieces = []
                        world = _create_training_world(ball_enabled)
                        training_started = False
                        selected_action = None
                        dragged_training_object = None
                        training_touches_used = 0
                        active_piece_id = "ai-piece"
                        piece_touch_counts = {
                            piece.body_id: 0
                            for piece in _training_player_pieces(world)
                        }
                        training_flick_in_progress = False
                        training_delay_remaining = 0.0
                        pending_flick_piece_id = None
                        pending_flick_contacted = False
                        pending_pass_receiver_id = None
                        pending_pass_ball_start = None
                        pending_pass_received = False
                        pending_touch_reset_piece_id = None
                        hint_message = "Scenario cleared"
                        continue

                    if not training_started and not ball_enabled:
                        if touch_control_rects["minus"].collidepoint(event.pos):
                            max_training_touches = max(
                                MIN_TRAINING_TOUCHES,
                                max_training_touches - 1,
                            )
                            training_touches_used = 0
                            hint_message = f"Max touches set to {max_training_touches}"
                            continue
                        if touch_control_rects["plus"].collidepoint(event.pos):
                            max_training_touches = min(
                                MAX_TRAINING_TOUCHES,
                                max_training_touches + 1,
                            )
                            training_touches_used = 0
                            hint_message = f"Max touches set to {max_training_touches}"
                            continue

                    selected_button = next(
                        (
                            key
                            for key in ("obstacle", "dummy-x", "dummy-y", "target")
                            if training_rects[key].collidepoint(event.pos)
                        ),
                        None,
                    )
                    if selected_button is not None:
                        if selected_button == "target" and ball_enabled:
                            hint_message = "Ball mode uses the right-hand goal"
                            continue
                        selected_action = (
                            None if selected_action == selected_button else selected_button
                        )
                        training_started = False
                        continue

                    if field.collidepoint(event.pos):
                        x = (event.pos[0] - field.left) / field.width
                        y = (event.pos[1] - field.top) / field.height
                        x = min(1.0, max(0.0, x))
                        y = min(1.0, max(0.0, y))
                        clicked_object = _training_object_at(
                            field,
                            training_scenario,
                            dummy_pieces,
                            [
                                piece.position
                                for piece in _training_player_pieces(world)
                            ],
                            world.ball.position,
                            ball_enabled,
                            event.pos,
                        )
                        if selected_action is not None and clicked_object is None:
                            if selected_action == "obstacle":
                                obstacle_size = Vector2(0.14, 0.14)
                                center = Vector2(
                                    min(1.0 - obstacle_size.x / 2, max(obstacle_size.x / 2, x)),
                                    min(1.0 - obstacle_size.y / 2, max(obstacle_size.y / 2, y)),
                                )
                                training_scenario.obstacles.append(
                                    Obstacle(
                                        center=center,
                                        size=obstacle_size,
                                    )
                                )
                            elif selected_action in ("dummy-x", "dummy-y"):
                                half_width = PIECE_RADIUS_MM / PITCH_LENGTH_MM
                                half_height = PIECE_RADIUS_MM / PITCH_WIDTH_MM
                                dummy = DummyPiece(
                                    center=Vector2(
                                        min(1.0 - half_width, max(half_width, x)),
                                        min(1.0 - half_height, max(half_height, y)),
                                    ),
                                    axis="x" if selected_action == "dummy-x" else "y",
                                )
                                dummy.reset_bounds()
                                _add_dummy_body(world, dummy, len(dummy_pieces))
                                dummy_pieces.append(dummy)
                            elif selected_action == "target":
                                target_radius = 0.06
                                training_scenario.target = TargetArea(
                                    center=Vector2(
                                        min(1.0 - target_radius, max(target_radius, x)),
                                        min(1.0 - target_radius, max(target_radius, y)),
                                    ),
                                    radius=target_radius,
                                )
                            selected_action = None
                            training_started = False
                            continue
                        if clicked_object is not None:
                            dragged_training_object = clicked_object
                            training_started = False
                            kind, player_index, _ = clicked_object
                            if kind == "player":
                                _training_player_pieces(world)[
                                    player_index
                                ].velocity = Vector2(0.0, 0.0)
                            continue
                        selected_action = None

                if mode == TRAINING_MODE:
                    continue

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
                if mode == FREE_PLAY_MODE and distance_button_rect.collidepoint(event.pos):
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
                elif mode == FREE_PLAY_MODE and slider_rect.inflate(0, 12).collidepoint(event.pos):
                    dragging_slider = True
                    strength = _set_strength_from_mouse(slider_rect, event.pos[0])
                elif mode == FREE_PLAY_MODE and mode_rect.collidepoint(event.pos):
                    aim_mode = "ball" if aim_mode == "marker" else "marker"
                elif mode == FREE_PLAY_MODE and minus_rect.collidepoint(event.pos):
                    strength = max(0, strength - STRENGTH_STEP)
                elif mode == FREE_PLAY_MODE and plus_rect.collidepoint(event.pos):
                    strength = min(100, strength + STRENGTH_STEP)
                elif mode == FREE_PLAY_MODE and flick_rect.collidepoint(event.pos):
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
                elif mode == FREE_PLAY_MODE and reset_rect.collidepoint(event.pos):
                    world.reset_pieces_and_ball()
                    target_position = DEFAULT_TARGET_POSITION
                    strength = DEFAULT_STRENGTH
                    aim_mode = DEFAULT_AIM_MODE
                    piece_distance_mm = 0.0
                    ball_distance_mm = 0.0
                    measuring_distances = False
                    hint_message = "Drag the player piece, ball, and target marker"
                else:
                    if mode == FREE_PLAY_MODE:
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
                if mode == TRAINING_MODE and dragged_training_object is not None:
                    field = draw_pitch(screen)
                    _move_training_selection(
                        field,
                        world,
                        training_scenario,
                        dummy_pieces,
                        dragged_training_object,
                        event.pos,
                    )
                elif mode == FREE_PLAY_MODE and dragging_slider:
                    field = draw_pitch(screen)
                    _, _, _, slider_rect, _, _, _, _ = _control_rects(field)
                    strength = _set_strength_from_mouse(slider_rect, event.pos[0])
                elif mode == FREE_PLAY_MODE and dragged_object is not None:
                    field = draw_pitch(screen)
                    target_position = _move_object_to_cursor(
                        field,
                        world,
                        target_position,
                        dragged_object,
                        event.pos,
                    )
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if mode == TRAINING_MODE and dragged_training_object is not None:
                    field = draw_pitch(screen)
                    _move_training_selection(
                        field,
                        world,
                        training_scenario,
                        dummy_pieces,
                        dragged_training_object,
                        event.pos,
                    )
                elif mode == FREE_PLAY_MODE and dragging_slider:
                    field = draw_pitch(screen)
                    _, _, _, slider_rect, _, _, _, _ = _control_rects(field)
                    strength = _set_strength_from_mouse(slider_rect, event.pos[0])
                elif mode == FREE_PLAY_MODE and dragged_object is not None:
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
                dragged_training_object = None

        if mode == FREE_PLAY_MODE and dragged_object is None:
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
        elif mode == TRAINING_MODE and dragged_training_object is None:
            player_pieces = _training_player_pieces(world)
            piece = next(
                player
                for player in player_pieces
                if player.body_id == active_piece_id
            )
            if training_started:
                _update_dummy_bodies(world, dummy_pieces, elapsed)
                world.step(elapsed)
                if (
                    pending_flick_piece_id is not None
                    and pending_flick_piece_id in world.last_ball_contacts
                ):
                    pending_flick_contacted = True
                    if pending_touch_reset_piece_id is not None:
                        piece_touch_counts[pending_touch_reset_piece_id] = 0
                        pending_touch_reset_piece_id = None
                if (
                    pending_flick_piece_id is not None
                    and pending_pass_ball_start is not None
                    and distance_between_mm(
                        world.ball.position,
                        pending_pass_ball_start,
                    ) > 3.0
                ):
                    teammates_contacted = [
                        player
                        for player in player_pieces
                        if player.body_id != pending_flick_piece_id
                        and player.body_id in world.last_ball_contacts
                    ]
                    if teammates_contacted:
                        pending_pass_receiver_id = teammates_contacted[0].body_id
                        pending_pass_received = True
                all_player_pieces_stopped = all(
                    player.velocity.length == 0.0
                    for player in player_pieces
                )
                completed_flick_piece_id: str | None = None
                if (
                    pending_flick_piece_id is not None
                    and all_player_pieces_stopped
                    and world.ball.velocity.length == 0.0
                ):
                    completed_flick_piece_id = pending_flick_piece_id
                    if not pending_flick_contacted:
                        world.possession = AWAY
                    pending_flick_piece_id = None
                    pending_flick_contacted = False
                if (
                    ball_enabled
                    and world.last_goal is not None
                    and world.last_goal.scoring_team == HOME
                ):
                    hint_message = (
                        f"Goal scored in {training_touches_used} flick(s)"
                    )
                    training_started = False
                elif (
                    ball_enabled
                    and world.possession is not None
                    and world.possession != HOME
                ):
                    hint_message = (
                        "No goal; defending player has possession "
                        "(goal kick restart pending)"
                    )
                    training_started = False
                else:
                    if (
                        pending_pass_received
                        and all_player_pieces_stopped
                        and (not ball_enabled or world.ball.velocity.length == 0.0)
                    ):
                        receiver_id = pending_pass_receiver_id
                        if receiver_id is not None:
                            if completed_flick_piece_id is not None:
                                piece_touch_counts[completed_flick_piece_id] = 0
                            active_piece_id = receiver_id
                        pending_pass_receiver_id = None
                        pending_pass_ball_start = None
                        pending_pass_received = False
                        piece = next(
                            player
                            for player in player_pieces
                            if player.body_id == active_piece_id
                        )
                        hint_message = "Pass received; teammate takes possession"
                    if (
                        all_player_pieces_stopped
                        and (not ball_enabled or world.ball.velocity.length == 0.0)
                    ):
                        if (
                            not ball_enabled
                            and training_scenario.target is not None
                            and training_scenario.target.contains(piece.position)
                        ):
                            hint_message = (
                                f"Target reached in {training_touches_used} touch(es)"
                            )
                            training_started = False
                        elif (
                            not ball_enabled
                            and training_touches_used >= max_training_touches
                        ):
                            hint_message = (
                                f"Touch limit reached ({max_training_touches}); "
                                "target not reached"
                            )
                            training_started = False
                        elif training_flick_in_progress:
                            training_flick_in_progress = False
                            training_delay_remaining = TRAINING_FLICK_DELAY_SECONDS
                            hint_message = (
                                f"Waiting {training_delay_remaining:.1f}s before next flick"
                            )
                        else:
                            launch_next_flick = training_delay_remaining == 0.0
                            if training_delay_remaining > 0.0:
                                training_delay_remaining = max(
                                    0.0,
                                    training_delay_remaining - elapsed,
                                )
                                if training_delay_remaining > 0.0:
                                    hint_message = (
                                        f"Next flick in "
                                        f"{training_delay_remaining:.1f}s"
                                    )
                                else:
                                    launch_next_flick = True

                            if launch_next_flick:
                                if ball_enabled:
                                    flick_obstacles = [
                                        *training_scenario.obstacles,
                                        *[
                                            Obstacle(
                                                center=dummy.center,
                                                size=Vector2(
                                                    dummy.size_mm / PITCH_LENGTH_MM,
                                                    dummy.size_mm / PITCH_WIDTH_MM,
                                                ),
                                                padding=0.0,
                                            )
                                            for dummy in dummy_pieces
                                        ],
                                    ]
                                    flick_plan = plan_training_team_ball_flick(
                                        [
                                            (
                                                player.body_id,
                                                player.position,
                                                piece_touch_counts.get(
                                                    player.body_id,
                                                    0,
                                                ),
                                            )
                                            for player in player_pieces
                                        ],
                                        world.ball.position,
                                        flick_obstacles,
                                    )
                                    if flick_plan is None:
                                        hint_message = (
                                            "No player piece has a safe ball route; "
                                            "reposition a piece or obstacle"
                                        )
                                        training_started = False
                                    else:
                                        flicking_piece = next(
                                            (
                                                player
                                                for player in player_pieces
                                                if player.body_id
                                                == flick_plan.flicking_piece_id
                                            ),
                                            None,
                                        )
                                        if flicking_piece is None:
                                            raise RuntimeError(
                                                "Team flick plan references an "
                                                "unknown player piece"
                                            )
                                        previous_piece_id = active_piece_id
                                        if (
                                            previous_piece_id
                                            != flicking_piece.body_id
                                        ):
                                            pending_touch_reset_piece_id = (
                                                previous_piece_id
                                            )
                                        active_piece_id = flicking_piece.body_id
                                        piece = flicking_piece
                                        flick_applied = flick_toward_target(
                                            world,
                                            flicking_piece.body_id,
                                            flick_plan.piece_target,
                                            flick_plan.strength,
                                        )
                                        if flick_applied:
                                            training_touches_used += 1
                                            piece_touch_counts[
                                                flicking_piece.body_id
                                            ] = piece_touch_counts.get(
                                                flicking_piece.body_id,
                                                0,
                                            ) + 1
                                            training_flick_in_progress = True
                                            pending_flick_piece_id = (
                                                flicking_piece.body_id
                                            )
                                            pending_flick_contacted = (
                                                distance_between_mm(
                                                    flicking_piece.position,
                                                    world.ball.position,
                                                )
                                                <= flicking_piece.radius_mm
                                                + world.ball.radius_mm
                                                + 1.0
                                            )
                                            pending_pass_receiver_id = (
                                                flick_plan.receiver_piece_id
                                            )
                                            pending_pass_ball_start = (
                                                world.ball.position
                                            )
                                            pending_pass_received = False
                                            active_index = player_pieces.index(
                                                flicking_piece
                                            )
                                            hint_message = (
                                                f"Piece {active_index + 1}, flick "
                                                f"{piece_touch_counts[flicking_piece.body_id]}"
                                                f"/3: {flick_plan.action} "
                                                f"({flick_plan.strength * 100:.0f}%)"
                                            )
                                        else:
                                            pending_touch_reset_piece_id = None
                                            hint_message = (
                                                "Could not apply the planned flick"
                                            )
                                            training_started = False
                                else:
                                    dummy_obstacles = [
                                        Obstacle(
                                            center=dummy.center,
                                            size=Vector2(
                                                dummy.size_mm / PITCH_LENGTH_MM,
                                                dummy.size_mm / PITCH_WIDTH_MM,
                                            ),
                                        )
                                        for dummy in dummy_pieces
                                    ]
                                    obstacles = [
                                        *training_scenario.obstacles,
                                        *dummy_obstacles,
                                    ]
                                    waypoint = choose_training_waypoint(
                                        piece.position,
                                        training_scenario.target,
                                        obstacles,
                                    )
                                    if waypoint is None:
                                        hint_message = (
                                            "No clear route; move or remove an obstacle"
                                        )
                                    else:
                                        flick_strength = training_flick_strength(
                                            piece.position,
                                            waypoint,
                                            piece.friction_mm_s2,
                                            touches_remaining=(
                                                max_training_touches
                                                - training_touches_used
                                            ),
                                        )
                                        if flick_toward_target(
                                            world,
                                            active_piece_id,
                                            waypoint,
                                            flick_strength,
                                        ):
                                            training_touches_used += 1
                                            training_flick_in_progress = True
                                            hint_message = (
                                                f"Touch {training_touches_used}/"
                                                f"{max_training_touches}: "
                                                f"flicking ({flick_strength * 100:.0f}%)"
                                            )
                                        else:
                                            hint_message = (
                                                "Could not apply the planned flick"
                                            )
                                            training_started = False
            elif any(player.velocity.length > 0.0 for player in player_pieces):
                world.step(elapsed)

        if mode == MENU_MODE:
            _draw_main_menu(screen, mouse_position)
        elif mode == FREE_PLAY_MODE:
            field = draw_pitch(screen)
            _draw_world(screen, field, world, target_position)
            _draw_ruler(screen, field)
            _draw_hint(screen, field, hint_message)
            _draw_controls(screen, field, strength, aim_mode)
        else:
            field = draw_pitch(screen)
            _draw_training_objects(
                screen,
                field,
                training_scenario,
                dummy_pieces,
                show_target=not ball_enabled,
            )
            if ball_enabled:
                _draw_training_ball(screen, field, world.ball.position)
            for player in _training_player_pieces(world):
                _draw_training_player(
                    screen,
                    field,
                    player.position,
                    active=player.body_id == active_piece_id,
                )
            _draw_training_buttons(
                screen,
                field,
                selected_action,
                mouse_position,
                ball_enabled,
            )
            _draw_training_touch_controls(
                screen,
                field,
                max_training_touches,
                hint_message,
                enabled=not training_started,
                ball_enabled=ball_enabled,
                piece_touches_used=piece_touch_counts.get(active_piece_id, 0),
            )
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
