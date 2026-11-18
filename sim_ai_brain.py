"""Headless AI player calculations for ball contact and scenario navigation."""

from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from math import ceil, cos, hypot, pi, sin, sqrt
from typing import Literal

from sim_ai_flick import distance_between_mm
from sim_physics import (
    BALL_FRICTION_MM_S2,
    BALL_RADIUS_MM,
    MAX_DRAG_MM,
    MAX_FLICK_SPEED_MM_S,
    MIN_FLICK_DRAG_MM,
    PIECE_FRICTION_MM_S2,
    PIECE_RADIUS_MM,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    SHOOTING_AREA_DEPTH_MM,
    PhysicsWorld,
    Vector2,
)

TRAINING_FLICK_SAFETY_FACTOR = 0.88
TRAINING_BALL_ADVANCE_MM = 30.0
TRAINING_SETUP_OFFSETS_MM = (15.0, 30.0)
TRAINING_SETUP_DIRECTIONS = 12


@dataclass(frozen=True)
class ContactEstimate:
    """Describe the gap and flick strength estimated for first ball contact."""

    gap_mm: float
    strength_percent: float | None


@dataclass(frozen=True)
class Obstacle:
    """Axis-aligned rectangular area the AI player should navigate around."""

    center: Vector2
    size: Vector2
    padding: float = 0.015

    def contains(self, point: Vector2, clearance: float = 0.0) -> bool:
        """Return whether a point is inside the rectangle plus clearance."""
        half_width = self.size.x / 2.0 + self.padding + clearance
        half_height = self.size.y / 2.0 + self.padding + clearance
        return (
            abs(point.x - self.center.x) <= half_width
            and abs(point.y - self.center.y) <= half_height
        )


@dataclass(frozen=True)
class TargetArea:
    """Large circular region the AI player should reach."""

    center: Vector2
    radius: float = 0.06

    def contains(self, point: Vector2) -> bool:
        """Return whether a pitch point is inside the target circle."""
        return hypot(point.x - self.center.x, point.y - self.center.y) <= self.radius


@dataclass
class TrainingScenario:
    """Scenario layout containing static obstacles and one target area."""

    obstacles: list[Obstacle] = field(default_factory=list)
    target: TargetArea | None = None


@dataclass(frozen=True)
class TrainingBallFlickPlan:
    """Describe a player-piece flick that contacts the ball toward a waypoint."""

    piece_target: Vector2
    ball_target: Vector2
    strength: float
    action: Literal["advance", "pass", "shot"] = "advance"
    receiver_piece_id: str | None = None
    flicking_piece_id: str | None = None


def _grid_position(position: Vector2, columns: int, rows: int) -> tuple[int, int]:
    """Map a normalized pitch point to its nearest navigation-grid cell."""
    return (
        min(columns - 1, max(0, round(position.x * (columns - 1)))),
        min(rows - 1, max(0, round(position.y * (rows - 1)))),
    )


def _cell_position(cell: tuple[int, int], columns: int, rows: int) -> Vector2:
    """Map a navigation-grid cell to normalized pitch coordinates."""
    return Vector2(cell[0] / (columns - 1), cell[1] / (rows - 1))


def _find_path(
    start: Vector2,
    target: TargetArea,
    obstacles: list[Obstacle],
    clearance: float,
) -> list[Vector2]:
    """Find a short eight-direction path on a normalized pitch grid."""
    columns = 49
    rows = 33
    start_cell = _grid_position(start, columns, rows)
    queue: list[tuple[float, int, tuple[int, int]]] = []
    tie_breaker = count()
    heappush(queue, (0.0, next(tie_breaker), start_cell))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {
        start_cell: None,
    }
    cost_so_far = {start_cell: 0.0}
    goal_cell: tuple[int, int] | None = None
    neighbor_steps = (
        (-1, 0), (1, 0), (0, -1), (0, 1),
        (-1, -1), (-1, 1), (1, -1), (1, 1),
    )

    while queue:
        _, _, current = heappop(queue)
        current_position = _cell_position(current, columns, rows)
        if target.contains(current_position):
            goal_cell = current
            break

        for delta_x, delta_y in neighbor_steps:
            neighbor = current[0] + delta_x, current[1] + delta_y
            if not (0 <= neighbor[0] < columns and 0 <= neighbor[1] < rows):
                continue
            neighbor_position = _cell_position(neighbor, columns, rows)
            if any(obstacle.contains(neighbor_position, clearance) for obstacle in obstacles):
                continue
            if delta_x and delta_y:
                side_cells = (
                    (current[0] + delta_x, current[1]),
                    (current[0], current[1] + delta_y),
                )
                if any(
                    any(
                        obstacle.contains(
                            _cell_position(side_cell, columns, rows),
                            clearance,
                        )
                        for obstacle in obstacles
                    )
                    for side_cell in side_cells
                ):
                    continue

            next_cost = cost_so_far[current] + hypot(
                delta_x / (columns - 1),
                delta_y / (rows - 1),
            )
            if next_cost >= cost_so_far.get(neighbor, float("inf")):
                continue
            cost_so_far[neighbor] = next_cost
            came_from[neighbor] = current
            heuristic = hypot(
                (target.center.x - neighbor_position.x),
                (target.center.y - neighbor_position.y),
            )
            heappush(
                queue,
                (next_cost + heuristic, next(tie_breaker), neighbor),
            )

    if goal_cell is None:
        return []

    path: list[Vector2] = []
    current_cell: tuple[int, int] | None = goal_cell
    while current_cell is not None:
        path.append(_cell_position(current_cell, columns, rows))
        current_cell = came_from[current_cell]
    path.reverse()
    return path


def _segment_is_clear(
    start: Vector2,
    end: Vector2,
    obstacles: list[Obstacle],
    clearance: float,
) -> bool:
    """Check a line at short physical intervals to avoid obstacle contact."""
    distance_mm = distance_between_mm(start, end)
    sample_count = max(1, ceil(distance_mm / 8.0))
    for sample_index in range(1, sample_count + 1):
        fraction = sample_index / sample_count
        point = Vector2(
            start.x + (end.x - start.x) * fraction,
            start.y + (end.y - start.y) * fraction,
        )
        if any(obstacle.contains(point, clearance) for obstacle in obstacles):
            return False
    return True


def choose_training_waypoint(
    piece_position: Vector2,
    target: TargetArea,
    obstacles: list[Obstacle] | None = None,
) -> Vector2 | None:
    """Choose a safe stopping point on an obstacle-avoiding path."""
    if target.contains(piece_position):
        return None
    obstacles = obstacles or []
    clearance = 0.012
    path = _find_path(
        piece_position,
        target,
        obstacles,
        clearance=clearance,
    )
    if not path:
        return None
    if len(path) == 1:
        candidate = path[0]
        if _segment_is_clear(
            piece_position,
            candidate,
            obstacles,
            clearance,
        ):
            return candidate
        return None

    waypoint: Vector2 | None = None
    for candidate in path[1:]:
        if not _segment_is_clear(
            piece_position,
            candidate,
            obstacles,
            clearance,
        ):
            break
        waypoint = candidate
    return waypoint


def training_flick_strength(
    piece_position: Vector2,
    waypoint: Vector2,
    friction_mm_s2: float = PIECE_FRICTION_MM_S2,
    *,
    touches_remaining: int | None = None,
) -> float:
    """Estimate the flick power needed to reach a stopping waypoint.

    Retain a small safety margin while multiple touches remain. On the final
    permitted touch, use the full stopping-distance estimate to avoid falling
    short of the target.

    Args:
        piece_position: Current normalized position of the player piece.
        waypoint: Planned normalized stopping position.
        friction_mm_s2: Player-piece friction in millimeters per second squared.
        touches_remaining: Number of allowed touches including this flick.

    Returns:
        float: Flick strength between 0.0 and 1.0.

    Raises:
        ValueError: If friction is not positive or no touches remain.
    """
    if friction_mm_s2 <= 0.0:
        raise ValueError("Piece friction must be greater than zero.")
    if touches_remaining is not None and touches_remaining < 1:
        raise ValueError("At least one touch must remain.")

    distance_mm = distance_between_mm(piece_position, waypoint)
    distance_factor = (
        1.0
        if touches_remaining == 1
        else TRAINING_FLICK_SAFETY_FACTOR
    )
    desired_speed_mm_s = sqrt(
        2.0 * friction_mm_s2 * distance_mm * distance_factor
    )
    return min(1.0, desired_speed_mm_s / MAX_FLICK_SPEED_MM_S)


def _training_ball_contact_plan(
    piece_position: Vector2,
    ball_position: Vector2,
    ball_target: Vector2,
    obstacles: list[Obstacle],
    action: Literal["advance", "pass", "shot"] = "advance",
) -> TrainingBallFlickPlan | None:
    """Calculate a safe angled contact and enough impulse for its ball path."""
    ball_direction = Vector2(
        (ball_target.x - ball_position.x) * PITCH_LENGTH_MM,
        (ball_target.y - ball_position.y) * PITCH_WIDTH_MM,
    ).normalized()
    ball_travel_mm = distance_between_mm(ball_position, ball_target)
    if ball_travel_mm == 0.0:
        return None

    contact_distance_mm = PIECE_RADIUS_MM + BALL_RADIUS_MM + 1.0
    piece_target = Vector2(
        ball_position.x - ball_direction.x * contact_distance_mm / PITCH_LENGTH_MM,
        ball_position.y - ball_direction.y * contact_distance_mm / PITCH_WIDTH_MM,
    )
    piece_path = Vector2(
        (piece_target.x - piece_position.x) * PITCH_LENGTH_MM,
        (piece_target.y - piece_position.y) * PITCH_WIDTH_MM,
    )
    piece_travel_mm = piece_path.length
    piece_direction = piece_path.normalized()
    if piece_travel_mm < 1.0:
        piece_target = ball_position
        piece_direction = ball_direction
        piece_travel_mm = 0.0
    alignment = piece_direction.dot(ball_direction)
    if alignment <= 0.25:
        return None

    clearance = max(
        PIECE_RADIUS_MM / PITCH_LENGTH_MM,
        BALL_RADIUS_MM / PITCH_WIDTH_MM,
    )
    if not _segment_is_clear(
        piece_position, piece_target, obstacles, clearance
    ) or not _segment_is_clear(
        ball_position, ball_target, obstacles, clearance
    ):
        return None

    desired_ball_speed_mm_s = sqrt(
        2.0 * BALL_FRICTION_MM_S2 * ball_travel_mm
    )
    desired_piece_impact_speed_mm_s = (
        desired_ball_speed_mm_s / 1.3 / alignment
    )
    required_piece_speed_mm_s = sqrt(
        desired_piece_impact_speed_mm_s**2
        + 2.0 * PIECE_FRICTION_MM_S2 * piece_travel_mm
    )
    strength = 1.02 * required_piece_speed_mm_s / MAX_FLICK_SPEED_MM_S
    if strength > 1.0:
        return None

    return TrainingBallFlickPlan(
        piece_target=piece_target,
        ball_target=ball_target,
        strength=strength,
        action=action,
    )


def _training_ball_pass_plan(
    piece_position: Vector2,
    ball_position: Vector2,
    teammates: list[tuple[str, Vector2]],
    obstacles: list[Obstacle],
) -> TrainingBallFlickPlan | None:
    """Choose a reachable teammate and flick the ball through their position."""
    best_plan: TrainingBallFlickPlan | None = None
    best_score: tuple[float, float] | None = None
    for receiver_id, receiver_position in sorted(
        teammates,
        key=lambda teammate: distance_between_mm(ball_position, teammate[1]),
    ):
        pass_direction = Vector2(
            (receiver_position.x - ball_position.x) * PITCH_LENGTH_MM,
            (receiver_position.y - ball_position.y) * PITCH_WIDTH_MM,
        ).normalized()
        if pass_direction.length == 0.0:
            continue
        contact_distance_mm = PIECE_RADIUS_MM + BALL_RADIUS_MM + 2.0
        ball_target = Vector2(
            receiver_position.x
            + pass_direction.x * contact_distance_mm / PITCH_LENGTH_MM,
            receiver_position.y
            + pass_direction.y * contact_distance_mm / PITCH_WIDTH_MM,
        )
        plan = _training_ball_contact_plan(
            piece_position,
            ball_position,
            ball_target,
            obstacles,
            action="pass",
        )
        if plan is None:
            continue
        score = (
            plan.strength,
            distance_between_mm(ball_position, ball_target),
        )
        if best_score is not None and score >= best_score:
            continue
        best_score = score
        best_plan = TrainingBallFlickPlan(
            piece_target=plan.piece_target,
            ball_target=plan.ball_target,
            strength=plan.strength,
            action="pass",
            receiver_piece_id=receiver_id,
        )

    return best_plan


def _training_ball_advance_waypoints(
    ball_position: Vector2,
    obstacles: list[Obstacle],
) -> list[Vector2]:
    progress_areas = (
        TargetArea(Vector2(0.92, 0.5), 0.015),
        TargetArea(Vector2(0.97, 0.44), 0.012),
        TargetArea(Vector2(0.97, 0.56), 0.012),
        TargetArea(Vector2(0.90, 0.36), 0.02),
        TargetArea(Vector2(0.90, 0.64), 0.02),
    )
    waypoints: list[Vector2] = []
    clearance = max(
        PIECE_RADIUS_MM / PITCH_LENGTH_MM,
        BALL_RADIUS_MM / PITCH_WIDTH_MM,
    )
    for progress_area in progress_areas:
        if progress_area.contains(ball_position):
            continue
        target = progress_area.center
        travel_mm = distance_between_mm(ball_position, target)
        fraction = min(1.0, TRAINING_BALL_ADVANCE_MM / travel_mm)
        waypoint = Vector2(
            ball_position.x + (target.x - ball_position.x) * fraction,
            ball_position.y + (target.y - ball_position.y) * fraction,
        )
        if not _segment_is_clear(
            ball_position,
            waypoint,
            obstacles,
            clearance,
        ):
            waypoint = choose_training_waypoint(
                ball_position,
                progress_area,
                obstacles,
            )
            if waypoint is None:
                continue
            travel_mm = distance_between_mm(ball_position, waypoint)
            if travel_mm > TRAINING_BALL_ADVANCE_MM:
                fraction = TRAINING_BALL_ADVANCE_MM / travel_mm
                waypoint = Vector2(
                    ball_position.x + (waypoint.x - ball_position.x) * fraction,
                    ball_position.y + (waypoint.y - ball_position.y) * fraction,
                )
        waypoints.append(waypoint)
    return waypoints


def _plan_training_ball_flick(
    piece_position: Vector2,
    ball_position: Vector2,
    obstacles: list[Obstacle],
    *,
    piece_touches_used: int,
    teammates: list[tuple[str, Vector2]],
    advance_waypoints: list[Vector2] | None,
) -> TrainingBallFlickPlan | None:
    """Plan one piece's shot, short advance, or possession-preserving pass."""
    if piece_touches_used >= 3:
        return None

    shooting_line = 1.0 - SHOOTING_AREA_DEPTH_MM / PITCH_LENGTH_MM
    goal_target = Vector2(1.02, 0.5)
    if ball_position.x > shooting_line:
        shot = _training_ball_contact_plan(
            piece_position,
            ball_position,
            goal_target,
            obstacles,
            action="shot",
        )
        if shot is not None:
            return shot

    if piece_touches_used >= 2:
        return _training_ball_pass_plan(
            piece_position,
            ball_position,
            teammates,
            obstacles,
        )

    if advance_waypoints is None:
        advance_waypoints = _training_ball_advance_waypoints(
            ball_position,
            obstacles,
        )
    advance_plans: list[TrainingBallFlickPlan] = []
    for waypoint in advance_waypoints:
        plan = _training_ball_contact_plan(
            piece_position,
            ball_position,
            waypoint,
            obstacles,
        )
        if plan is not None and plan.ball_target.x >= ball_position.x:
            advance_plans.append(plan)
    if advance_plans:
        return min(
            advance_plans,
            key=lambda plan: (
                plan.strength,
                distance_between_mm(ball_position, plan.ball_target),
            ),
        )
    return _training_ball_pass_plan(
        piece_position,
        ball_position,
        teammates,
        obstacles,
    )


def plan_training_ball_flick(
    piece_position: Vector2,
    ball_position: Vector2,
    obstacles: list[Obstacle] | None = None,
    *,
    piece_touches_used: int = 0,
    teammates: list[tuple[str, Vector2]] | None = None,
) -> TrainingBallFlickPlan | None:
    """Plan a controlled advance, shot, or possession-preserving pass."""
    return _plan_training_ball_flick(
        piece_position,
        ball_position,
        obstacles or [],
        piece_touches_used=piece_touches_used,
        teammates=teammates or [],
        advance_waypoints=None,
    )


def _approach_intersects_teammate(
    piece_position: Vector2,
    piece_target: Vector2,
    teammate_position: Vector2,
) -> bool:
    """Return whether a flicking piece's approach intersects a teammate base."""
    approach_mm = Vector2(
        (piece_target.x - piece_position.x) * PITCH_LENGTH_MM,
        (piece_target.y - piece_position.y) * PITCH_WIDTH_MM,
    )
    approach_length_squared = approach_mm.dot(approach_mm)
    if approach_length_squared == 0.0:
        closest_point = piece_position
    else:
        teammate_offset_mm = Vector2(
            (teammate_position.x - piece_position.x) * PITCH_LENGTH_MM,
            (teammate_position.y - piece_position.y) * PITCH_WIDTH_MM,
        )
        approach_fraction = max(
            0.0,
            min(
                1.0,
                teammate_offset_mm.dot(approach_mm) / approach_length_squared,
            ),
        )
        closest_point = Vector2(
            piece_position.x
            + (piece_target.x - piece_position.x) * approach_fraction,
            piece_position.y
            + (piece_target.y - piece_position.y) * approach_fraction,
        )

    return (
        distance_between_mm(closest_point, teammate_position)
        <= 22.0
    )


def _training_ball_followup_plan(
    piece_position: Vector2,
    ball_position: Vector2,
    piece_touches_used: int,
    teammates: list[tuple[str, Vector2]],
    obstacles: list[Obstacle],
) -> TrainingBallFlickPlan | None:
    """Find a short, direct follow-up flick for a setup-pass receiver."""
    if piece_touches_used >= 3:
        return None

    shooting_line = 1.0 - SHOOTING_AREA_DEPTH_MM / PITCH_LENGTH_MM
    if ball_position.x > shooting_line:
        shot = _training_ball_contact_plan(
            piece_position,
            ball_position,
            Vector2(1.02, 0.5),
            obstacles,
            action="shot",
        )
        if shot is not None:
            return shot

    if piece_touches_used >= 2:
        return _training_ball_pass_plan(
            piece_position,
            ball_position,
            teammates,
            obstacles,
        )

    advance_plans: list[TrainingBallFlickPlan] = []
    for angle in (-pi / 6.0, 0.0, pi / 6.0):
        ball_target = Vector2(
            ball_position.x
            + cos(angle) * TRAINING_BALL_ADVANCE_MM / PITCH_LENGTH_MM,
            ball_position.y
            + sin(angle) * TRAINING_BALL_ADVANCE_MM / PITCH_WIDTH_MM,
        )
        if not (
            BALL_RADIUS_MM / PITCH_LENGTH_MM
            <= ball_target.x
            <= 1.0 - BALL_RADIUS_MM / PITCH_LENGTH_MM
            and BALL_RADIUS_MM / PITCH_WIDTH_MM
            <= ball_target.y
            <= 1.0 - BALL_RADIUS_MM / PITCH_WIDTH_MM
        ):
            continue
        plan = _training_ball_contact_plan(
            piece_position,
            ball_position,
            ball_target,
            obstacles,
            action="advance",
        )
        if plan is not None:
            advance_plans.append(plan)

    if advance_plans:
        return min(
            advance_plans,
            key=lambda plan: (
                plan.strength,
                distance_between_mm(ball_position, plan.ball_target),
            ),
        )
    return _training_ball_pass_plan(
        piece_position,
        ball_position,
        teammates,
        obstacles,
    )


def _training_ball_setup_plan(
    player_pieces: list[tuple[str, Vector2, int]],
    flicking_piece_id: str,
    ball_position: Vector2,
    obstacles: list[Obstacle],
) -> TrainingBallFlickPlan | None:
    """Find a short third-touch nudge that opens a teammate's next route."""
    flicking_piece_position = next(
        position
        for piece_id, position, _ in player_pieces
        if piece_id == flicking_piece_id
    )
    teammates = [
        (piece_id, position, touches_used)
        for piece_id, position, touches_used in player_pieces
        if piece_id != flicking_piece_id and touches_used < 3
    ]
    other_piece_positions = [
        (piece_id, position)
        for piece_id, position, _ in player_pieces
        if piece_id != flicking_piece_id
    ]
    ball_margin_x = BALL_RADIUS_MM / PITCH_LENGTH_MM
    ball_margin_y = BALL_RADIUS_MM / PITCH_WIDTH_MM
    best_plan: TrainingBallFlickPlan | None = None
    best_score: tuple[int, float, float, float] | None = None
    next_action_priority = {"shot": 0, "pass": 1, "advance": 1}

    for receiver_id, receiver_position, receiver_touches in teammates:
        receiver_teammates = [
            (piece_id, position)
            for piece_id, position, _ in player_pieces
            if piece_id != receiver_id
        ]
        for offset_mm in TRAINING_SETUP_OFFSETS_MM:
            for direction_index in range(TRAINING_SETUP_DIRECTIONS):
                angle = 2.0 * pi * direction_index / TRAINING_SETUP_DIRECTIONS
                ball_target = Vector2(
                    ball_position.x
                    + cos(angle) * offset_mm / PITCH_LENGTH_MM,
                    ball_position.y
                    + sin(angle) * offset_mm / PITCH_WIDTH_MM,
                )
                if not (
                    ball_margin_x <= ball_target.x <= 1.0 - ball_margin_x
                    and ball_margin_y <= ball_target.y <= 1.0 - ball_margin_y
                ):
                    continue

                setup_plan = _training_ball_contact_plan(
                    flicking_piece_position,
                    ball_position,
                    ball_target,
                    obstacles,
                    action="pass",
                )
                if setup_plan is None or any(
                    _approach_intersects_teammate(
                        flicking_piece_position,
                        setup_plan.piece_target,
                        teammate_position,
                    )
                    for _, teammate_position in other_piece_positions
                ):
                    continue

                next_plan = _training_ball_followup_plan(
                    receiver_position,
                    ball_target,
                    receiver_touches,
                    receiver_teammates,
                    obstacles,
                )
                if next_plan is None:
                    continue
                if any(
                    _approach_intersects_teammate(
                        receiver_position,
                        next_plan.piece_target,
                        teammate_position,
                    )
                    for _, teammate_position in receiver_teammates
                ) or _approach_intersects_teammate(
                    receiver_position,
                    next_plan.piece_target,
                    setup_plan.piece_target,
                ):
                    continue

                score = (
                    next_action_priority[next_plan.action],
                    offset_mm,
                    setup_plan.strength,
                    next_plan.strength,
                )
                if best_score is not None and score >= best_score:
                    continue
                best_score = score
                best_plan = TrainingBallFlickPlan(
                    piece_target=setup_plan.piece_target,
                    ball_target=setup_plan.ball_target,
                    strength=setup_plan.strength,
                    action="pass",
                    receiver_piece_id=receiver_id,
                )

    return best_plan


def plan_training_team_ball_flick(
    player_pieces: list[tuple[str, Vector2, int]],
    ball_position: Vector2,
    obstacles: list[Obstacle] | None = None,
) -> TrainingBallFlickPlan | None:
    """Choose the safest available piece for the next ball-contact flick."""
    obstacles = obstacles or []
    candidate_plans: list[TrainingBallFlickPlan] = []
    shooting_line = 1.0 - SHOOTING_AREA_DEPTH_MM / PITCH_LENGTH_MM
    has_advancing_piece = any(
        touches_used < 2 for _, _, touches_used in player_pieces
    )
    advance_waypoints = None
    if ball_position.x <= shooting_line and has_advancing_piece:
        advance_waypoints = _training_ball_advance_waypoints(
            ball_position,
            obstacles,
        )
    for piece_id, piece_position, touches_used in player_pieces:
        teammates = [
            (teammate_id, teammate_position)
            for teammate_id, teammate_position, _ in player_pieces
            if teammate_id != piece_id
        ]
        plan = _plan_training_ball_flick(
            piece_position,
            ball_position,
            obstacles,
            piece_touches_used=touches_used,
            teammates=teammates,
            advance_waypoints=advance_waypoints,
        )
        if plan is not None:
            if any(
                _approach_intersects_teammate(
                    piece_position,
                    plan.piece_target,
                    teammate_position,
                )
                for teammate_id, teammate_position, _ in player_pieces
                if teammate_id != piece_id
            ):
                continue
            candidate_plans.append(
                TrainingBallFlickPlan(
                    piece_target=plan.piece_target,
                    ball_target=plan.ball_target,
                    strength=plan.strength,
                    action=plan.action,
                    receiver_piece_id=plan.receiver_piece_id,
                    flicking_piece_id=piece_id,
                )
            )

    if not any(plan.action == "shot" for plan in candidate_plans):
        for piece_id, _, touches_used in player_pieces:
            if touches_used != 2:
                continue
            setup_plan = _training_ball_setup_plan(
                player_pieces,
                piece_id,
                ball_position,
                obstacles,
            )
            if setup_plan is not None:
                candidate_plans.append(
                    TrainingBallFlickPlan(
                        piece_target=setup_plan.piece_target,
                        ball_target=setup_plan.ball_target,
                        strength=setup_plan.strength,
                        action="setup",
                        receiver_piece_id=setup_plan.receiver_piece_id,
                        flicking_piece_id=piece_id,
                    )
                )

    shot_plans = [
        plan for plan in candidate_plans if plan.action == "shot"
    ]
    if shot_plans:
        return min(shot_plans, key=lambda plan: plan.strength)

    setup_plans = [
        plan for plan in candidate_plans if plan.action == "setup"
    ]
    if setup_plans:
        return min(setup_plans, key=lambda plan: plan.strength)

    possession_plans = [
        plan
        for plan in candidate_plans
        if plan.action in {"advance", "pass"}
    ]
    if possession_plans:
        return min(
            possession_plans,
            key=lambda plan: (
                plan.strength,
                distance_between_mm(ball_position, plan.ball_target),
                -plan.ball_target.x,
            ),
        )
    if candidate_plans:
        return min(candidate_plans, key=lambda plan: plan.strength)
    return None


def estimate_contact_strength(
    world: PhysicsWorld,
    piece_id: str,
) -> ContactEstimate:
    """Estimate the strength needed to roll a player piece into the ball.

    The calculation assumes a straight, unobstructed path and constant
    piece-friction deceleration. It excludes rebounds and other collisions.

    Args:
        world: Physics world containing the player piece and ball.
        piece_id: Identifier of the player piece to evaluate.

    Returns:
        ContactEstimate: Edge-to-edge gap and required strength percentage.
            A ``None`` strength means the estimated gap exceeds maximum range.

    Raises:
        ValueError: If the piece identifier is unknown or its friction is
            negative.
    """
    piece = next(
        (body for body in world.pieces if body.body_id == piece_id),
        None,
    )
    if piece is None:
        raise ValueError(f"Unknown piece: {piece_id}")
    if piece.friction_mm_s2 < 0.0:
        raise ValueError("Piece friction must not be negative.")

    center_distance_mm = distance_between_mm(piece.position, world.ball.position)
    gap_mm = max(
        0.0,
        center_distance_mm - piece.radius_mm - world.ball.radius_mm,
    )
    if gap_mm == 0.0:
        return ContactEstimate(gap_mm, 0.0)

    minimum_strength_percent = 100.0 * MIN_FLICK_DRAG_MM / MAX_DRAG_MM
    if piece.friction_mm_s2 == 0.0:
        return ContactEstimate(gap_mm, minimum_strength_percent)

    required_speed_mm_s = sqrt(2.0 * piece.friction_mm_s2 * gap_mm)
    if required_speed_mm_s > MAX_FLICK_SPEED_MM_S:
        return ContactEstimate(gap_mm, None)

    strength_percent = max(
        minimum_strength_percent,
        100.0 * required_speed_mm_s / MAX_FLICK_SPEED_MM_S,
    )
    return ContactEstimate(gap_mm, strength_percent)
