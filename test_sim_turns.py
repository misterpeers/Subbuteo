"""Focused tests for the headless attacking turn controller."""

import unittest
from unittest.mock import patch

from sim_ai_brain import FlickPlan
from sim_physics import (
    AWAY,
    BALL_RADIUS_MM,
    HOME,
    PIECE_RADIUS_MM,
    Body,
    PhysicsWorld,
    Vector2,
)
from sim_scenarios import build_world, random_setup
from sim_turns import TurnController

STEP_SECONDS = 1.0 / 60.0
MAX_UPDATES = 60 * 120


def _piece(body_id: str, team: str, position: Vector2) -> Body:
    """Create a movable player piece for a test world."""
    return Body(
        body_id=body_id,
        position=position,
        radius_mm=PIECE_RADIUS_MM,
        mass=22.0,
        team=team,
    )


def _world(pieces: list[Body], ball_position: Vector2) -> PhysicsWorld:
    """Create a world containing the given pieces and a ball."""
    ball = Body(
        body_id="ball",
        position=ball_position,
        radius_mm=BALL_RADIUS_MM,
        mass=2.7,
        kind="ball",
    )
    return PhysicsWorld(pieces, ball)


def _run_until_finished(controller: TurnController) -> list:
    """Update a controller until it records an outcome; return all events."""
    events = []
    for _ in range(MAX_UPDATES):
        events.extend(controller.update(STEP_SECONDS))
        if controller.finished:
            return events
    raise AssertionError("The controller did not finish.")


class TurnControllerTests(unittest.TestCase):
    """Check flick sequencing, possession handling, and attack direction."""

    def test_eligible_shot_scores_and_ends_the_sequence(self) -> None:
        """A piece in range of a clear goal shoots and the goal ends play."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.82, 0.5))],
            Vector2(0.85, 0.5),
        )
        controller = TurnController(world, HOME, flick_delay_seconds=0.0)

        events = _run_until_finished(controller)

        self.assertEqual(events[0].kind, "flick")
        self.assertEqual(events[0].plan.action, "shot")
        self.assertEqual(controller.outcome.kind, "goal")
        self.assertEqual(controller.outcome.team, HOME)
        self.assertEqual(world.home_score, 1)

    def test_away_team_attacks_toward_decreasing_x(self) -> None:
        """The away team's planned flick moves the ball toward X = 0."""
        world = _world(
            [_piece("away-1", AWAY, Vector2(0.18, 0.5))],
            Vector2(0.15, 0.5),
        )
        controller = TurnController(world, AWAY, flick_delay_seconds=0.0)

        events = _run_until_finished(controller)

        self.assertEqual(events[0].plan.action, "shot")
        self.assertLess(events[0].plan.ball_target.x, 0.15)
        self.assertEqual(controller.outcome.kind, "goal")
        self.assertEqual(controller.outcome.team, AWAY)
        self.assertEqual(world.away_score, 1)

    def test_a_flick_that_misses_the_ball_loses_possession(self) -> None:
        """A flick without ball contact ends the attack as a missed flick."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.4, 0.5))],
            Vector2(0.6, 0.5),
        )
        controller = TurnController(
            world,
            HOME,
            flick_delay_seconds=0.0,
            verify_flicks=False,
        )
        miss = FlickPlan(
            piece_target=Vector2(0.4, 0.9),
            ball_target=Vector2(0.6, 0.5),
            strength=0.2,
            flicking_piece_id="home-1",
        )

        with patch("sim_turns.plan_team_flick", return_value=miss):
            _run_until_finished(controller)

        self.assertEqual(controller.outcome.kind, "possession_lost")
        self.assertEqual(controller.outcome.reason, "missed_flick")
        self.assertEqual(controller.outcome.team, HOME)

    def test_ball_contact_with_an_opposing_piece_loses_possession(self) -> None:
        """The ball striking an opposing piece hands the ball over."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.4, 0.5)),
                _piece("away-1", AWAY, Vector2(0.55, 0.5)),
            ],
            Vector2(0.45, 0.5),
        )
        controller = TurnController(
            world,
            HOME,
            flick_delay_seconds=0.0,
            verify_flicks=False,
        )
        long_pass = FlickPlan(
            piece_target=Vector2(0.45, 0.5),
            ball_target=Vector2(0.6, 0.5),
            strength=0.6,
            flicking_piece_id="home-1",
        )

        with patch("sim_turns.plan_team_flick", return_value=long_pass):
            _run_until_finished(controller)

        self.assertEqual(controller.outcome.kind, "possession_lost")
        self.assertEqual(controller.outcome.reason, "opponent_contact")

    def test_hand_over_gives_the_attack_to_the_opposing_team(self) -> None:
        """With hand-over enabled, a lost ball starts the other team's attack."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.4, 0.5)),
                _piece("away-1", AWAY, Vector2(0.8, 0.5)),
            ],
            Vector2(0.6, 0.5),
        )
        controller = TurnController(
            world,
            HOME,
            flick_delay_seconds=0.0,
            hand_over_on_loss=True,
            verify_flicks=False,
        )
        miss = FlickPlan(
            piece_target=Vector2(0.4, 0.9),
            ball_target=Vector2(0.6, 0.5),
            strength=0.2,
            flicking_piece_id="home-1",
        )

        events = []
        with patch("sim_turns.plan_team_flick", return_value=miss):
            for _ in range(MAX_UPDATES):
                events.extend(controller.update(STEP_SECONDS))
                if any(event.kind == "possession_lost" for event in events):
                    break

        self.assertFalse(controller.finished)
        self.assertEqual(controller.attacking_team, AWAY)
        self.assertEqual(world.possession, AWAY)
        self.assertEqual(
            [piece.body_id for piece in controller.attacking_pieces()],
            ["away-1"],
        )
        self.assertTrue(all(count == 0 for count in controller.touch_counts.values()))

    def test_no_piece_ever_exceeds_three_consecutive_touches(self) -> None:
        """The controller never plans a fourth consecutive touch."""
        for seed in range(4):
            with self.subTest(seed=seed):
                setup = random_setup(seed)
                controller = TurnController(
                    build_world(setup),
                    setup.team,
                    flick_delay_seconds=0.0,
                )
                for _ in range(MAX_UPDATES):
                    controller.update(STEP_SECONDS)
                    self.assertLessEqual(
                        max(controller.touch_counts.values()),
                        3,
                    )
                    if controller.finished:
                        break

    def test_decision_stats_count_each_decision_by_source(self) -> None:
        """Every flick decision is timed and attributed to a source."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.82, 0.5))],
            Vector2(0.85, 0.5),
        )
        controller = TurnController(world, HOME, flick_delay_seconds=0.0)

        _run_until_finished(controller)

        stats = controller.decision_stats
        self.assertEqual(stats.decisions, 1)
        self.assertEqual(stats.planned, 1)
        self.assertEqual(stats.sampled + stats.none, 0)
        self.assertGreaterEqual(stats.durations_seconds[0], 0.0)

    def test_decision_stats_count_a_decision_with_no_move(self) -> None:
        """A decision that finds nothing is recorded as no move."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.05, 0.5))],
            Vector2(0.7, 0.5),
        )
        controller = TurnController(world, HOME, flick_delay_seconds=0.0)

        _run_until_finished(controller)

        self.assertEqual(controller.outcome.kind, "no_plan")
        self.assertEqual(controller.decision_stats.none, 1)

    def test_ball_stops_record_each_decision_and_clear_on_reset(self) -> None:
        """The controller remembers where the ball stood before each flick."""
        setup = random_setup(0)
        controller = TurnController(
            build_world(setup),
            setup.team,
            flick_delay_seconds=0.0,
        )
        for _ in range(MAX_UPDATES):
            controller.update(STEP_SECONDS)
            if controller.flicks_taken >= 2 or controller.finished:
                break

        self.assertGreaterEqual(len(controller.ball_stops), 2)
        self.assertEqual(controller.ball_stops[0], setup.ball_position)
        controller.reset()
        self.assertEqual(controller.ball_stops, [])

    def test_unknown_team_is_rejected(self) -> None:
        """A controller can only be created for a known team."""
        world = _world([], Vector2(0.5, 0.5))
        with self.assertRaises(ValueError):
            TurnController(world, "neutral")


if __name__ == "__main__":
    unittest.main()
