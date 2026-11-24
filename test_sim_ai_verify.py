"""Focused tests for headless what-if flick simulation."""

import unittest

from sim_ai_brain import FlickPlan, plan_team_flick_candidates
from sim_ai_verify import (
    REPEAT_CATEGORY,
    STEP_BACK_CATEGORY,
    FlickOutcome,
    _ball_progress_mm,
    _rank_key,
    has_next_contact,
    plan_verified_team_flick,
    simulate_flick,
    simulate_plan,
)
from sim_physics import (
    AWAY,
    BALL_FRICTION_MM_S2,
    BALL_RADIUS_MM,
    HOME,
    PIECE_RADIUS_MM,
    Body,
    PhysicsWorld,
    Vector2,
)


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
    """Create a world with the given pieces and a ball."""
    ball = Body(
        body_id="ball",
        position=ball_position,
        radius_mm=BALL_RADIUS_MM,
        mass=2.7,
        kind="ball",
        friction_mm_s2=BALL_FRICTION_MM_S2,
    )
    return PhysicsWorld(pieces, ball)


class SimulateFlickTests(unittest.TestCase):
    """Check that simulated outcomes match what the physics really does."""

    def test_clear_shot_is_reported_as_a_goal(self) -> None:
        """A shot from inside the shooting area scores in the simulation."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.82, 0.5))],
            Vector2(0.85, 0.5),
        )

        outcome = simulate_flick(world, "home-1", Vector2(1.02, 0.5), 0.75)

        self.assertTrue(outcome.goal)
        self.assertTrue(outcome.ball_contacted)
        self.assertTrue(outcome.keeps_possession)

    def test_simulation_leaves_the_original_world_untouched(self) -> None:
        """The world passed in is never modified by a what-if run."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.4, 0.5))],
            Vector2(0.45, 0.5),
        )

        simulate_flick(world, "home-1", Vector2(0.45, 0.5), 0.4)

        self.assertEqual(world.pieces[0].position, Vector2(0.4, 0.5))
        self.assertEqual(world.ball.position, Vector2(0.45, 0.5))
        self.assertIsNone(world.possession)

    def test_flick_that_misses_the_ball_does_not_keep_possession(self) -> None:
        """A flick away from the ball makes no contact."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.4, 0.5))],
            Vector2(0.7, 0.5),
        )

        outcome = simulate_flick(world, "home-1", Vector2(0.4, 0.9), 0.2)

        self.assertFalse(outcome.ball_contacted)
        self.assertFalse(outcome.keeps_possession)
        self.assertTrue(outcome.settled)

    def test_ball_hitting_an_opposing_piece_is_reported(self) -> None:
        """Opposing contact is detected and rejects the flick."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.4, 0.5)),
                _piece("away-1", AWAY, Vector2(0.55, 0.5)),
            ],
            Vector2(0.45, 0.5),
        )

        outcome = simulate_flick(world, "home-1", Vector2(0.45, 0.5), 0.6)

        self.assertTrue(outcome.opponent_contact)
        self.assertFalse(outcome.keeps_possession)

    def test_pass_reports_receiver_and_small_teammate_gap(self) -> None:
        """A pass that reaches a teammate names the receiver and its gap."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.5, 0.5)),
                _piece("home-2", HOME, Vector2(0.62, 0.5)),
            ],
            Vector2(0.54, 0.5),
        )

        outcome = simulate_flick(
            world,
            "home-1",
            Vector2(0.54, 0.5),
            0.5,
            touch_counts={"home-1": 2},
        )

        self.assertEqual(outcome.receiver_id, "home-2")
        self.assertIsNotNone(outcome.teammate_gap_mm)
        self.assertLess(outcome.teammate_gap_mm, 30.0)

    def test_pieces_without_touches_left_are_not_counted_as_reachable(self) -> None:
        """A teammate on three touches is not a next flicker."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.5, 0.5)),
                _piece("home-2", HOME, Vector2(0.62, 0.5)),
            ],
            Vector2(0.54, 0.5),
        )

        outcome = simulate_flick(
            world,
            "home-1",
            Vector2(0.54, 0.5),
            0.12,
            touch_counts={"home-1": 2, "home-2": 3},
        )

        self.assertIsNone(outcome.teammate_gap_mm)

    def test_away_team_scores_at_the_home_goal(self) -> None:
        """Attack direction is respected for the away team."""
        world = _world(
            [_piece("away-1", AWAY, Vector2(0.18, 0.5))],
            Vector2(0.15, 0.5),
        )

        outcome = simulate_flick(world, "away-1", Vector2(-0.02, 0.5), 0.75)

        self.assertTrue(outcome.goal)
        self.assertTrue(outcome.ball_in_shooting_area)

    def test_zero_strength_flick_is_not_applied(self) -> None:
        """A flick the engine refuses is reported as not applied."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.4, 0.5))],
            Vector2(0.45, 0.5),
        )

        outcome = simulate_flick(world, "home-1", Vector2(0.45, 0.5), 0.0)

        self.assertFalse(outcome.flick_applied)
        self.assertFalse(outcome.keeps_possession)

    def test_hitting_a_teammate_before_the_ball_is_a_foul(self) -> None:
        """A flicker that strikes a teammate first does not keep possession."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.40, 0.5)),
                _piece("home-2", HOME, Vector2(0.43, 0.5)),
            ],
            Vector2(0.50, 0.5),
        )

        outcome = simulate_flick(world, "home-1", Vector2(0.50, 0.5), 0.5)

        self.assertTrue(outcome.touched_piece_before_ball)
        self.assertFalse(outcome.keeps_possession)

    def test_touching_the_ball_first_then_a_piece_is_not_a_foul(self) -> None:
        """Contact after the ball is allowed by the rules."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.5, 0.5)),
                _piece("home-2", HOME, Vector2(0.62, 0.5)),
            ],
            Vector2(0.54, 0.5),
        )

        outcome = simulate_flick(world, "home-1", Vector2(0.54, 0.5), 0.5)

        self.assertFalse(outcome.touched_piece_before_ball)

    def test_ball_progress_is_signed_by_attack_direction(self) -> None:
        """Moving the ball toward the attacked goal is positive progress."""
        home_world = _world(
            [_piece("home-1", HOME, Vector2(0.45, 0.5))],
            Vector2(0.5, 0.5),
        )
        away_world = _world(
            [_piece("away-1", AWAY, Vector2(0.55, 0.5))],
            Vector2(0.5, 0.5),
        )

        home = simulate_flick(home_world, "home-1", Vector2(0.5, 0.5), 0.3)
        away = simulate_flick(away_world, "away-1", Vector2(0.5, 0.5), 0.3)

        self.assertGreater(home.ball_progress_mm, 0.0)
        self.assertGreater(away.ball_progress_mm, 0.0)

    def test_unknown_piece_and_unnamed_plan_are_rejected(self) -> None:
        """Bad inputs raise instead of returning a misleading outcome."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.4, 0.5))],
            Vector2(0.45, 0.5),
        )
        plan = FlickPlan(Vector2(0.45, 0.5), Vector2(0.5, 0.5), 0.3)

        with self.assertRaises(ValueError):
            simulate_flick(world, "missing", Vector2(0.45, 0.5), 0.3)
        with self.assertRaises(ValueError):
            simulate_plan(world, plan)


class VerifiedPlanningTests(unittest.TestCase):
    """Check that verified planning only returns flicks that really work."""

    def test_sampling_finds_a_flick_when_the_planner_has_none(self) -> None:
        """A piece beside the ball with no teammate still finds a safe flick."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.6, 0.3))],
            Vector2(0.55, 0.4),
        )
        self.assertEqual(
            plan_team_flick_candidates(
                [("home-1", Vector2(0.6, 0.3), 0)],
                Vector2(0.55, 0.4),
            ),
            [],
            "The scenario must leave the geometric planner without a plan.",
        )

        without = plan_verified_team_flick(
            world,
            HOME,
            {},
            allow_sampling=False,
        )
        with_sampling = plan_verified_team_flick(world, HOME, {})

        self.assertIsNone(without)
        self.assertIsNotNone(with_sampling)
        self.assertEqual(with_sampling.source, "sampled")
        self.assertTrue(with_sampling.outcome.keeps_possession)

    def test_sampling_does_not_pick_a_flick_that_hits_a_teammate_first(self) -> None:
        """Sampled flicks obey the contact-order foul check."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.45, 0.5)),
                _piece("home-2", HOME, Vector2(0.475, 0.5)),
            ],
            Vector2(0.55, 0.5),
        )

        verified = plan_verified_team_flick(world, HOME, {})

        if verified is not None:
            self.assertFalse(verified.outcome.touched_piece_before_ball)

    def test_scoring_shot_is_chosen_and_reported_as_a_goal(self) -> None:
        """A clear shot is verified as scoring and selected first."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.82, 0.5)),
                _piece("home-2", HOME, Vector2(0.7, 0.62)),
            ],
            Vector2(0.85, 0.5),
        )

        verified = plan_verified_team_flick(world, HOME, {})

        self.assertIsNotNone(verified)
        self.assertEqual(verified.plan.action, "shot")
        self.assertTrue(verified.outcome.goal)

    def test_candidate_that_loses_the_ball_is_not_returned(self) -> None:
        """A flick whose simulation hits an opposing piece is rejected."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.45, 0.5)),
                _piece("away-1", AWAY, Vector2(0.52, 0.5)),
            ],
            Vector2(0.5, 0.5),
        )
        first = plan_team_flick_candidates(
            [("home-1", Vector2(0.45, 0.5), 0)],
            Vector2(0.5, 0.5),
        )[0]
        self.assertTrue(
            simulate_plan(world, first, {}).opponent_contact,
            "The scenario must tempt the planner into hitting the opponent.",
        )

        verified = plan_verified_team_flick(world, HOME, {})

        if verified is not None:
            self.assertTrue(verified.outcome.keeps_possession)
            self.assertFalse(verified.outcome.opponent_contact)

    def test_no_candidates_returns_none(self) -> None:
        """When no piece can reach the ball nothing is returned."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.05, 0.5))],
            Vector2(0.7, 0.5),
        )

        self.assertIsNone(plan_verified_team_flick(world, HOME, {}))

    def test_verified_planning_does_not_modify_the_world(self) -> None:
        """Choosing a flick leaves every body where it was."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.45, 0.5))],
            Vector2(0.5, 0.5),
        )

        plan_verified_team_flick(world, HOME, {})

        self.assertEqual(world.pieces[0].position, Vector2(0.45, 0.5))
        self.assertEqual(world.ball.position, Vector2(0.5, 0.5))
        self.assertIsNone(world.possession)

    def test_away_team_gets_a_verified_flick_toward_the_home_goal(self) -> None:
        """Verified planning is direction-aware."""
        world = _world(
            [_piece("away-1", AWAY, Vector2(0.18, 0.5))],
            Vector2(0.15, 0.5),
        )

        verified = plan_verified_team_flick(world, AWAY, {})

        self.assertIsNotNone(verified)
        self.assertTrue(verified.outcome.goal)



def _outcome(
    ball_position: Vector2,
    *,
    progress_mm: float = 0.0,
    goal: bool = False,
    forward_contact: bool = True,
) -> FlickOutcome:
    """Create a possession-keeping outcome for ranking tests."""
    return FlickOutcome(
        flick_applied=True,
        ball_contacted=True,
        opponent_contact=False,
        possession_kept=True,
        goal=goal,
        receiver_id=None,
        ball_position=ball_position,
        ball_travel_mm=abs(progress_mm),
        ball_in_shooting_area=False,
        teammate_gap_mm=20.0,
        settled=True,
        ball_progress_mm=progress_mm,
        forward_contact_available=forward_contact,
    )


_ADVANCE = FlickPlan(
    piece_target=Vector2(0.5, 0.5),
    ball_target=Vector2(0.5, 0.5),
    strength=0.3,
    action="advance",
    flicking_piece_id="home-1",
)


class NextContactTests(unittest.TestCase):
    """Check the test for a clear, in-range next contact with the ball."""

    def test_clear_in_range_piece_has_a_next_contact(self) -> None:
        """A nearby piece with nothing in the way can play the ball."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.5, 0.5))],
            Vector2(0.55, 0.5),
        )

        self.assertTrue(has_next_contact(world, ["home-1"]))

    def test_piece_in_the_path_blocks_the_next_contact(self) -> None:
        """A piece between the flicker and the ball blocks the route."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.5, 0.5)),
                _piece("home-2", HOME, Vector2(0.525, 0.5)),
            ],
            Vector2(0.56, 0.5),
        )

        self.assertFalse(has_next_contact(world, ["home-1"]))
        self.assertTrue(has_next_contact(world, ["home-1", "home-2"]))

    def test_ball_out_of_flick_range_has_no_next_contact(self) -> None:
        """A piece more than a full flick away cannot reach the ball."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.1, 0.5))],
            Vector2(0.7, 0.5),
        )

        self.assertFalse(has_next_contact(world, ["home-1"]))

    def test_behind_ball_depends_on_attack_direction(self) -> None:
        """Only a piece behind the ball counts for a forward next contact."""
        world = _world(
            [_piece("home-1", HOME, Vector2(0.6, 0.5))],
            Vector2(0.55, 0.5),
        )

        self.assertFalse(
            has_next_contact(world, ["home-1"], behind_ball_for=1)
        )
        self.assertTrue(
            has_next_contact(world, ["home-1"], behind_ball_for=-1)
        )

    def test_third_touch_that_blocks_the_only_teammate_is_flagged(self) -> None:
        """A last touch leaving the flicker between teammate and ball fails."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.5, 0.5)),
                _piece("home-2", HOME, Vector2(0.4, 0.5)),
            ],
            Vector2(0.52, 0.5),
        )

        outcome = simulate_flick(
            world,
            "home-1",
            Vector2(0.52, 0.5),
            0.15,
            touch_counts={"home-1": 2},
        )

        self.assertTrue(outcome.keeps_possession)
        self.assertFalse(outcome.next_contact_available)

    def test_same_flick_with_touches_left_keeps_a_next_contact(self) -> None:
        """The flicker itself counts while it still has touches left."""
        world = _world(
            [
                _piece("home-1", HOME, Vector2(0.5, 0.5)),
                _piece("home-2", HOME, Vector2(0.4, 0.5)),
            ],
            Vector2(0.52, 0.5),
        )

        outcome = simulate_flick(
            world,
            "home-1",
            Vector2(0.52, 0.5),
            0.15,
            touch_counts={"home-1": 0},
        )

        self.assertTrue(outcome.next_contact_available)
        self.assertTrue(outcome.forward_contact_available)


class RankingTests(unittest.TestCase):
    """Check step backs, repeats and progress measurement."""

    def test_large_backward_move_is_a_step_back(self) -> None:
        """Moving the ball well back ranks after forward moves."""
        back = _rank_key(
            _ADVANCE,
            _outcome(Vector2(0.4, 0.5), progress_mm=-80.0),
        )
        ahead = _rank_key(
            _ADVANCE,
            _outcome(Vector2(0.6, 0.5), progress_mm=30.0),
        )

        self.assertEqual(back[0], STEP_BACK_CATEGORY)
        self.assertLess(ahead, back)

    def test_returning_to_a_visited_position_is_a_repeat(self) -> None:
        """A ball stopping where it already stopped ranks last."""
        visited = [Vector2(0.5, 0.5)]
        repeat = _rank_key(_ADVANCE, _outcome(Vector2(0.5, 0.5)), visited)
        back = _rank_key(
            _ADVANCE,
            _outcome(Vector2(0.4, 0.5), progress_mm=-80.0),
            visited,
        )

        self.assertEqual(repeat[0], REPEAT_CATEGORY)
        self.assertLess(back, repeat)

    def test_a_goal_is_never_a_repeat(self) -> None:
        """Scoring ranks first even at a visited position."""
        key = _rank_key(
            _ADVANCE,
            _outcome(Vector2(0.5, 0.5), goal=True),
            [Vector2(0.5, 0.5)],
        )

        self.assertEqual(key[0], 0)

    def test_teammate_behind_the_ball_is_preferred(self) -> None:
        """Between equal moves, one leaving a forward contact ranks first."""
        ready = _rank_key(_ADVANCE, _outcome(Vector2(0.6, 0.5)))
        not_ready = _rank_key(
            _ADVANCE,
            _outcome(Vector2(0.6, 0.5), forward_contact=False),
        )

        self.assertLess(ready, not_ready)

    def test_progress_in_shooting_area_is_toward_the_goal_mouth(self) -> None:
        """Along the goal line toward the goal counts as progress."""
        toward = _ball_progress_mm(
            Vector2(0.99, 0.8),
            Vector2(0.99, 0.7),
            HOME,
        )
        away = _ball_progress_mm(
            Vector2(0.99, 0.6),
            Vector2(0.99, 0.7),
            HOME,
        )
        mirrored = _ball_progress_mm(
            Vector2(0.01, 0.8),
            Vector2(0.01, 0.7),
            AWAY,
        )

        self.assertGreater(toward, 0.0)
        self.assertLess(away, 0.0)
        self.assertAlmostEqual(toward, mirrored)

    def test_progress_outside_shooting_area_is_along_the_length(self) -> None:
        """Outside the shooting area only movement along X counts."""
        self.assertAlmostEqual(
            _ball_progress_mm(Vector2(0.5, 0.5), Vector2(0.55, 0.3), HOME),
            0.05 * 1200.0,
        )

if __name__ == "__main__":
    unittest.main()
