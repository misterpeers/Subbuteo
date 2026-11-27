"""Headless scenario harness for measuring the attacking AI.

The harness builds worlds from plain setup descriptions, runs them through the
same turn controller, planner and physics used everywhere else, and reports
outcomes. Random setups are seeded per scenario so any failure can be
reproduced exactly from its seed.
"""

import argparse
from collections import Counter
from dataclasses import dataclass, field
from math import ceil
from random import Random

from sim_ai_brain import Obstacle
from sim_physics import (
    BALL_FRICTION_MM_S2,
    BALL_RADIUS_MM,
    HOME,
    PIECE_FRICTION_MM_S2,
    PIECE_RADIUS_MM,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    Body,
    PhysicsWorld,
    Vector2,
    attack_direction,
    opposing_team,
)
from sim_turns import TurnController

DEFAULT_STEP_SECONDS = 1.0 / 60.0
DEFAULT_MAX_FLICKS = 30
DEFAULT_MAX_SECONDS = 600.0
MINIMUM_SEPARATION_MM = 2.0 * PIECE_RADIUS_MM + 6.0
FAILURE_SEEDS_SHOWN = 10
BLOCKER_MIN_BALL_GAP_MM = 60.0
BLOCKER_MAX_X = 0.92


@dataclass(frozen=True)
class ScenarioSetup:
    """Describe a starting position for one team's attack.

    Positions are normalized pitch coordinates.

    Attributes:
        team: The attacking team.
        piece_positions: Starting positions of the attacking player pieces.
        ball_position: Starting position of the ball.
        obstacles: Areas the AI should avoid when planning.
        blocker_positions: Starting positions of opposing player pieces that
            stand still (test blockers; a full match does not use them). The
            ball touching one loses possession as usual.
    """

    team: str
    piece_positions: tuple[Vector2, ...]
    ball_position: Vector2
    obstacles: tuple[Obstacle, ...] = ()
    blocker_positions: tuple[Vector2, ...] = ()


@dataclass(frozen=True)
class ScenarioResult:
    """Summarise how one scenario ended.

    Attributes:
        outcome: ``goal``, ``possession_lost``, ``no_plan``, ``flick_failed``,
            ``flick_limit`` or ``timeout``.
        reason: Detail for a lost possession, if any.
        flicks: Number of flicks taken.
        elapsed_seconds: Simulated time used.
        decision_seconds: Wall-clock time taken by each flick decision.
        planned_decisions: Decisions that used a planner candidate.
        sampled_decisions: Decisions that fell back to a sampled flick.
        no_move_decisions: Decisions that found no usable flick.
    """

    outcome: str
    reason: str | None
    flicks: int
    elapsed_seconds: float
    decision_seconds: tuple[float, ...] = ()
    planned_decisions: int = 0
    sampled_decisions: int = 0
    no_move_decisions: int = 0


@dataclass
class BatchSummary:
    """Aggregate results over many scenarios.

    Attributes:
        results: Result for each scenario, keyed by its seed.
        outcomes: Count of each outcome label, with any loss reason appended.
    """

    results: dict[int, ScenarioResult] = field(default_factory=dict)
    outcomes: Counter[str] = field(default_factory=Counter)

    @property
    def total(self) -> int:
        """Return the number of scenarios run."""
        return len(self.results)

    @property
    def goal_rate(self) -> float:
        """Return the fraction of scenarios that ended in a goal."""
        return self.outcomes["goal"] / self.total if self.total else 0.0

    @property
    def mean_goal_flicks(self) -> float:
        """Return the mean flicks taken in scenarios that scored."""
        goal_flicks = [
            result.flicks
            for result in self.results.values()
            if result.outcome == "goal"
        ]
        return sum(goal_flicks) / len(goal_flicks) if goal_flicks else 0.0

    def failing_seeds(self) -> list[int]:
        """Return the seeds of scenarios that did not end in a goal."""
        return [
            seed
            for seed, result in self.results.items()
            if result.outcome != "goal"
        ]

    @property
    def decision_count(self) -> int:
        """Return the number of flick decisions made across all scenarios."""
        return sum(len(r.decision_seconds) for r in self.results.values())

    @property
    def planned_decisions(self) -> int:
        """Return decisions that used a geometric planner candidate."""
        return sum(r.planned_decisions for r in self.results.values())

    @property
    def sampled_decisions(self) -> int:
        """Return decisions that fell back to a sampled flick."""
        return sum(r.sampled_decisions for r in self.results.values())

    @property
    def no_move_decisions(self) -> int:
        """Return decisions that found no usable flick."""
        return sum(r.no_move_decisions for r in self.results.values())

    def _all_decision_ms(self) -> list[float]:
        """Return every decision duration in milliseconds, sorted."""
        return sorted(
            seconds * 1000.0
            for result in self.results.values()
            for seconds in result.decision_seconds
        )

    @property
    def mean_decision_ms(self) -> float:
        """Return the mean decision time in milliseconds."""
        durations = self._all_decision_ms()
        return sum(durations) / len(durations) if durations else 0.0

    def decision_ms_percentile(self, percent: float) -> float:
        """Return a decision-time percentile in milliseconds.

        Args:
            percent: Percentile from 0 to 100; 100 gives the slowest decision.

        Returns:
            float: The nearest-rank percentile, or 0.0 with no decisions.

        Raises:
            ValueError: If the percentile is outside 0 to 100.
        """
        if not 0.0 <= percent <= 100.0:
            raise ValueError("Percentile must be between 0 and 100.")
        durations = self._all_decision_ms()
        if not durations:
            return 0.0
        index = max(0, ceil(percent / 100.0 * len(durations)) - 1)
        return durations[index]


def build_world(setup: ScenarioSetup) -> PhysicsWorld:
    """Create a physics world from a scenario setup.

    Args:
        setup: The starting position to build.

    Returns:
        PhysicsWorld: A world with the team's pieces, any opposing blockers
            and a ball.
    """
    opponent = opposing_team(setup.team)
    blockers = [
        Body(
            body_id=f"{opponent}-b{index + 1}",
            position=position,
            radius_mm=PIECE_RADIUS_MM,
            mass=22.0,
            team=opponent,
            friction_mm_s2=PIECE_FRICTION_MM_S2,
        )
        for index, position in enumerate(setup.blocker_positions)
    ]
    pieces = [
        Body(
            body_id=f"{setup.team}-{index + 1}",
            position=position,
            radius_mm=PIECE_RADIUS_MM,
            mass=22.0,
            team=setup.team,
            friction_mm_s2=PIECE_FRICTION_MM_S2,
        )
        for index, position in enumerate(setup.piece_positions)
    ]
    ball = Body(
        body_id="ball",
        position=setup.ball_position,
        radius_mm=BALL_RADIUS_MM,
        mass=2.7,
        kind="ball",
        friction_mm_s2=BALL_FRICTION_MM_S2,
    )
    return PhysicsWorld(pieces + blockers, ball)


def run_scenario(
    setup: ScenarioSetup,
    *,
    max_flicks: int = DEFAULT_MAX_FLICKS,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    step_seconds: float = DEFAULT_STEP_SECONDS,
    verify_flicks: bool = True,
) -> ScenarioResult:
    """Play one attacking sequence to its end.

    Args:
        setup: The starting position.
        max_flicks: Flicks allowed before the run is abandoned.
        max_seconds: Simulated seconds allowed before the run is abandoned.
        step_seconds: Simulation step used for each controller update.
        verify_flicks: Whether the controller simulates each planned flick
            before using it.

    Returns:
        ScenarioResult: How the sequence ended.
    """
    world = build_world(setup)
    controller = TurnController(
        world,
        setup.team,
        flick_delay_seconds=0.0,
        verify_flicks=verify_flicks,
    )
    obstacles = list(setup.obstacles)
    elapsed = 0.0

    def finish(outcome: str, reason: str | None) -> ScenarioResult:
        """Build the result using the controller's current statistics."""
        stats = controller.decision_stats
        return ScenarioResult(
            outcome=outcome,
            reason=reason,
            flicks=controller.flicks_taken,
            elapsed_seconds=elapsed,
            decision_seconds=tuple(stats.durations_seconds),
            planned_decisions=stats.planned,
            sampled_decisions=stats.sampled,
            no_move_decisions=stats.none,
        )

    while elapsed < max_seconds:
        controller.update(step_seconds, obstacles)
        elapsed += step_seconds
        outcome = controller.outcome
        if outcome is not None:
            return finish(outcome.kind, outcome.reason)
        if controller.flicks_taken > max_flicks:
            return finish("flick_limit", None)
    return finish("timeout", None)


def random_setup(
    seed: int,
    team: str = HOME,
    piece_count: int = 3,
    blocker_count: int = 0,
) -> ScenarioSetup:
    """Generate a reproducible random starting position.

    Positions are drawn in the team's own attacking frame and mirrored for a
    team that attacks toward decreasing X, so both teams face equivalent
    problems for the same seed. Blockers come from a separate generator, so
    the attacking pieces and ball are the same for a seed whatever the
    blocker count. Each blocker stands between the ball and the attacked
    goal line (up to ``BLOCKER_MAX_X``), at least
    ``BLOCKER_MIN_BALL_GAP_MM`` from the ball and clear of every other body.

    Args:
        seed: Seed that fully determines the setup.
        team: The attacking team.
        piece_count: Number of attacking player pieces.
        blocker_count: Number of static opposing pieces to add.

    Returns:
        ScenarioSetup: The generated setup.

    Raises:
        ValueError: If the piece count is below one.
    """
    if piece_count < 1:
        raise ValueError("At least one piece is required.")
    if blocker_count < 0:
        raise ValueError("The blocker count cannot be negative.")
    rng = Random(seed)
    placed: list[Vector2] = []

    def sample(
        min_x: float,
        max_x: float,
        source: Random = rng,
    ) -> Vector2:
        """Draw a position that does not overlap any already placed body."""
        while True:
            candidate = Vector2(
                source.uniform(min_x, max_x),
                source.uniform(0.1, 0.9),
            )
            if all(
                Vector2(
                    (candidate.x - other.x) * PITCH_LENGTH_MM,
                    (candidate.y - other.y) * PITCH_WIDTH_MM,
                ).length
                >= MINIMUM_SEPARATION_MM
                for other in placed
            ):
                placed.append(candidate)
                return candidate

    ball = sample(0.3, 0.75)
    pieces = [sample(0.1, 0.7) for _ in range(piece_count)]
    blocker_rng = Random(f"blockers:{seed}")
    blockers: list[Vector2] = []
    while len(blockers) < blocker_count:
        candidate = sample(
            min(ball.x, BLOCKER_MAX_X - 0.01),
            BLOCKER_MAX_X,
            blocker_rng,
        )
        gap = Vector2(
            (candidate.x - ball.x) * PITCH_LENGTH_MM,
            (candidate.y - ball.y) * PITCH_WIDTH_MM,
        ).length
        if gap < BLOCKER_MIN_BALL_GAP_MM:
            placed.remove(candidate)
            continue
        blockers.append(candidate)
    if attack_direction(team) < 0:
        ball = Vector2(1.0 - ball.x, ball.y)
        pieces = [Vector2(1.0 - piece.x, piece.y) for piece in pieces]
        blockers = [Vector2(1.0 - piece.x, piece.y) for piece in blockers]
    return ScenarioSetup(
        team=team,
        piece_positions=tuple(pieces),
        ball_position=ball,
        blocker_positions=tuple(blockers),
    )


def run_batch(
    count: int,
    *,
    seed: int = 0,
    team: str = HOME,
    piece_count: int = 3,
    max_flicks: int = DEFAULT_MAX_FLICKS,
    verify_flicks: bool = True,
    blocker_count: int = 0,
) -> BatchSummary:
    """Run many seeded random scenarios and collect their results.

    Args:
        count: Number of scenarios to run.
        seed: First seed; scenario ``n`` uses ``seed + n``.
        team: The attacking team.
        piece_count: Number of attacking player pieces per scenario.
        max_flicks: Flicks allowed per scenario.
        verify_flicks: Whether flicks are simulated before use.
        blocker_count: Static opposing pieces per scenario (testing only).

    Returns:
        BatchSummary: Per-seed results and outcome counts.
    """
    summary = BatchSummary()
    for offset in range(count):
        scenario_seed = seed + offset
        result = run_scenario(
            random_setup(scenario_seed, team, piece_count, blocker_count),
            max_flicks=max_flicks,
            verify_flicks=verify_flicks,
        )
        summary.results[scenario_seed] = result
        label = (
            result.outcome
            if result.reason is None
            else f"{result.outcome}:{result.reason}"
        )
        summary.outcomes[label] += 1
    return summary


def format_summary(summary: BatchSummary) -> str:
    """Render a batch summary as readable text.

    Args:
        summary: The batch to describe.

    Returns:
        str: Multi-line report including seeds to reproduce failures.
    """
    lines = [
        f"Scenarios: {summary.total}",
        f"Goal rate: {summary.goal_rate:.1%}",
        f"Mean flicks per goal: {summary.mean_goal_flicks:.1f}",
        "Outcomes:",
    ]
    lines.extend(
        f"  {label}: {number}"
        for label, number in sorted(summary.outcomes.items())
    )
    if summary.decision_count:
        lines.extend(
            [
                f"Decisions: {summary.decision_count} "
                f"(planned {summary.planned_decisions}, "
                f"sampled fallback {summary.sampled_decisions}, "
                f"no move {summary.no_move_decisions})",
                f"Decision time ms: mean {summary.mean_decision_ms:.0f}, "
                f"median {summary.decision_ms_percentile(50):.0f}, "
                f"p95 {summary.decision_ms_percentile(95):.0f}, "
                f"max {summary.decision_ms_percentile(100):.0f}",
            ]
        )
    failing = summary.failing_seeds()
    if failing:
        shown = ", ".join(str(seed) for seed in failing[:FAILURE_SEEDS_SHOWN])
        lines.append(f"First failing seeds: {shown}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """Run a batch from the command line and print its summary.

    Args:
        argv: Optional argument list; defaults to ``sys.argv``.
    """
    parser = argparse.ArgumentParser(
        description="Measure the attacking AI over seeded random scenarios.",
    )
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--team", choices=("home", "away"), default="home")
    parser.add_argument("--pieces", type=int, default=3)
    parser.add_argument("--max-flicks", type=int, default=DEFAULT_MAX_FLICKS)
    parser.add_argument(
        "--blockers",
        type=int,
        default=0,
        help="Static opposing pieces between the ball and the goal (testing).",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Use the planner's first choice without simulating it first.",
    )
    arguments = parser.parse_args(argv)
    summary = run_batch(
        arguments.count,
        seed=arguments.seed,
        team=arguments.team,
        piece_count=arguments.pieces,
        max_flicks=arguments.max_flicks,
        verify_flicks=not arguments.no_verify,
        blocker_count=arguments.blockers,
    )
    print(format_summary(summary))


if __name__ == "__main__":
    main()
