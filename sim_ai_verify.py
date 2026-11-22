"""Headless what-if simulation of candidate flicks.

The planners propose flicks from geometry. This module checks a proposal by
cloning the physics world, applying the flick through the same code path the
match uses, running physics until everything stops, and reporting what really
happened. Nothing here changes the world it is given.
"""

from dataclasses import dataclass

from sim_ai_brain import (
    FlickPlan,
    Obstacle,
    plan_team_flick_candidates,
    sample_flick_candidates,
)
from sim_ai_flick import distance_between_mm, flick_toward_target
from sim_physics import (
    ATTACK_TOWARD_DECREASING_X,
    PITCH_LENGTH_MM,
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
            negative when it moved back toward the team's own goal.
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
    gaps = [
        distance_between_mm(body.position, ball_position)
        - body.radius_mm
        - trial.ball.radius_mm
        for body in trial.pieces
        if body.team == team
        and body.movable
        and body.kind == "piece"
        and (
            counts.get(body.body_id, 0) + (1 if body.body_id == piece_id else 0)
            < MAX_CONSECUTIVE_TOUCHES
            or body.body_id == receiver_id
        )
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
        ball_progress_mm=(
            attack_direction(team)
            * (ball_position.x - ball_start.x)
            * PITCH_LENGTH_MM
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


def _rank_key(
    plan: FlickPlan,
    outcome: FlickOutcome,
) -> tuple[int, int, float, float]:
    """Order verified flicks: goal, setup, advance or pass, then weak shot.

    Within a category, a ball that stops within safe reach of a teammate is
    preferred, then lower flick strength, then shorter ball travel.
    """
    if outcome.goal:
        category = 0
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
        0 if near_teammate else 1,
        plan.strength,
        outcome.ball_travel_mm,
    )


def plan_verified_team_flick(
    world: PhysicsWorld,
    team: str,
    touch_counts: dict[str, int],
    obstacles: list[Obstacle] | None = None,
    *,
    max_candidates: int = MAX_VERIFIED_CANDIDATES,
    allow_sampling: bool = True,
    max_sampled_candidates: int = MAX_SAMPLED_CANDIDATES,
) -> VerifiedFlick | None:
    """Choose a flick for a team by simulating candidate flicks.

    The planner's geometric candidates are simulated first. Candidates that
    miss the ball, hit another piece before the ball, touch an opposing piece
    or lose possession are rejected, and the search stops at the first
    candidate that scores. If none survive, exploratory flicks around the ball
    are simulated instead, which can find forward, sideways or backward moves
    the planner does not propose.

    Args:
        world: The current world; it is not modified.
        team: The attacking team.
        touch_counts: Consecutive touches already used by each piece.
        obstacles: Areas the planner should avoid.
        max_candidates: Most planner candidates to simulate.
        allow_sampling: Whether to fall back to exploratory flicks.
        max_sampled_candidates: Most exploratory flicks to simulate.

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

    best: tuple[tuple[int, int, float, float], FlickPlan, FlickOutcome] | None
    best = None
    tried = 0
    for plan in candidates:
        outcome = simulate_plan(world, plan, touch_counts)
        tried += 1
        if not outcome.keeps_possession:
            continue
        key = _rank_key(plan, outcome)
        if best is None or key < best[0]:
            best = (key, plan, outcome)
        if outcome.goal:
            break
    if best is not None:
        return VerifiedFlick(best[1], best[2], tried)

    if not allow_sampling:
        return None
    sampled = _best_sampled_flick(
        world,
        attackers,
        touch_counts,
        obstacles,
        max_sampled_candidates,
    )
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
) -> tuple[int, int, float, float] | None:
    """Rank an exploratory flick, or return ``None`` if it is not worthwhile.

    Forward progress is preferred. A flick that does not advance the ball is
    only worthwhile if it leaves the ball in reach of a teammate or inside the
    shooting area, which covers a deliberate step back or sideways.
    """
    near_teammate = (
        outcome.teammate_gap_mm is not None
        and outcome.teammate_gap_mm <= SAFE_REACH_MM
    )
    if outcome.goal:
        tier = 0
    elif outcome.ball_progress_mm >= MIN_SAMPLED_PROGRESS_MM:
        tier = 1
    elif near_teammate or outcome.ball_in_shooting_area:
        tier = 2
    else:
        return None
    return (
        tier,
        0 if near_teammate else 1,
        plan.strength,
        outcome.ball_travel_mm,
    )


def _best_sampled_flick(
    world: PhysicsWorld,
    attackers: list[Body],
    touch_counts: dict[str, int],
    obstacles: list[Obstacle] | None,
    max_candidates: int,
) -> tuple[FlickPlan, FlickOutcome, int] | None:
    """Simulate exploratory flicks and return the best, with the count tried."""
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

    best: tuple[tuple[int, int, float, float], FlickPlan, FlickOutcome] | None
    best = None
    tried = 0
    for plan in candidates:
        outcome = simulate_plan(world, plan, touch_counts)
        tried += 1
        if not outcome.keeps_possession:
            continue
        key = _sampled_rank_key(plan, outcome)
        if key is None:
            continue
        if best is None or key < best[0]:
            best = (key, plan, outcome)
        if outcome.goal:
            break
    if best is None:
        return None
    return best[1], best[2], tried
