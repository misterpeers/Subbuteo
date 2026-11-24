"""Headless what-if simulation of candidate flicks.

The planners propose flicks from geometry. This module checks a proposal by
cloning the physics world, applying the flick through the same code path the
match uses, running physics until everything stops, and reporting what really
happened. Nothing here changes the world it is given.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt

from sim_ai_brain import (
    FlickPlan,
    Obstacle,
    plan_team_flick_candidates,
    sample_flick_candidates,
)
from sim_ai_flick import distance_between_mm, flick_toward_target
from sim_physics import (
    ATTACK_TOWARD_DECREASING_X,
    MAX_FLICK_SPEED_MM_S,
    PIECE_FRICTION_MM_S2,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    SHOOTING_AREA_DEPTH_MM,
    Body,
    PhysicsWorld,
    Vector2,
    attack_direction,
)

SIMULATION_STEP_SECONDS = 1.0 / 60.0
MAX_SIMULATION_STEPS = 600
CONTACT_TOLERANCE_MM = 1.0
PASS_MOVEMENT_THRESHOLD_MM = 3.0
MAX_CONSECUTIVE_TOUCHES = 3
MAX_VERIFIED_CANDIDATES = 12
MAX_SAMPLED_CANDIDATES = 40
MIN_SAMPLED_PROGRESS_MM = 10.0
SAFE_REACH_MM = 100.0
STEP_BACK_MM = 50.0
STEP_BACK_CATEGORY = 4
REPEAT_CATEGORY = 5
REPEAT_RADIUS_MM = 8.0
LEVEL_GOAL = 0
LEVEL_ADVANCE = 1
LEVEL_STEP_BACK = 2
LEVEL_REPEAT = 3


@dataclass(frozen=True)
class VerifiedFlick:
    """A candidate flick together with its simulated result.

    Attributes:
        plan: The chosen flick plan.
        outcome: What simulating that plan did.
        candidates_tried: How many candidates were simulated to find it.
        source: ``"planned"`` for a geometric candidate or ``"sampled"`` for
            an exploratory one.
    """

    plan: FlickPlan
    outcome: "FlickOutcome"
    candidates_tried: int
    source: str = "planned"


@dataclass(frozen=True)
class FlickOutcome:
    """Describe what a simulated flick did.

    Attributes:
        flick_applied: Whether the physics engine accepted the flick.
        ball_contacted: Whether the flicking piece touched the ball.
        opponent_contact: Whether the ball touched an opposing piece.
        possession_kept: Whether the attacking team still holds possession.
        goal: Whether the attacking team scored.
        receiver_id: Teammate the ball reached after moving, if any.
        ball_position: Where the ball stopped.
        ball_travel_mm: Distance the ball moved from its start.
        ball_in_shooting_area: Whether the ball stopped strictly inside the
            attacked goal's shooting area.
        teammate_gap_mm: Edge-to-edge gap from the stopped ball to the nearest
            teammate who may flick next, or ``None`` if there is none. The
            flicking piece counts while it has touches left after this flick.
        settled: Whether every movable body stopped within the step limit.
        touched_piece_before_ball: Whether the flicking piece hit another piece
            before it touched the ball, which is an attacking foul.
        ball_progress_mm: How far the ball moved toward the attacked goal;
            negative when it moved back toward the team's own goal. Outside
            the shooting area this is the change along the pitch length.
            When the ball starts inside the shooting area it is the reduction
            in distance to the goal-mouth center, so moving the ball along
            the goal line toward the goal counts as progress.
        next_contact_available: Whether, once everything has stopped, at
            least one teammate who may flick next can reach the ball within
            flick range along a straight path that no other piece blocks.
        forward_contact_available: Whether such a teammate also stands behind
            the ball, so its next flick can push the ball toward the attacked
            goal.
    """

    flick_applied: bool
    ball_contacted: bool
    opponent_contact: bool
    possession_kept: bool
    goal: bool
    receiver_id: str | None
    ball_position: Vector2
    ball_travel_mm: float
    ball_in_shooting_area: bool
    teammate_gap_mm: float | None
    settled: bool
    touched_piece_before_ball: bool = False
    ball_progress_mm: float = 0.0
    next_contact_available: bool = True
    forward_contact_available: bool = True

    @property
    def keeps_possession(self) -> bool:
        """Return whether the flick legally contacted the ball and kept it."""
        return (
            self.flick_applied
            and self.ball_contacted
            and not self.touched_piece_before_ball
            and not self.opponent_contact
            and self.possession_kept
        )


def _in_shooting_area(ball_position: Vector2, team: str) -> bool:
    """Return whether the ball is strictly inside the attacked shooting area."""
    boundary = SHOOTING_AREA_DEPTH_MM / PITCH_LENGTH_MM
    if attack_direction(team) == ATTACK_TOWARD_DECREASING_X:
        return ball_position.x < boundary
    return ball_position.x > 1.0 - boundary


def _to_mm(position: Vector2) -> tuple[float, float]:
    """Convert a normalized position to pitch millimeters."""
    return position.x * PITCH_LENGTH_MM, position.y * PITCH_WIDTH_MM


def _path_is_blocked(
    piece: Body,
    contact_point: tuple[float, float],
    other: Body,
) -> bool:
    """Return whether a piece sliding to a point would hit another body.

    Args:
        piece: The piece that would move.
        contact_point: Millimeter point where the piece's center would stop.
        other: A body that might lie in the way.

    Returns:
        bool: ``True`` if the moving piece would overlap ``other`` on the way.
    """
    start_x, start_y = _to_mm(piece.position)
    other_x, other_y = _to_mm(other.position)
    end_x, end_y = contact_point
    delta_x, delta_y = end_x - start_x, end_y - start_y
    length_squared = delta_x * delta_x + delta_y * delta_y
    if length_squared == 0.0:
        fraction = 0.0
    else:
        fraction = max(
            0.0,
            min(
                1.0,
                (
                    (other_x - start_x) * delta_x
                    + (other_y - start_y) * delta_y
                )
                / length_squared,
            ),
        )
    nearest_x = start_x + fraction * delta_x
    nearest_y = start_y + fraction * delta_y
    distance = sqrt((other_x - nearest_x) ** 2 + (other_y - nearest_y) ** 2)
    return distance < piece.radius_mm + other.radius_mm


def has_next_contact(
    world: PhysicsWorld,
    piece_ids: list[str],
    *,
    behind_ball_for: int | None = None,
) -> bool:
    """Return whether any listed piece can make a legal next contact.

    A piece qualifies when the ball is within its flick range and the straight
    path from the piece to the point where it would touch the ball does not
    pass through any other piece. This is a cheap, conservative test: a real
    flick may still succeed at an angle, and simulation decides when that
    flick is actually chosen.

    Args:
        world: A settled world.
        piece_ids: Pieces that may take the next flick.
        behind_ball_for: When set to an attack direction (``1`` or ``-1``),
            only pieces whose center is at least a ball radius behind the ball
            in that direction count, so their flick can push the ball forward.

    Returns:
        bool: ``True`` if at least one listed piece has a clear, in-range
            route to the ball.
    """
    ball = world.ball
    ball_x, ball_y = _to_mm(ball.position)
    for piece in world.pieces:
        if piece.body_id not in piece_ids:
            continue
        piece_x, piece_y = _to_mm(piece.position)
        if (
            behind_ball_for is not None
            and behind_ball_for * (ball_x - piece_x) < ball.radius_mm
        ):
            continue
        to_ball_x, to_ball_y = ball_x - piece_x, ball_y - piece_y
        distance = sqrt(to_ball_x * to_ball_x + to_ball_y * to_ball_y)
        if distance == 0.0:
            continue
        reach = piece.radius_mm + ball.radius_mm
        gap = max(0.0, distance - reach)
        if sqrt(2.0 * PIECE_FRICTION_MM_S2 * gap) > MAX_FLICK_SPEED_MM_S:
            continue
        contact_point = (
            ball_x - to_ball_x / distance * reach,
            ball_y - to_ball_y / distance * reach,
        )
        if not any(
            _path_is_blocked(piece, contact_point, other)
            for other in world.pieces
            if other.body_id != piece.body_id
        ):
            return True
    return False


def _ball_progress_mm(start: Vector2, end: Vector2, team: str) -> float:
    """Return how far the ball moved toward the attacked goal, in mm.

    Args:
        start: Ball position when the flick began.
        end: Ball position once everything stopped.
        team: The attacking team.

    Returns:
        float: Progress along the pitch length, or, when the ball started in
            the shooting area, the reduction in distance to the goal-mouth
            center. Negative values mean the ball moved away.
    """
    direction = attack_direction(team)
    if not _in_shooting_area(start, team):
        return direction * (end.x - start.x) * PITCH_LENGTH_MM
    goal_center = Vector2(1.0 if direction > 0 else 0.0, 0.5)
    return distance_between_mm(start, goal_center) - distance_between_mm(
        end,
        goal_center,
    )


def _everything_stopped(world: PhysicsWorld) -> bool:
    """Return whether the ball and every movable piece have stopped."""
    return world.ball.velocity.length == 0.0 and all(
        piece.velocity.length == 0.0
        for piece in world.pieces
        if piece.movable
    )


def simulate_flick(
    world: PhysicsWorld,
    piece_id: str,
    piece_target: Vector2,
    strength: float,
    touch_counts: dict[str, int] | None = None,
) -> FlickOutcome:
    """Simulate one flick on a clone of the world and report the result.

    Args:
        world: The current world; it is not modified.
        piece_id: Identifier of the flicking player piece.
        piece_target: Normalized point the piece is flicked toward.
        strength: Flick strength from 0.0 to 1.0.
        touch_counts: Consecutive touches already used by each piece. Used to
            decide which teammates may flick next. Missing pieces count as 0.

    Returns:
        FlickOutcome: What the flick did.

    Raises:
        ValueError: If the piece is unknown or has no team, or the strength is
            outside 0.0 to 1.0.
    """
    trial = world.clone()
    piece = next(
        (body for body in trial.pieces if body.body_id == piece_id),
        None,
    )
    if piece is None:
        raise ValueError(f"Unknown piece: {piece_id}")
    if piece.team is None:
        raise ValueError("The flicking piece must belong to a team.")
    team = piece.team
    counts = touch_counts or {}

    ball_start = trial.ball.position
    contacted = (
        distance_between_mm(piece.position, ball_start)
        <= piece.radius_mm + trial.ball.radius_mm + CONTACT_TOLERANCE_MM
    )
    applied = flick_toward_target(trial, piece_id, piece_target, strength)
    if not applied:
        return FlickOutcome(
            flick_applied=False,
            ball_contacted=False,
            opponent_contact=False,
            possession_kept=world.possession == team,
            goal=False,
            receiver_id=None,
            ball_position=ball_start,
            ball_travel_mm=0.0,
            ball_in_shooting_area=_in_shooting_area(ball_start, team),
            teammate_gap_mm=None,
            settled=True,
        )

    teams = {body.body_id: body.team for body in trial.pieces}
    opponent_contact = False
    touched_piece_before_ball = False
    goal = False
    receiver_id: str | None = None
    settled = False
    for _ in range(MAX_SIMULATION_STEPS):
        trial.step(SIMULATION_STEP_SECONDS)
        contacts = trial.last_ball_contacts
        if (
            not contacted
            and piece_id not in contacts
            and any(piece_id in pair for pair in trial.last_piece_contacts)
        ):
            touched_piece_before_ball = True
        if piece_id in contacts:
            contacted = True
        for body_id in contacts:
            body_team = teams[body_id]
            if body_team is not None and body_team != team:
                opponent_contact = True
        if (
            receiver_id is None
            and distance_between_mm(trial.ball.position, ball_start)
            > PASS_MOVEMENT_THRESHOLD_MM
        ):
            receiver_id = next(
                (
                    body_id
                    for body_id in contacts
                    if body_id != piece_id and teams[body_id] == team
                ),
                None,
            )
        if trial.last_goal is not None and trial.last_goal.scoring_team == team:
            goal = True
            settled = True
            break
        if _everything_stopped(trial):
            settled = True
            break

    ball_position = trial.ball.position
    next_pieces = [
        body
        for body in trial.pieces
        if body.team == team
        and body.movable
        and body.kind == "piece"
        and (
            counts.get(body.body_id, 0) + (1 if body.body_id == piece_id else 0)
            < MAX_CONSECUTIVE_TOUCHES
            or body.body_id == receiver_id
            or (receiver_id is not None and body.body_id == piece_id)
        )
    ]
    gaps = [
        distance_between_mm(body.position, ball_position)
        - body.radius_mm
        - trial.ball.radius_mm
        for body in next_pieces
    ]
    return FlickOutcome(
        flick_applied=True,
        ball_contacted=contacted,
        opponent_contact=opponent_contact,
        possession_kept=trial.possession == team,
        goal=goal,
        receiver_id=receiver_id,
        ball_position=ball_position,
        ball_travel_mm=distance_between_mm(ball_start, ball_position),
        ball_in_shooting_area=_in_shooting_area(ball_position, team),
        teammate_gap_mm=max(0.0, min(gaps)) if gaps else None,
        settled=settled,
        touched_piece_before_ball=touched_piece_before_ball,
        ball_progress_mm=_ball_progress_mm(ball_start, ball_position, team),
        next_contact_available=goal
        or has_next_contact(trial, [body.body_id for body in next_pieces]),
        forward_contact_available=goal
        or has_next_contact(
            trial,
            [body.body_id for body in next_pieces],
            behind_ball_for=attack_direction(team),
        ),
    )


def simulate_plan(
    world: PhysicsWorld,
    plan: FlickPlan,
    touch_counts: dict[str, int] | None = None,
) -> FlickOutcome:
    """Simulate a planned flick on a clone of the world.

    Args:
        world: The current world; it is not modified.
        plan: A plan whose ``flicking_piece_id`` is set.
        touch_counts: Consecutive touches already used by each piece.

    Returns:
        FlickOutcome: What the planned flick did.

    Raises:
        ValueError: If the plan does not name a flicking piece.
    """
    if plan.flicking_piece_id is None:
        raise ValueError("The plan must name a flicking piece.")
    return simulate_flick(
        world,
        plan.flicking_piece_id,
        plan.piece_target,
        plan.strength,
        touch_counts,
    )


def _is_repeat(
    outcome: FlickOutcome,
    visited_ball_positions: Sequence[Vector2],
) -> bool:
    """Return whether a flick leaves the ball where it has already stopped.

    Args:
        outcome: The simulated flick.
        visited_ball_positions: Earlier ball stop positions in this attack,
            including the current one.

    Returns:
        bool: ``True`` if the ball would stop within ``REPEAT_RADIUS_MM`` of
            any earlier stop, which signals a loop. A goal is never a repeat.
    """
    if outcome.goal:
        return False
    return any(
        distance_between_mm(outcome.ball_position, visited) < REPEAT_RADIUS_MM
        for visited in visited_ball_positions
    )


def _rank_key(
    plan: FlickPlan,
    outcome: FlickOutcome,
    visited_ball_positions: Sequence[Vector2] = (),
) -> tuple[int, int, int, float, float]:
    """Order verified flicks: goal, setup, advance or pass, weak shot, step back.

    A flick that moves the ball more than ``STEP_BACK_MM`` toward the team's
    own goal is a deliberate step back, and a flick that returns the ball to
    where it has already stopped in this attack is a repeat. Both rank after
    every other flick, the repeat last. Within a category, a flick that leaves
    a teammate behind the ball is preferred, then a ball that stops within
    safe reach of a teammate, then lower flick strength, then shorter ball
    travel.
    """
    if outcome.goal:
        category = 0
    elif _is_repeat(outcome, visited_ball_positions):
        category = REPEAT_CATEGORY
    elif outcome.ball_progress_mm < -STEP_BACK_MM:
        category = STEP_BACK_CATEGORY
    elif plan.action == "setup":
        category = 1
    elif plan.action == "shot":
        category = 3
    else:
        category = 2
    near_teammate = (
        outcome.teammate_gap_mm is not None
        and outcome.teammate_gap_mm <= SAFE_REACH_MM
    )
    return (
        category,
        0 if outcome.forward_contact_available else 1,
        0 if near_teammate else 1,
        plan.strength,
        outcome.ball_travel_mm,
    )


def _planned_level(category: int) -> int:
    """Map a planned rank category to the shared quality level.

    Args:
        category: The first element of a ``_rank_key`` result.

    Returns:
        int: One of the ``LEVEL_*`` constants.
    """
    if category == 0:
        return LEVEL_GOAL
    if category == REPEAT_CATEGORY:
        return LEVEL_REPEAT
    if category == STEP_BACK_CATEGORY:
        return LEVEL_STEP_BACK
    return LEVEL_ADVANCE


def plan_verified_team_flick(
    world: PhysicsWorld,
    team: str,
    touch_counts: dict[str, int],
    obstacles: list[Obstacle] | None = None,
    *,
    max_candidates: int = MAX_VERIFIED_CANDIDATES,
    allow_sampling: bool = True,
    max_sampled_candidates: int = MAX_SAMPLED_CANDIDATES,
    visited_ball_positions: Sequence[Vector2] = (),
) -> VerifiedFlick | None:
    """Choose a flick for a team by simulating candidate flicks.

    The planner's geometric candidates are simulated first. Candidates that
    miss the ball, hit another piece before the ball, touch an opposing piece,
    lose possession, or leave no teammate a clear next contact with the ball
    are rejected, and the search stops at the first candidate that scores.

    Planned and exploratory flicks share four quality levels: a goal; a
    forward or sideways move; a step back, which moves the ball more than
    ``STEP_BACK_MM`` toward the team's own goal; and a repeat, which returns
    the ball within ``REPEAT_RADIUS_MM`` of a position where it has already
    stopped in this attack. If no planned flick survives, or the best one is
    a step back or a repeat, exploratory flicks around the ball are simulated
    too, and the one on the better level is used, the planned flick on a tie.
    Exploratory flicks can find forward, sideways or backward moves the
    planner does not propose.

    Args:
        world: The current world; it is not modified.
        team: The attacking team.
        touch_counts: Consecutive touches already used by each piece.
        obstacles: Areas the planner should avoid.
        max_candidates: Most planner candidates to simulate.
        allow_sampling: Whether to fall back to exploratory flicks.
        max_sampled_candidates: Most exploratory flicks to simulate.
        visited_ball_positions: Where the ball has stopped earlier in this
            attack, including its current position. Used to detect loops.

    Returns:
        VerifiedFlick | None: The best verified flick, or ``None`` if every
            candidate was rejected or none exist.
    """
    attackers = [
        piece
        for piece in world.pieces
        if piece.team == team and piece.movable and piece.kind == "piece"
    ]
    candidates = plan_team_flick_candidates(
        [
            (
                piece.body_id,
                piece.position,
                touch_counts.get(piece.body_id, 0),
            )
            for piece in attackers
        ],
        world.ball.position,
        obstacles,
        attack_direction=attack_direction(team),
    )[:max_candidates]

    best: (
        tuple[tuple[int, int, int, float, float], FlickPlan, FlickOutcome]
        | None
    ) = None
    tried = 0
    for plan in candidates:
        outcome = simulate_plan(world, plan, touch_counts)
        tried += 1
        if not outcome.keeps_possession or not outcome.next_contact_available:
            continue
        key = _rank_key(plan, outcome, visited_ball_positions)
        if best is None or key < best[0]:
            best = (key, plan, outcome)
        if outcome.goal:
            break

    if best is not None:
        planned_level = _planned_level(best[0][0])
        if not allow_sampling or planned_level <= LEVEL_ADVANCE:
            return VerifiedFlick(best[1], best[2], tried)
    if not allow_sampling:
        return None

    sampled = _best_sampled_flick(
        world,
        attackers,
        touch_counts,
        obstacles,
        max_sampled_candidates,
        visited_ball_positions,
    )
    if best is not None and (sampled is None or sampled[3] >= planned_level):
        extra = sampled[2] if sampled is not None else 0
        return VerifiedFlick(best[1], best[2], tried + extra)
    if sampled is None:
        return None
    return VerifiedFlick(
        sampled[0],
        sampled[1],
        tried + sampled[2],
        source="sampled",
    )


def _sampled_rank_key(
    plan: FlickPlan,
    outcome: FlickOutcome,
    visited_ball_positions: Sequence[Vector2] = (),
) -> tuple[int, int, int, float, float] | None:
    """Rank an exploratory flick, or return ``None`` if it is not worthwhile.

    Forward progress is preferred. A flick that does not advance the ball is
    only worthwhile if it leaves the ball in reach of a teammate or inside the
    shooting area, which covers a deliberate step back or sideways. Among
    flicks on the same tier, one that leaves a teammate behind the ball is
    preferred, so a step back sets up a forward move. A flick that returns the
    ball to a position where it has already stopped ranks last.
    """
    near_teammate = (
        outcome.teammate_gap_mm is not None
        and outcome.teammate_gap_mm <= SAFE_REACH_MM
    )
    if outcome.goal:
        tier = 0
    elif _is_repeat(outcome, visited_ball_positions):
        tier = 3
    elif outcome.ball_progress_mm >= MIN_SAMPLED_PROGRESS_MM:
        tier = 1
    elif near_teammate or outcome.ball_in_shooting_area:
        tier = 2
    else:
        return None
    return (
        tier,
        0 if outcome.forward_contact_available else 1,
        0 if near_teammate else 1,
        plan.strength,
        outcome.ball_travel_mm,
    )


def _sampled_level(
    key: tuple[int, int, int, float, float],
    outcome: FlickOutcome,
) -> int:
    """Map an exploratory flick's rank to the shared quality level.

    Args:
        key: The flick's ``_sampled_rank_key`` result.
        outcome: The flick's simulated outcome.

    Returns:
        int: One of the ``LEVEL_*`` constants.
    """
    if key[0] == 0:
        return LEVEL_GOAL
    if key[0] == 3:
        return LEVEL_REPEAT
    if outcome.ball_progress_mm < -STEP_BACK_MM:
        return LEVEL_STEP_BACK
    return LEVEL_ADVANCE


def _best_sampled_flick(
    world: PhysicsWorld,
    attackers: list[Body],
    touch_counts: dict[str, int],
    obstacles: list[Obstacle] | None,
    max_candidates: int,
    visited_ball_positions: Sequence[Vector2] = (),
) -> tuple[FlickPlan, FlickOutcome, int, int] | None:
    """Simulate exploratory flicks and return the best.

    Args:
        world: The current world; it is not modified.
        attackers: The attacking team's player pieces.
        touch_counts: Consecutive touches already used by each piece.
        obstacles: Areas a piece's path to the ball must avoid.
        max_candidates: Most exploratory flicks to simulate.
        visited_ball_positions: Earlier ball stop positions in this attack.

    Returns:
        tuple | None: The plan, its outcome, the number of flicks simulated
            and the plan's shared quality level, or ``None`` if no exploratory
            flick is worthwhile.
    """
    candidates: list[FlickPlan] = []
    for piece in attackers:
        if touch_counts.get(piece.body_id, 0) >= MAX_CONSECUTIVE_TOUCHES:
            continue
        candidates.extend(
            sample_flick_candidates(
                piece.body_id,
                piece.position,
                world.ball.position,
                obstacles,
            )
        )
    candidates.sort(key=lambda plan: plan.strength)
    candidates = candidates[:max_candidates]

    best: (
        tuple[tuple[int, int, int, float, float], FlickPlan, FlickOutcome]
        | None
    ) = None
    tried = 0
    for plan in candidates:
        outcome = simulate_plan(world, plan, touch_counts)
        tried += 1
        if not outcome.keeps_possession or not outcome.next_contact_available:
            continue
        key = _sampled_rank_key(plan, outcome, visited_ball_positions)
        if key is None:
            continue
        if best is None or key < best[0]:
            best = (key, plan, outcome)
        if outcome.goal:
            break
    if best is None:
        return None
    return best[1], best[2], tried, _sampled_level(best[0], best[2])
