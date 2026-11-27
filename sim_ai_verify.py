"""Headless what-if simulation of candidate flicks.

The planners propose flicks from geometry. This module checks a proposal by
cloning the physics world, applying the flick through the same code path the
match uses, running physics until everything stops, and reporting what really
happened. Nothing here changes the world it is given.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import sqrt

from sim_ai_brain import (
    FlickPlan,
    Obstacle,
    bank_pass_candidates,
    block_flick_cap,
    plan_team_flick_candidates,
    progress_steps,
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

_RankKey = tuple[int, int, int, int, int, float, float]

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
DEAD_END_CATEGORY = 6
MAX_SHOT_CHECKS = 3
LONG_SAMPLE_STRENGTHS = (0.5, 0.7, 0.9)
BANK_ONLY_WHEN_NO_DIRECT = True
MAX_BANK_CANDIDATES = 20
LEVEL_GOAL = 0
LEVEL_ADVANCE = 1
LEVEL_STEP_BACK = 2
LEVEL_REPEAT = 3
LEVEL_DEAD_END = 4


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
        dead_end: Whether the flick leaves the attack with no way to go on
            after one more touch: it did not score, the ball stopped outside
            the shooting area, the flicking piece kept the ball and will have
            only its final touch left, and no other piece of the team is
            within flick range of the ball. That final touch can then neither
            shoot nor pass, so the attack would stall.
        needs_shot_check: Whether the flick leaves the flicking piece alone
            on its final touch, as for ``dead_end``, but with the ball inside
            the shooting area. The attack then goes on only if that final
            touch can score, which the chooser checks by looking one flick
            ahead.
        exposed: Whether an opposing piece could put itself between the
            next attacking piece and the ball with one block-flick within
            its strength cap (``block_flick_cap``), so the attack could lose
            its route to the ball. Always ``False`` for a goal or when there
            are no opposing field pieces.
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
    dead_end: bool = False
    needs_shot_check: bool = False
    exposed: bool = False

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


def _within_flick_range(piece: Body, ball: Body) -> bool:
    """Return whether a full-strength flick could carry a piece to the ball.

    Other pieces in the way are ignored.

    Args:
        piece: The piece that would flick.
        ball: The ball.

    Returns:
        bool: ``True`` if the edge-to-edge gap can be covered by a flick of
            at most full strength.
    """
    gap = max(
        0.0,
        distance_between_mm(piece.position, ball.position)
        - piece.radius_mm
        - ball.radius_mm,
    )
    return sqrt(2.0 * PIECE_FRICTION_MM_S2 * gap) <= MAX_FLICK_SPEED_MM_S


def _is_isolated_final_touch(
    world: PhysicsWorld,
    team: str,
    piece_id: str,
    touches_after_flick: int,
    receiver_id: str | None,
    goal: bool,
) -> bool:
    """Return whether a settled flick leaves one piece alone on its last touch.

    Only one piece can be partway through its consecutive touches, because a
    different piece touching the ball resets the previous piece's count. This
    is true when that piece kept the ball, will be on its final touch, and no
    other piece of the team is within flick range of the ball, so the final
    touch cannot be a pass. The attack can then only go on with a goal: the
    caller treats the flick as a dead end when the ball is outside the
    shooting area, and checks for a scoring shot when it is inside.

    Args:
        world: The settled trial world after the flick.
        team: The attacking team.
        piece_id: The piece that flicked.
        touches_after_flick: That piece's consecutive touches including this
            flick.
        receiver_id: The teammate the ball reached, if any; a pass resets the
            flicking piece's count, so it is never a dead end.
        goal: Whether the flick scored.

    Returns:
        bool: ``True`` if the piece is left alone on its final touch.
    """
    if goal or receiver_id is not None:
        return False
    if touches_after_flick != MAX_CONSECUTIVE_TOUCHES - 1:
        return False
    return not any(
        _within_flick_range(body, world.ball)
        for body in world.pieces
        if body.team == team
        and body.movable
        and body.kind == "piece"
        and body.body_id != piece_id
    )


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
        if not _within_flick_range(piece, ball):
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


def _flick_reach_mm(strength: float) -> float:
    """Return how far a piece slides when flicked at a strength.

    Args:
        strength: Flick strength from 0.0 to 1.0.

    Returns:
        float: Sliding distance in millimeters before friction stops it.
    """
    speed = strength * MAX_FLICK_SPEED_MM_S
    return speed * speed / (2.0 * PIECE_FRICTION_MM_S2)


def _distance_to_segment_mm(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Return the distance from a point to a line segment, in millimeters.

    Args:
        point: The point, in millimeters.
        start: One end of the segment, in millimeters.
        end: The other end of the segment, in millimeters.

    Returns:
        float: The shortest distance from the point to the segment.
    """
    delta_x, delta_y = end[0] - start[0], end[1] - start[1]
    length_squared = delta_x * delta_x + delta_y * delta_y
    fraction = 0.0
    if length_squared > 0.0:
        fraction = max(
            0.0,
            min(
                1.0,
                (
                    (point[0] - start[0]) * delta_x
                    + (point[1] - start[1]) * delta_y
                )
                / length_squared,
            ),
        )
    nearest_x = start[0] + fraction * delta_x
    nearest_y = start[1] + fraction * delta_y
    return sqrt((point[0] - nearest_x) ** 2 + (point[1] - nearest_y) ** 2)


def is_exposed(
    world: PhysicsWorld,
    team: str,
    next_pieces: Sequence[Body],
) -> bool:
    """Return whether a defender could block the next attacking contact.

    The next attacking piece is the nearest piece, among those that may flick
    next, that stands behind the ball (so it can push the ball forward), or
    the nearest of them if none stands behind it. The gap is the segment from
    that piece's center to the ball's center. The position is exposed if any
    opposing field piece could slide its base onto that segment with one
    block-flick at its strength cap, which grows with its distance from the
    ball (``block_flick_cap``). This is a quick, cautious estimate: it does
    not check that the blocking flick would itself be legal.

    Args:
        world: A settled world.
        team: The attacking team.
        next_pieces: The attacking pieces that may take the next flick.

    Returns:
        bool: ``True`` if some opposing piece could reach the gap.
    """
    opponents = [
        body
        for body in world.pieces
        if body.team is not None
        and body.team != team
        and body.movable
        and body.kind == "piece"
    ]
    if not opponents or not next_pieces:
        return False
    ball = world.ball
    ball_mm = _to_mm(ball.position)
    direction = attack_direction(team)
    behind = [
        body
        for body in next_pieces
        if direction * (ball_mm[0] - _to_mm(body.position)[0])
        >= ball.radius_mm
    ]
    nearest = min(
        behind or list(next_pieces),
        key=lambda body: distance_between_mm(body.position, ball.position),
    )
    piece_mm = _to_mm(nearest.position)
    for opponent in opponents:
        cap = block_flick_cap(
            distance_between_mm(opponent.position, ball.position)
        )
        gap = (
            _distance_to_segment_mm(_to_mm(opponent.position), piece_mm, ball_mm)
            - opponent.radius_mm
        )
        if gap <= _flick_reach_mm(cap):
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
    return _run_flick(world, piece_id, piece_target, strength, touch_counts)[0]


def _run_flick(
    world: PhysicsWorld,
    piece_id: str,
    piece_target: Vector2,
    strength: float,
    touch_counts: dict[str, int] | None = None,
) -> tuple[FlickOutcome, PhysicsWorld]:
    """Simulate one flick on a clone and return its result and the clone.

    Args:
        world: The current world; it is not modified.
        piece_id: Identifier of the flicking player piece.
        piece_target: Normalized point the piece is flicked toward.
        strength: Flick strength from 0.0 to 1.0.
        touch_counts: Consecutive touches already used by each piece.

    Returns:
        tuple[FlickOutcome, PhysicsWorld]: What the flick did, and the cloned
            world as it stood when the simulation stopped.

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
        outcome = FlickOutcome(
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
        return outcome, trial

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
    in_area = _in_shooting_area(ball_position, team)
    final_touch_alone = _is_isolated_final_touch(
        trial,
        team,
        piece_id,
        counts.get(piece_id, 0) + 1,
        receiver_id,
        goal,
    )
    outcome = FlickOutcome(
        flick_applied=True,
        ball_contacted=contacted,
        opponent_contact=opponent_contact,
        possession_kept=trial.possession == team,
        goal=goal,
        receiver_id=receiver_id,
        ball_position=ball_position,
        ball_travel_mm=distance_between_mm(ball_start, ball_position),
        ball_in_shooting_area=in_area,
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
        dead_end=final_touch_alone and not in_area,
        needs_shot_check=final_touch_alone and in_area,
        exposed=not goal and is_exposed(trial, team, next_pieces),
    )
    return outcome, trial


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
) -> _RankKey:
    """Order verified flicks: goal, setup, advance or pass, weak shot, step back.

    A flick that moves the ball more than ``STEP_BACK_MM`` toward the team's
    own goal is a deliberate step back, and a flick that returns the ball to
    where it has already stopped in this attack is a repeat. Both rank after
    every other flick, the repeat after the step back. A dead end (see
    ``FlickOutcome.dead_end``) ranks last of all, because the attack would
    stall after one more touch. Within a category the balanced,
    possession-first rule applies: possession safety first (a teammate left
    behind the ball, then a ball that stops within safe reach of a teammate,
    then a position that is not exposed to a block-flick), then more forward
    progress in ``PROGRESS_STEP_MM`` steps up to ``MAX_ADVANCE_MM``, then lower
    flick strength, then shorter ball travel.
    """
    if outcome.goal:
        category = 0
    elif outcome.dead_end:
        category = DEAD_END_CATEGORY
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
        1 if outcome.exposed else 0,
        -progress_steps(outcome.ball_progress_mm),
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
    if category == DEAD_END_CATEGORY:
        return LEVEL_DEAD_END
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
    bank_only_when_no_direct: bool = BANK_ONLY_WHEN_NO_DIRECT,
) -> VerifiedFlick | None:
    """Choose a flick for a team by simulating candidate flicks.

    The planner's geometric candidates are simulated first. Candidates that
    miss the ball, hit another piece before the ball, touch an opposing piece,
    lose possession, or leave no teammate a clear next contact with the ball
    are rejected, and the search stops at the first candidate that scores.

    Planned and exploratory flicks share five quality levels: a goal; a
    forward or sideways move; a step back, which moves the ball more than
    ``STEP_BACK_MM`` toward the team's own goal; a repeat, which returns
    the ball within ``REPEAT_RADIUS_MM`` of a position where it has already
    stopped in this attack; and a dead end, which leaves the piece on its
    final touch outside the shooting area with no teammate in range. If no
    planned flick survives, or the best one is a step back, a repeat or a
    dead end, exploratory flicks around the ball are simulated
    too, and the one on the better level is used, the planned flick on a tie.

    Bank passes (a pass off one wall, see ``bank_pass_candidates``) join the
    planned flicks only when no planned flick reached the "advance" level,
    that is no direct shot, setup, advance or pass survived simulation
    (``BANK_ONLY_WHEN_NO_DIRECT``, Q7). At most ``MAX_BANK_CANDIDATES`` are
    simulated, weakest first, and they are ranked like any other pass. There
    are no bank shots (Q31).
    Exploratory flicks can find forward, sideways or backward moves the
    planner does not propose. If nothing better than a dead end exists, the
    exploratory contacts are tried once more at the stronger
    ``LONG_SAMPLE_STRENGTHS``, which can carry the ball into the shooting
    area. A flick that leaves a lone piece on its final touch inside the
    shooting area is used only if a look one flick ahead finds a scoring
    shot (at most ``MAX_SHOT_CHECKS`` looks per decision); otherwise it
    counts as a dead end.

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
        bank_only_when_no_direct: When ``True`` (the rule for equal AI
            players), bank passes are tried only if no direct flick reached
            the advance level; when ``False``, they are always tried.

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

    checker = _ShotChecker(world, team, touch_counts, obstacles)
    planned: list[_Ranked] = []
    tried = 0
    for plan in candidates:
        outcome = simulate_plan(world, plan, touch_counts)
        tried += 1
        if not outcome.keeps_possession or not outcome.next_contact_available:
            continue
        planned.append(
            (_rank_key(plan, outcome, visited_ball_positions), plan, outcome)
        )
        if outcome.goal:
            break

    has_direct = any(
        entry[0][0] < STEP_BACK_CATEGORY for entry in planned
    )
    if not bank_only_when_no_direct or not has_direct:
        banks = bank_pass_candidates(
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
        )[:MAX_BANK_CANDIDATES]
        for plan in banks:
            outcome = simulate_plan(world, plan, touch_counts)
            tried += 1
            if not outcome.keeps_possession or not outcome.next_contact_available:
                continue
            planned.append(
                (_rank_key(plan, outcome, visited_ball_positions), plan, outcome)
            )

    best = _select(planned, checker, DEAD_END_CATEGORY)
    planned_level = LEVEL_DEAD_END + 1
    if best is not None:
        planned_level = _planned_level(best[0][0])
        if not allow_sampling or planned_level <= LEVEL_ADVANCE:
            return VerifiedFlick(best[1], best[2], tried + checker.simulated)
    if not allow_sampling:
        return None

    sampled = _best_sampled_flick(
        world,
        attackers,
        touch_counts,
        obstacles,
        max_sampled_candidates,
        visited_ball_positions,
        checker,
    )
    extra = sampled[2] if sampled is not None else 0
    sampled_level = sampled[3] if sampled is not None else LEVEL_DEAD_END + 1
    if min(planned_level, sampled_level) >= LEVEL_DEAD_END:
        long_sampled = _best_sampled_flick(
            world,
            attackers,
            touch_counts,
            obstacles,
            max_sampled_candidates,
            visited_ball_positions,
            checker,
            strengths=LONG_SAMPLE_STRENGTHS,
        )
        if long_sampled is not None:
            extra += long_sampled[2]
            if long_sampled[3] < sampled_level:
                sampled = long_sampled
                sampled_level = long_sampled[3]
    tried += extra + checker.simulated
    if best is not None and (sampled is None or sampled_level >= planned_level):
        return VerifiedFlick(best[1], best[2], tried)
    if sampled is None:
        return None
    return VerifiedFlick(sampled[0], sampled[1], tried, source="sampled")


_Ranked = tuple[_RankKey, FlickPlan, FlickOutcome]


class _ShotChecker:
    """Look one flick ahead to see whether a lone piece's final touch scores.

    A flick that leaves the flicking piece alone on its final touch inside
    the shooting area (``FlickOutcome.needs_shot_check``) keeps the attack
    going only if that final touch can score. The checker simulates the flick,
    then plans the next one on the settled result and reports whether it is a
    goal. Each check is a full planning run, so a decision has a small budget
    of checks; once it is spent, unchecked flicks are treated as dead ends.

    Attributes:
        simulated: Flicks simulated by all checks so far, for statistics.
    """

    def __init__(
        self,
        world: PhysicsWorld,
        team: str,
        touch_counts: dict[str, int],
        obstacles: list[Obstacle] | None,
        budget: int = MAX_SHOT_CHECKS,
    ) -> None:
        """Create a checker for one decision.

        Args:
            world: The current world; it is not modified.
            team: The attacking team.
            touch_counts: Consecutive touches already used by each piece.
            obstacles: Areas the planner should avoid.
            budget: Most lookahead checks allowed.
        """
        self._world = world
        self._team = team
        self._touch_counts = touch_counts
        self._obstacles = obstacles
        self._budget = budget
        self.simulated = 0

    def scores_next(self, plan: FlickPlan) -> bool:
        """Return whether the touch after a planned flick can score.

        Args:
            plan: A flick whose outcome needs a shot check.

        Returns:
            bool: ``True`` if the planner finds a verified goal after the
                flick; ``False`` if it does not, or the budget is spent.
        """
        if self._budget <= 0 or plan.flicking_piece_id is None:
            return False
        self._budget -= 1
        piece_id = plan.flicking_piece_id
        _, trial = _run_flick(
            self._world,
            piece_id,
            plan.piece_target,
            plan.strength,
            self._touch_counts,
        )
        self.simulated += 1
        counts = dict(self._touch_counts)
        counts[piece_id] = counts.get(piece_id, 0) + 1
        result = plan_verified_team_flick(
            trial,
            self._team,
            counts,
            self._obstacles,
        )
        if result is None:
            return False
        self.simulated += result.candidates_tried
        return result.outcome.goal


def _select(
    entries: list[_Ranked],
    checker: _ShotChecker,
    dead_end_head: int,
) -> _Ranked | None:
    """Return the best ranked flick, checking lone final touches for a shot.

    Entries are taken in rank order. One that needs a shot check is used only
    if the checker confirms the next touch scores; otherwise it is kept aside
    as a dead end.

    Args:
        entries: Verified flicks with their rank keys.
        checker: The decision's shot checker.
        dead_end_head: First key element that marks a dead end for this kind
            of rank key.

    Returns:
        _Ranked | None: The best usable entry; failing that, the best entry
            that failed its shot check, re-keyed as a dead end; or ``None`` if
            there are no entries.
    """
    failed: list[_Ranked] = []
    for entry in sorted(entries, key=lambda item: item[0]):
        if entry[2].needs_shot_check and not checker.scores_next(entry[1]):
            failed.append(entry)
            continue
        return entry
    if not failed:
        return None
    key, plan, outcome = failed[0]
    return (dead_end_head, *key[1:]), plan, outcome


def _sampled_rank_key(
    plan: FlickPlan,
    outcome: FlickOutcome,
    visited_ball_positions: Sequence[Vector2] = (),
) -> _RankKey | None:
    """Rank an exploratory flick, or return ``None`` if it is not worthwhile.

    Forward progress is preferred. A flick that does not advance the ball is
    only worthwhile if it leaves the ball in reach of a teammate or inside the
    shooting area, which covers a deliberate step back or sideways. Among
    flicks on the same tier, one that leaves a teammate behind the ball is
    preferred, so a step back sets up a forward move; then the same
    possession-first order as ``_rank_key`` (near a teammate, not exposed,
    more progress up to ``MAX_ADVANCE_MM``, lower strength). A flick that returns the
    ball to a position where it has already stopped ranks next to last, and a
    dead end (see ``FlickOutcome.dead_end``) ranks last.
    """
    near_teammate = (
        outcome.teammate_gap_mm is not None
        and outcome.teammate_gap_mm <= SAFE_REACH_MM
    )
    if outcome.goal:
        tier = 0
    elif outcome.dead_end:
        tier = 4
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
        1 if outcome.exposed else 0,
        -progress_steps(outcome.ball_progress_mm),
        plan.strength,
        outcome.ball_travel_mm,
    )


def _sampled_level(
    key: _RankKey,
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
    if key[0] == 4:
        return LEVEL_DEAD_END
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
    checker: _ShotChecker | None = None,
    *,
    strengths: Sequence[float] | None = None,
) -> tuple[FlickPlan, FlickOutcome, int, int] | None:
    """Simulate exploratory flicks and return the best.

    Args:
        world: The current world; it is not modified.
        attackers: The attacking team's player pieces.
        touch_counts: Consecutive touches already used by each piece.
        obstacles: Areas a piece's path to the ball must avoid.
        max_candidates: Most exploratory flicks to simulate.
        visited_ball_positions: Earlier ball stop positions in this attack.
        checker: The decision's shot checker; a new one is made if omitted.
        strengths: When given, the sampled contact points are flicked at
            these strengths instead of the usual ones. Used for the long
            reach pass that runs only when nothing better than a dead end
            exists.

    Returns:
        tuple | None: The plan, its outcome, the number of flicks simulated
            and the plan's shared quality level, or ``None`` if no exploratory
            flick is worthwhile.
    """
    if checker is None:
        team = attackers[0].team if attackers else None
        checker = _ShotChecker(world, team or "", touch_counts, obstacles)
    candidates: list[FlickPlan] = []
    for piece in attackers:
        if touch_counts.get(piece.body_id, 0) >= MAX_CONSECUTIVE_TOUCHES:
            continue
        sampled = sample_flick_candidates(
            piece.body_id,
            piece.position,
            world.ball.position,
            obstacles,
        )
        if strengths is None:
            candidates.extend(sampled)
            continue
        if not sampled:
            continue
        weakest = sampled[0].strength
        contacts = [plan for plan in sampled if plan.strength == weakest]
        candidates.extend(
            replace(plan, strength=strength)
            for strength in strengths
            if strength > weakest
            for plan in contacts
        )
    candidates.sort(key=lambda plan: plan.strength)
    candidates = candidates[:max_candidates]

    entries: list[_Ranked] = []
    tried = 0
    for plan in candidates:
        outcome = simulate_plan(world, plan, touch_counts)
        tried += 1
        if not outcome.keeps_possession or not outcome.next_contact_available:
            continue
        key = _sampled_rank_key(plan, outcome, visited_ball_positions)
        if key is None:
            continue
        entries.append((key, plan, outcome))
        if outcome.goal:
            break
    best = _select(entries, checker, 4)
    if best is None:
        return None
    return best[1], best[2], tried, _sampled_level(best[0], best[2])
