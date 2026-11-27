"""Headless AI player calculations for ball contact and scenario navigation."""

from dataclasses import dataclass, field, replace
from heapq import heappop, heappush
from itertools import count
from math import ceil, cos, hypot, pi, sin, sqrt
from typing import Literal

from sim_ai_flick import distance_between_mm
from sim_physics import (
    ATTACK_TOWARD_DECREASING_X,
    ATTACK_TOWARD_INCREASING_X,
    BALL_FRICTION_MM_S2,
    BALL_RADIUS_MM,
    GOAL_AREA_WIDTH_MM,
    MAX_DRAG_MM,
    MAX_FLICK_SPEED_MM_S,
    MIN_FLICK_DRAG_MM,
    PIECE_FRICTION_MM_S2,
    PIECE_RADIUS_MM,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    SHOOTING_AREA_DEPTH_MM,
    WALL_RESTITUTION,
    PhysicsWorld,
    Vector2,
)

FLICK_SAFETY_FACTOR = 0.88
BALL_ADVANCE_MM = 30.0
ADVANCE_DISTANCES_MM = (30.0, 60.0, 100.0)
MAX_ADVANCE_MM = 100.0
PROGRESS_STEP_MM = 10.0
BLOCK_CAP_NEAR = 0.2
BLOCK_CAP_FAR = 0.6
BLOCK_CAP_NEAR_MM = 100.0
BLOCK_CAP_FAR_MM = 400.0
BANK_STRENGTH_FACTORS = (0.9, 1.0, 1.15)
BANK_WALL_MARGIN_MM = 20.0
SHOT_AIM_DEPTH_MM = 24.0
SHOT_AIM_OFFSETS_MM = (0.0, -20.0, 20.0, -38.0, 38.0)
SETUP_OFFSETS_MM = (15.0, 30.0)
SETUP_DIRECTIONS = 12
SAMPLE_CONTACT_OFFSETS_MM = (-14.0, -7.0, 0.0, 7.0, 14.0)
SAMPLE_STRENGTH_MULTIPLIERS = (1.1, 1.5, 2.2, 3.5)
SAMPLE_MIN_STRENGTH = 0.1


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
class Scenario:
    """Scenario layout containing static obstacles and one target area."""

    obstacles: list[Obstacle] = field(default_factory=list)
    target: TargetArea | None = None


@dataclass(frozen=True)
class FlickPlan:
    """Describe a player-piece flick that contacts the ball toward a waypoint.

    Attributes:
        piece_target: Normalized point the piece is flicked toward.
        ball_target: Normalized point the ball is meant to reach.
        strength: Flick strength from 0.0 to 1.0.
        action: ``advance``, ``pass``, ``shot`` or ``setup``.
        receiver_piece_id: The intended receiver of a pass or setup.
        flicking_piece_id: The piece that flicks, when known.
        bank: Whether the ball is meant to rebound off a wall on the way.
            Only passes are ever banked; there are no bank shots.
    """

    piece_target: Vector2
    ball_target: Vector2
    strength: float
    action: Literal["advance", "pass", "shot", "setup"] = "advance"
    receiver_piece_id: str | None = None
    flicking_piece_id: str | None = None
    bank: bool = False


def _validated_direction(attack_direction: int) -> int:
    """Return a valid attack direction or reject an unsupported value."""
    if attack_direction not in (
        ATTACK_TOWARD_INCREASING_X,
        ATTACK_TOWARD_DECREASING_X,
    ):
        raise ValueError("Attack direction must be 1 or -1.")
    return attack_direction


def _mirror_position(position: Vector2, mirror: bool) -> Vector2:
    """Reflect a normalized position along X when mirroring is requested."""
    return Vector2(1.0 - position.x, position.y) if mirror else position


def _mirror_obstacles(
    obstacles: list[Obstacle],
    mirror: bool,
) -> list[Obstacle]:
    """Reflect obstacles along X when mirroring is requested."""
    if not mirror:
        return obstacles
    return [
        Obstacle(
            center=_mirror_position(obstacle.center, True),
            size=obstacle.size,
            padding=obstacle.padding,
        )
        for obstacle in obstacles
    ]


def _mirror_plan(plan: FlickPlan | None, mirror: bool) -> FlickPlan | None:
    """Reflect a plan's targets along X when mirroring is requested."""
    if plan is None or not mirror:
        return plan
    return replace(
        plan,
        piece_target=_mirror_position(plan.piece_target, True),
        ball_target=_mirror_position(plan.ball_target, True),
    )

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


def choose_waypoint(
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


def waypoint_flick_strength(
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
        else FLICK_SAFETY_FACTOR
    )
    desired_speed_mm_s = sqrt(
        2.0 * friction_mm_s2 * distance_mm * distance_factor
    )
    return min(1.0, desired_speed_mm_s / MAX_FLICK_SPEED_MM_S)


def _ball_contact_plan(
    piece_position: Vector2,
    ball_position: Vector2,
    ball_target: Vector2,
    obstacles: list[Obstacle],
    action: Literal["advance", "pass", "shot", "setup"] = "advance",
    ball_launch_speed_mm_s: float | None = None,
) -> FlickPlan | None:
    """Calculate a safe angled contact and enough impulse for its ball path.

    Args:
        piece_position: Normalized position of the flicking piece.
        ball_position: Normalized ball position.
        ball_target: Normalized point the ball should travel toward.
        obstacles: Areas the piece and ball paths must avoid.
        action: The action recorded on the plan.
        ball_launch_speed_mm_s: Ball speed wanted just after contact. When
            omitted, the speed that stops the ball at ``ball_target`` is
            used. A bank pass gives a higher speed, because the ball must
            carry on past the wall.

    Returns:
        FlickPlan | None: The contact plan, or ``None`` if the approach is too
            oblique, a path is blocked, or more than full strength is needed.
    """
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

    desired_ball_speed_mm_s = (
        ball_launch_speed_mm_s
        if ball_launch_speed_mm_s is not None
        else sqrt(2.0 * BALL_FRICTION_MM_S2 * ball_travel_mm)
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

    return FlickPlan(
        piece_target=piece_target,
        ball_target=ball_target,
        strength=strength,
        action=action,
    )


def _ball_pass_plan(
    piece_position: Vector2,
    ball_position: Vector2,
    teammates: list[tuple[str, Vector2]],
    obstacles: list[Obstacle],
) -> FlickPlan | None:
    """Choose a reachable teammate and flick the ball through their position."""
    best_plan: FlickPlan | None = None
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
        plan = _ball_contact_plan(
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
        best_plan = FlickPlan(
            piece_target=plan.piece_target,
            ball_target=plan.ball_target,
            strength=plan.strength,
            action="pass",
            receiver_piece_id=receiver_id,
        )

    return best_plan


def _bank_walls() -> list[tuple[str, float]]:
    """Return the walls a bank pass may use, attacking toward increasing X.

    Each wall is given as the axis that is constant along it and the
    millimeter coordinate of the ball's center when it touches the wall. The
    walls are both touchlines and the attacked goal line. The team's own goal
    line is never used, so a bank pass cannot turn into an own goal.

    Returns:
        list[tuple[str, float]]: ``("x" or "y", line_mm)`` pairs.
    """
    return [
        ("y", BALL_RADIUS_MM),
        ("y", PITCH_WIDTH_MM - BALL_RADIUS_MM),
        ("x", PITCH_LENGTH_MM - BALL_RADIUS_MM),
    ]


def bank_bounce_point(
    ball_position: Vector2,
    target: Vector2,
    axis: str,
    line_mm: float,
) -> Vector2 | None:
    """Return where a one-wall bank pass must touch the wall.

    The physics keeps the ball's speed along a wall and scales its speed
    across the wall by ``WALL_RESTITUTION``. A straight line from the ball to
    the target's image, placed beyond the wall at the target's distance from
    the wall divided by the restitution, therefore crosses the wall where the
    ball must bounce. Friction does not change the direction, so the image is
    exact apart from speed.

    Args:
        ball_position: Normalized ball position.
        target: Normalized point the ball should reach after the bounce.
        axis: ``"y"`` for a touchline or ``"x"`` for a goal line.
        line_mm: Coordinate, along ``axis``, of the ball's center at the
            bounce.

    Returns:
        Vector2 | None: The normalized bounce point, or ``None`` if the ball
            and target are not on the same side of the wall, the bounce
            would fall within ``BANK_WALL_MARGIN_MM`` of a corner, or, on a
            goal line, within the goal-area span (where a touch would hand
            possession to the defender) plus that margin.
    """
    index = 0 if axis == "x" else 1
    ball_mm = (ball_position.x * PITCH_LENGTH_MM, ball_position.y * PITCH_WIDTH_MM)
    target_mm = (target.x * PITCH_LENGTH_MM, target.y * PITCH_WIDTH_MM)
    ball_side = ball_mm[index] - line_mm
    target_side = target_mm[index] - line_mm
    if ball_side * target_side <= 0.0:
        return None
    image = list(target_mm)
    image[index] = line_mm - target_side / WALL_RESTITUTION
    fraction = (line_mm - ball_mm[index]) / (image[index] - ball_mm[index])
    if not 0.0 < fraction < 1.0:
        return None
    other = 1 - index
    along_mm = ball_mm[other] + fraction * (image[other] - ball_mm[other])
    extent_mm = PITCH_LENGTH_MM if other == 0 else PITCH_WIDTH_MM
    corner_margin = BALL_RADIUS_MM + BANK_WALL_MARGIN_MM
    if not corner_margin <= along_mm <= extent_mm - corner_margin:
        return None
    if axis == "x" and (
        abs(along_mm - PITCH_WIDTH_MM / 2.0)
        <= GOAL_AREA_WIDTH_MM / 2.0 + BANK_WALL_MARGIN_MM
    ):
        return None
    if axis == "x":
        return Vector2(line_mm / PITCH_LENGTH_MM, along_mm / PITCH_WIDTH_MM)
    return Vector2(along_mm / PITCH_LENGTH_MM, line_mm / PITCH_WIDTH_MM)


def _bank_pass_plans(
    piece_position: Vector2,
    ball_position: Vector2,
    receiver_id: str,
    receiver_position: Vector2,
    obstacles: list[Obstacle],
) -> list[FlickPlan]:
    """Plan bank passes from one piece to one receiver, off each usable wall.

    The ball's launch speed covers both legs: enough speed after the bounce to
    reach the receiver, divided by the share of speed the bounce keeps for
    this angle, plus what friction takes on the way to the wall. Each pass is
    offered at ``BANK_STRENGTH_FACTORS`` times that strength, because errors
    grow over the longer path; simulation picks the one that works.

    Args:
        piece_position: Normalized position of the passing piece.
        ball_position: Normalized ball position.
        receiver_id: Identifier of the receiving teammate.
        receiver_position: Normalized position of the receiver.
        obstacles: Areas the piece and ball paths must avoid.

    Returns:
        list[FlickPlan]: Bank passes within full strength, possibly empty.
    """
    plans: list[FlickPlan] = []
    clearance = max(
        PIECE_RADIUS_MM / PITCH_LENGTH_MM,
        BALL_RADIUS_MM / PITCH_WIDTH_MM,
    )
    for axis, line_mm in _bank_walls():
        bounce = bank_bounce_point(
            ball_position,
            receiver_position,
            axis,
            line_mm,
        )
        if bounce is None:
            continue
        if not _segment_is_clear(bounce, receiver_position, obstacles, clearance):
            continue
        first_leg_mm = distance_between_mm(ball_position, bounce)
        second_leg_mm = distance_between_mm(bounce, receiver_position)
        if first_leg_mm == 0.0:
            continue
        incoming = Vector2(
            (bounce.x - ball_position.x) * PITCH_LENGTH_MM,
            (bounce.y - ball_position.y) * PITCH_WIDTH_MM,
        ).normalized()
        across, along = (
            (incoming.x, incoming.y) if axis == "x" else (incoming.y, incoming.x)
        )
        kept = sqrt(along * along + (WALL_RESTITUTION * across) ** 2)
        after_bounce = sqrt(2.0 * BALL_FRICTION_MM_S2 * second_leg_mm)
        launch_speed = sqrt(
            (after_bounce / kept) ** 2
            + 2.0 * BALL_FRICTION_MM_S2 * first_leg_mm
        )
        contact = _ball_contact_plan(
            piece_position,
            ball_position,
            bounce,
            obstacles,
            action="pass",
            ball_launch_speed_mm_s=launch_speed,
        )
        if contact is None:
            continue
        for factor in BANK_STRENGTH_FACTORS:
            strength = contact.strength * factor
            if strength > 1.0:
                continue
            plans.append(
                FlickPlan(
                    piece_target=contact.piece_target,
                    ball_target=receiver_position,
                    strength=strength,
                    action="pass",
                    receiver_piece_id=receiver_id,
                    bank=True,
                )
            )
    return plans


def bank_pass_candidates(
    player_pieces: list[tuple[str, Vector2, int]],
    ball_position: Vector2,
    obstacles: list[Obstacle] | None = None,
    *,
    attack_direction: int = ATTACK_TOWARD_INCREASING_X,
) -> list[FlickPlan]:
    """List bank passes for a team: passes that rebound off one wall.

    Every piece with touches left may pass to every teammate, off either
    touchline or the attacked goal line outside the goal-area span. A pass
    whose approach would run through a teammate is left out. There are no
    bank shots (rules, Q31); callers use these only when no direct pass
    works (Q7).

    Args:
        player_pieces: Identifier, normalized position and consecutive touch
            count for each piece of the attacking team.
        ball_position: Normalized ball position.
        obstacles: Areas that piece and ball paths must avoid.
        attack_direction: ``1`` to attack toward increasing X or ``-1`` to
            attack toward decreasing X.

    Returns:
        list[FlickPlan]: Bank passes with their flicking piece set, weakest
            first.

    Raises:
        ValueError: If the attack direction is not ``1`` or ``-1``.
    """
    direction = _validated_direction(attack_direction)
    mirror = direction == ATTACK_TOWARD_DECREASING_X
    pieces = [
        (piece_id, _mirror_position(position, mirror), touches_used)
        for piece_id, position, touches_used in player_pieces
    ]
    ball = _mirror_position(ball_position, mirror)
    mirrored_obstacles = _mirror_obstacles(obstacles or [], mirror)
    plans: list[FlickPlan] = []
    for piece_id, piece_position, touches_used in pieces:
        if touches_used >= 3:
            continue
        for receiver_id, receiver_position, _ in pieces:
            if receiver_id == piece_id:
                continue
            for plan in _bank_pass_plans(
                piece_position,
                ball,
                receiver_id,
                receiver_position,
                mirrored_obstacles,
            ):
                if any(
                    _approach_intersects_teammate(
                        piece_position,
                        plan.piece_target,
                        other_position,
                    )
                    for other_id, other_position, _ in pieces
                    if other_id != piece_id
                ):
                    continue
                plans.append(replace(plan, flicking_piece_id=piece_id))
    plans.sort(key=lambda plan: plan.strength)
    return [
        mirrored
        for plan in plans
        if (mirrored := _mirror_plan(plan, mirror)) is not None
    ]


def _shot_plans(
    piece_position: Vector2,
    ball_position: Vector2,
    obstacles: list[Obstacle],
) -> list[FlickPlan]:
    """Return shots at aim points across the goal mouth, centre first.

    Each aim point lies ``SHOT_AIM_DEPTH_MM`` behind the goal line, offset
    across the mouth by one of ``SHOT_AIM_OFFSETS_MM``. The outermost offset
    keeps the ball clear of the posts. Offering several aims lets simulation
    find an open part of the goal when the centre is blocked or the angle is
    tight.

    Args:
        piece_position: Normalized position of the shooting piece.
        ball_position: Normalized ball position, attacking toward increasing X.
        obstacles: Areas the piece and ball paths must avoid.

    Returns:
        list[FlickPlan]: Possible shots in aim order (the centre, then
            further out), or an empty list if the ball is not strictly inside
            the shooting area or no aim has a safe contact.
    """
    shooting_line = 1.0 - SHOOTING_AREA_DEPTH_MM / PITCH_LENGTH_MM
    if ball_position.x <= shooting_line:
        return []
    aim_x = 1.0 + SHOT_AIM_DEPTH_MM / PITCH_LENGTH_MM
    shots: list[FlickPlan] = []
    for offset_mm in SHOT_AIM_OFFSETS_MM:
        shot = _ball_contact_plan(
            piece_position,
            ball_position,
            Vector2(aim_x, 0.5 + offset_mm / PITCH_WIDTH_MM),
            obstacles,
            action="shot",
        )
        if shot is not None:
            shots.append(shot)
    return shots


def block_flick_cap(distance_mm: float) -> float:
    """Return the largest block-flick strength for a piece at a distance.

    The cap grows with the piece's distance from the ball (rules, Q22): a
    piece near the ball may only make a small adjustment, while a distant
    piece may flick harder to get back into play. Between the near and far
    distances the cap rises in a straight line.

    Args:
        distance_mm: Distance from the piece to the ball, in millimeters.

    Returns:
        float: Strength cap from ``BLOCK_CAP_NEAR`` to ``BLOCK_CAP_FAR``.
    """
    if distance_mm <= BLOCK_CAP_NEAR_MM:
        return BLOCK_CAP_NEAR
    if distance_mm >= BLOCK_CAP_FAR_MM:
        return BLOCK_CAP_FAR
    fraction = (distance_mm - BLOCK_CAP_NEAR_MM) / (
        BLOCK_CAP_FAR_MM - BLOCK_CAP_NEAR_MM
    )
    return BLOCK_CAP_NEAR + (BLOCK_CAP_FAR - BLOCK_CAP_NEAR) * fraction


def progress_steps(progress_mm: float) -> int:
    """Return forward progress in whole steps, capped at the balanced limit.

    Used to rank flicks under the balanced, possession-first rule. Progress
    is counted in ``PROGRESS_STEP_MM`` steps so that a millimeter or two of
    extra travel does not outrank a lower flick strength, and it is capped
    at ``MAX_ADVANCE_MM`` so that going further than the balanced limit earns
    nothing more.

    Args:
        progress_mm: Ball movement toward the attacked goal, in millimeters.

    Returns:
        int: Whole progress steps; negative for a backward move.
    """
    return int(min(progress_mm, MAX_ADVANCE_MM) // PROGRESS_STEP_MM)


def _ball_advance_waypoints(
    ball_position: Vector2,
    obstacles: list[Obstacle],
    distances_mm: tuple[float, ...] = ADVANCE_DISTANCES_MM,
) -> list[Vector2]:
    """Return ball targets that advance toward areas near the goal.

    For each progress area, a target is placed at each advance distance
    along the straight line toward it, or along an obstacle-avoiding route
    when the straight line is blocked. Distances above ``MAX_ADVANCE_MM``
    (the balanced limit) are skipped, and a target is never placed beyond
    its area's center.

    Args:
        ball_position: Normalized ball position, attacking toward increasing X.
        obstacles: Areas the ball path must avoid.
        distances_mm: Ball travel distances to offer, in millimeters.

    Returns:
        list[Vector2]: Distinct advance targets.
    """
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
    distances = [
        distance for distance in distances_mm if distance <= MAX_ADVANCE_MM
    ]
    for progress_area in progress_areas:
        if progress_area.contains(ball_position):
            continue
        detour: Vector2 | None = None
        detour_checked = False
        for advance_mm in distances:
            target = progress_area.center
            travel_mm = distance_between_mm(ball_position, target)
            fraction = min(1.0, advance_mm / travel_mm)
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
                if not detour_checked:
                    detour = choose_waypoint(
                        ball_position,
                        progress_area,
                        obstacles,
                    )
                    detour_checked = True
                if detour is None:
                    continue
                waypoint = detour
                travel_mm = distance_between_mm(ball_position, waypoint)
                if travel_mm > advance_mm:
                    fraction = advance_mm / travel_mm
                    waypoint = Vector2(
                        ball_position.x
                        + (waypoint.x - ball_position.x) * fraction,
                        ball_position.y
                        + (waypoint.y - ball_position.y) * fraction,
                    )
            if any(
                distance_between_mm(waypoint, existing) < 1.0
                for existing in waypoints
            ):
                continue
            waypoints.append(waypoint)
    return waypoints


def _piece_advance_plans(
    piece_position: Vector2,
    ball_position: Vector2,
    obstacles: list[Obstacle],
    advance_waypoints: list[Vector2] | None,
) -> list[FlickPlan]:
    """Return every reachable advance for one piece.

    An advance must not move the ball backward along the pitch.

    Args:
        piece_position: Normalized position of the piece.
        ball_position: Normalized ball position, attacking toward increasing X.
        obstacles: Areas the piece and ball paths must avoid.
        advance_waypoints: Ball targets to try. ``None`` means the standard
            targets toward the goal from ``_ball_advance_waypoints``.

    Returns:
        list[FlickPlan]: The advances the piece can make within full strength.
    """
    if advance_waypoints is None:
        advance_waypoints = _ball_advance_waypoints(
            ball_position,
            obstacles,
        )
    advance_plans: list[FlickPlan] = []
    for waypoint in advance_waypoints:
        plan = _ball_contact_plan(
            piece_position,
            ball_position,
            waypoint,
            obstacles,
        )
        if plan is not None and plan.ball_target.x >= ball_position.x:
            advance_plans.append(plan)
    return advance_plans


def _advances_by_distance(
    plans: list[FlickPlan],
    ball_position: Vector2,
) -> list[FlickPlan]:
    """Keep the weakest advance at each offered advance distance.

    Each plan is grouped with the smallest ``ADVANCE_DISTANCES_MM`` value
    that covers its ball travel, and the lowest-strength plan of each group
    is kept. This lets a piece offer a short, a medium and a long advance
    without simulating every target area at every distance.

    Args:
        plans: One piece's advance plans.
        ball_position: Normalized ball position.

    Returns:
        list[FlickPlan]: At most one plan per advance distance, longest first.
    """
    best: dict[float, FlickPlan] = {}
    for plan in plans:
        travel_mm = distance_between_mm(ball_position, plan.ball_target)
        group = next(
            (
                distance
                for distance in ADVANCE_DISTANCES_MM
                if travel_mm <= distance + 1.0
            ),
            ADVANCE_DISTANCES_MM[-1],
        )
        if group not in best or plan.strength < best[group].strength:
            best[group] = plan
    return [best[group] for group in sorted(best, reverse=True)]


def _plan_piece_flick(
    piece_position: Vector2,
    ball_position: Vector2,
    obstacles: list[Obstacle],
    *,
    piece_touches_used: int,
    teammates: list[tuple[str, Vector2]],
    advance_waypoints: list[Vector2] | None,
) -> FlickPlan | None:
    """Plan one piece's shot, short advance, or possession-preserving pass.

    This is the single place that decides between shooting, advancing and
    passing for one piece. It plans the flicking piece's own move and also
    judges a setup-pass receiver's next move; the two differ only in the
    advance targets they pass in.

    Coordinates use the canonical attacking direction of increasing X.

    Args:
        piece_position: Normalized position of the piece.
        ball_position: Normalized ball position.
        obstacles: Areas the piece and ball paths must avoid.
        piece_touches_used: Consecutive touches the piece has already used.
        teammates: Identifiers and positions of possible pass receivers.
        advance_waypoints: Ball targets for an advance. ``None`` means the
            standard targets toward the goal from ``_ball_advance_waypoints``.

    Returns:
        FlickPlan | None: A shot if one is available inside the shooting area,
            otherwise a pass on the final touch, otherwise the advance needing
            the least strength, otherwise a pass; ``None`` if nothing is safe.
    """
    if piece_touches_used >= 3:
        return None

    shots = _shot_plans(piece_position, ball_position, obstacles)
    if shots:
        return shots[0]

    if piece_touches_used >= 2:
        return _ball_pass_plan(
            piece_position,
            ball_position,
            teammates,
            obstacles,
        )

    advance_plans = _piece_advance_plans(
        piece_position,
        ball_position,
        obstacles,
        advance_waypoints,
    )
    if advance_plans:
        return min(
            advance_plans,
            key=lambda plan: (
                plan.strength,
                distance_between_mm(ball_position, plan.ball_target),
            ),
        )
    return _ball_pass_plan(
        piece_position,
        ball_position,
        teammates,
        obstacles,
    )


def plan_piece_flick(
    piece_position: Vector2,
    ball_position: Vector2,
    obstacles: list[Obstacle] | None = None,
    *,
    piece_touches_used: int = 0,
    teammates: list[tuple[str, Vector2]] | None = None,
    attack_direction: int = ATTACK_TOWARD_INCREASING_X,
) -> FlickPlan | None:
    """Plan a controlled advance, shot, or possession-preserving pass.

    Args:
        piece_position: Normalized position of the flicking player piece.
        ball_position: Normalized ball position.
        obstacles: Areas the piece and ball paths must avoid.
        piece_touches_used: Consecutive touches already used by the piece.
        teammates: Identifiers and positions of possible pass receivers.
        attack_direction: ``1`` to attack toward increasing X or ``-1`` to
            attack toward decreasing X.

    Returns:
        FlickPlan | None: The chosen plan, or ``None`` if no safe plan exists.

    Raises:
        ValueError: If the attack direction is not ``1`` or ``-1``.
    """
    direction = _validated_direction(attack_direction)
    mirror = direction == ATTACK_TOWARD_DECREASING_X
    plan = _plan_piece_flick(
        _mirror_position(piece_position, mirror),
        _mirror_position(ball_position, mirror),
        _mirror_obstacles(obstacles or [], mirror),
        piece_touches_used=piece_touches_used,
        teammates=[
            (teammate_id, _mirror_position(position, mirror))
            for teammate_id, position in teammates or []
        ],
        advance_waypoints=None,
    )
    return _mirror_plan(plan, mirror)


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


def _angled_advance_waypoints(ball_position: Vector2) -> list[Vector2]:
    """Return short advance targets straight ahead and 30 degrees either side.

    Used to judge a setup-pass receiver's next flick, where a quick local
    check is wanted rather than a route toward the goal.

    Args:
        ball_position: Normalized ball position, attacking toward increasing X.

    Returns:
        list[Vector2]: Targets ``BALL_ADVANCE_MM`` from the ball that keep the
            ball inside the pitch.
    """
    waypoints: list[Vector2] = []
    for angle in (-pi / 6.0, 0.0, pi / 6.0):
        ball_target = Vector2(
            ball_position.x + cos(angle) * BALL_ADVANCE_MM / PITCH_LENGTH_MM,
            ball_position.y + sin(angle) * BALL_ADVANCE_MM / PITCH_WIDTH_MM,
        )
        if (
            BALL_RADIUS_MM / PITCH_LENGTH_MM
            <= ball_target.x
            <= 1.0 - BALL_RADIUS_MM / PITCH_LENGTH_MM
            and BALL_RADIUS_MM / PITCH_WIDTH_MM
            <= ball_target.y
            <= 1.0 - BALL_RADIUS_MM / PITCH_WIDTH_MM
        ):
            waypoints.append(ball_target)
    return waypoints


def _ball_setup_plan(
    player_pieces: list[tuple[str, Vector2, int]],
    flicking_piece_id: str,
    ball_position: Vector2,
    obstacles: list[Obstacle],
) -> FlickPlan | None:
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
    best_plan: FlickPlan | None = None
    best_score: tuple[int, float, float, float] | None = None
    next_action_priority = {"shot": 0, "pass": 1, "advance": 1}

    for receiver_id, receiver_position, receiver_touches in teammates:
        receiver_teammates = [
            (piece_id, position)
            for piece_id, position, _ in player_pieces
            if piece_id != receiver_id
        ]
        for offset_mm in SETUP_OFFSETS_MM:
            for direction_index in range(SETUP_DIRECTIONS):
                angle = 2.0 * pi * direction_index / SETUP_DIRECTIONS
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

                setup_plan = _ball_contact_plan(
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

                next_plan = _plan_piece_flick(
                    receiver_position,
                    ball_target,
                    obstacles,
                    piece_touches_used=receiver_touches,
                    teammates=receiver_teammates,
                    advance_waypoints=_angled_advance_waypoints(ball_target),
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
                best_plan = FlickPlan(
                    piece_target=setup_plan.piece_target,
                    ball_target=setup_plan.ball_target,
                    strength=setup_plan.strength,
                    action="pass",
                    receiver_piece_id=receiver_id,
                )

    return best_plan


def _team_flick_candidates(
    player_pieces: list[tuple[str, Vector2, int]],
    ball_position: Vector2,
    obstacles: list[Obstacle],
) -> list[FlickPlan]:
    """List candidate flicks for a team attacking toward increasing X."""
    candidate_plans: list[FlickPlan] = []
    shooting_line = 1.0 - SHOOTING_AREA_DEPTH_MM / PITCH_LENGTH_MM
    has_advancing_piece = any(
        touches_used < 2 for _, _, touches_used in player_pieces
    )
    advance_waypoints = None
    if ball_position.x <= shooting_line and has_advancing_piece:
        advance_waypoints = _ball_advance_waypoints(
            ball_position,
            obstacles,
        )
    for piece_id, piece_position, touches_used in player_pieces:
        teammates = [
            (teammate_id, teammate_position)
            for teammate_id, teammate_position, _ in player_pieces
            if teammate_id != piece_id
        ]
        plan = _plan_piece_flick(
            piece_position,
            ball_position,
            obstacles,
            piece_touches_used=touches_used,
            teammates=teammates,
            advance_waypoints=advance_waypoints,
        )
        if plan is None:
            continue
        piece_plans = [plan]
        if plan.action == "shot":
            piece_plans = _shot_plans(piece_position, ball_position, obstacles)
        elif plan.action == "advance":
            piece_plans = _advances_by_distance(
                _piece_advance_plans(
                    piece_position,
                    ball_position,
                    obstacles,
                    advance_waypoints,
                ),
                ball_position,
            )
        for piece_plan in piece_plans:
            if any(
                _approach_intersects_teammate(
                    piece_position,
                    piece_plan.piece_target,
                    teammate_position,
                )
                for teammate_id, teammate_position, _ in player_pieces
                if teammate_id != piece_id
            ):
                continue
            candidate_plans.append(
                FlickPlan(
                    piece_target=piece_plan.piece_target,
                    ball_target=piece_plan.ball_target,
                    strength=piece_plan.strength,
                    action=piece_plan.action,
                    receiver_piece_id=piece_plan.receiver_piece_id,
                    flicking_piece_id=piece_id,
                )
            )

    if not any(plan.action == "shot" for plan in candidate_plans):
        for piece_id, _, touches_used in player_pieces:
            if touches_used != 2:
                continue
            setup_plan = _ball_setup_plan(
                player_pieces,
                piece_id,
                ball_position,
                obstacles,
            )
            if setup_plan is not None:
                candidate_plans.append(
                    FlickPlan(
                        piece_target=setup_plan.piece_target,
                        ball_target=setup_plan.ball_target,
                        strength=setup_plan.strength,
                        action="setup",
                        receiver_piece_id=setup_plan.receiver_piece_id,
                        flicking_piece_id=piece_id,
                    )
                )

    shot_plans = sorted(
        (plan for plan in candidate_plans if plan.action == "shot"),
        key=lambda plan: plan.strength,
    )
    setup_plans = sorted(
        (plan for plan in candidate_plans if plan.action == "setup"),
        key=lambda plan: plan.strength,
    )
    possession_plans = sorted(
        (
            plan
            for plan in candidate_plans
            if plan.action in {"advance", "pass"}
        ),
        key=lambda plan: (
            -progress_steps(
                (plan.ball_target.x - ball_position.x) * PITCH_LENGTH_MM
            ),
            plan.strength,
            distance_between_mm(ball_position, plan.ball_target),
        ),
    )
    return [*shot_plans, *setup_plans, *possession_plans]


def _plan_team_flick(
    player_pieces: list[tuple[str, Vector2, int]],
    ball_position: Vector2,
    obstacles: list[Obstacle],
) -> FlickPlan | None:
    """Choose the best next flick for a team attacking toward increasing X."""
    candidates = _team_flick_candidates(
        player_pieces,
        ball_position,
        obstacles,
    )
    return candidates[0] if candidates else None


def plan_team_flick_candidates(
    player_pieces: list[tuple[str, Vector2, int]],
    ball_position: Vector2,
    obstacles: list[Obstacle] | None = None,
    *,
    attack_direction: int = ATTACK_TOWARD_INCREASING_X,
) -> list[FlickPlan]:
    """List every safe candidate flick for a team, best first.

    The order follows the attacker priorities: shots, then setup passes, then
    advances and passes, each by lower flick strength. A piece that can shoot
    offers one shot per aim point across the goal mouth. Setup passes are only
    generated when no shot is available.

    Args:
        player_pieces: Identifier, normalized position, and consecutive touch
            count for each piece of the attacking team.
        ball_position: Normalized ball position.
        obstacles: Areas that piece and ball paths must avoid.
        attack_direction: ``1`` to attack toward increasing X or ``-1`` to
            attack toward decreasing X.

    Returns:
        list[FlickPlan]: Candidates with their flicking piece identifiers,
            possibly empty.

    Raises:
        ValueError: If the attack direction is not ``1`` or ``-1``.
    """
    direction = _validated_direction(attack_direction)
    mirror = direction == ATTACK_TOWARD_DECREASING_X
    candidates = _team_flick_candidates(
        [
            (piece_id, _mirror_position(position, mirror), touches_used)
            for piece_id, position, touches_used in player_pieces
        ],
        _mirror_position(ball_position, mirror),
        _mirror_obstacles(obstacles or [], mirror),
    )
    return [
        mirrored
        for plan in candidates
        if (mirrored := _mirror_plan(plan, mirror)) is not None
    ]


def plan_team_flick(
    player_pieces: list[tuple[str, Vector2, int]],
    ball_position: Vector2,
    obstacles: list[Obstacle] | None = None,
    *,
    attack_direction: int = ATTACK_TOWARD_INCREASING_X,
) -> FlickPlan | None:
    """Choose the safest available piece for the next ball-contact flick.

    Args:
        player_pieces: Identifier, normalized position, and consecutive touch
            count for each piece of the attacking team.
        ball_position: Normalized ball position.
        obstacles: Areas that piece and ball paths must avoid.
        attack_direction: ``1`` to attack toward increasing X or ``-1`` to
            attack toward decreasing X. Use ``sim_physics.attack_direction``
            to derive it from a team.

    Returns:
        FlickPlan | None: The chosen plan with its flicking piece identifier,
            or ``None`` if no piece has a safe route.

    Raises:
        ValueError: If the attack direction is not ``1`` or ``-1``.
    """
    direction = _validated_direction(attack_direction)
    mirror = direction == ATTACK_TOWARD_DECREASING_X
    plan = _plan_team_flick(
        [
            (piece_id, _mirror_position(position, mirror), touches_used)
            for piece_id, position, touches_used in player_pieces
        ],
        _mirror_position(ball_position, mirror),
        _mirror_obstacles(obstacles or [], mirror),
    )
    return _mirror_plan(plan, mirror)

def sample_flick_candidates(
    piece_id: str,
    piece_position: Vector2,
    ball_position: Vector2,
    obstacles: list[Obstacle] | None = None,
) -> list[FlickPlan]:
    """Generate exploratory flicks from one piece toward the ball.

    Each candidate aims the piece at a point beside the ball's center, so the
    ball leaves at an angle to the piece-to-ball line, at a few strengths from
    just enough to reach the ball upward. The candidates have no direction of
    their own: whether they advance, move sideways or move backward depends on
    where the piece stands, and callers judge that from simulation.

    Args:
        piece_id: Identifier of the flicking piece.
        piece_position: Normalized piece position.
        ball_position: Normalized ball position.
        obstacles: Areas the piece's path to the ball must avoid.

    Returns:
        list[FlickPlan]: Candidates ordered from weakest to strongest, or an
            empty list if the ball is out of range or the path is blocked.
    """
    to_ball = Vector2(
        (ball_position.x - piece_position.x) * PITCH_LENGTH_MM,
        (ball_position.y - piece_position.y) * PITCH_WIDTH_MM,
    )
    distance_mm = to_ball.length
    if distance_mm == 0.0:
        return []

    gap_mm = max(0.0, distance_mm - PIECE_RADIUS_MM - BALL_RADIUS_MM)
    needed_strength = (
        sqrt(2.0 * PIECE_FRICTION_MM_S2 * gap_mm) / MAX_FLICK_SPEED_MM_S
    )
    if needed_strength > 1.0:
        return []
    clearance = max(
        PIECE_RADIUS_MM / PITCH_LENGTH_MM,
        BALL_RADIUS_MM / PITCH_WIDTH_MM,
    )
    if obstacles and not _segment_is_clear(
        piece_position,
        ball_position,
        obstacles,
        clearance,
    ):
        return []

    base_strength = max(SAMPLE_MIN_STRENGTH, needed_strength)
    strengths = sorted(
        {
            round(min(1.0, base_strength * multiplier), 4)
            for multiplier in SAMPLE_STRENGTH_MULTIPLIERS
        }
    )
    direction = to_ball.normalized()
    sideways = Vector2(-direction.y, direction.x)
    candidates: list[FlickPlan] = []
    for strength in strengths:
        for offset_mm in SAMPLE_CONTACT_OFFSETS_MM:
            aim = Vector2(
                ball_position.x + sideways.x * offset_mm / PITCH_LENGTH_MM,
                ball_position.y + sideways.y * offset_mm / PITCH_WIDTH_MM,
            )
            candidates.append(
                FlickPlan(
                    piece_target=aim,
                    ball_target=ball_position,
                    strength=strength,
                    action="advance",
                    flicking_piece_id=piece_id,
                )
            )
    return candidates


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
