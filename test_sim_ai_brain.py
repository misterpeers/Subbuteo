"""Focused tests for headless AI player distance and contact estimates."""

import unittest
from math import sqrt

from sim_ai_brain import (
    Obstacle,
    TargetArea,
    choose_training_waypoint,
    estimate_contact_strength,
    plan_training_ball_flick,
    plan_training_team_ball_flick,
    training_flick_strength,
)
from sim_ai_flick import distance_between_mm, flick_toward_target
from sim_physics import (
    BALL_FRICTION_MM_S2,
    BALL_RADIUS_MM,
    HOME,
    MAX_FLICK_SPEED_MM_S,
    MAX_DRAG_MM,
    MIN_FLICK_DRAG_MM,
    PIECE_FRICTION_MM_S2,
    PIECE_RADIUS_MM,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    Body,
    PhysicsWorld,
    Vector2,
)


def _world(ball_x: float) -> PhysicsWorld:
    """Create a world with a fixed player piece and a configurable ball."""
    piece = Body(
        body_id="ai-piece",
        position=Vector2(0.25, 0.5),
        radius_mm=PIECE_RADIUS_MM,
        mass=22.0,
        team=HOME,
        friction_mm_s2=PIECE_FRICTION_MM_S2,
    )
    ball = Body(
        body_id="ball",
        position=Vector2(ball_x, 0.5),
        radius_mm=BALL_RADIUS_MM,
        mass=2.7,
        kind="ball",
    )
    return PhysicsWorld([piece], ball)


class ContactEstimateTests(unittest.TestCase):
    """Check strength estimates for contact, range, and friction limits."""

    def test_estimate_uses_edge_gap_and_existing_flick_physics(self) -> None:
        """The estimate accounts for both radii and piece friction."""
        world = _world(0.5)

        estimate = estimate_contact_strength(world, "ai-piece")

        gap_mm = 0.25 * PITCH_LENGTH_MM - PIECE_RADIUS_MM - BALL_RADIUS_MM
        expected_percent = (
            100.0
            * sqrt(2.0 * PIECE_FRICTION_MM_S2 * gap_mm)
            / MAX_FLICK_SPEED_MM_S
        )
        self.assertAlmostEqual(estimate.gap_mm, gap_mm)
        self.assertAlmostEqual(estimate.strength_percent, expected_percent)

    def test_no_power_is_needed_when_already_touching(self) -> None:
        """An overlapping/touching setup reports zero gap and zero strength."""
        ball_x = (
            0.25
            + (PIECE_RADIUS_MM + BALL_RADIUS_MM) / PITCH_LENGTH_MM
        )
        estimate = estimate_contact_strength(_world(ball_x), "ai-piece")

        self.assertAlmostEqual(estimate.gap_mm, 0.0)
        self.assertEqual(estimate.strength_percent, 0.0)

    def test_unreachable_ball_reports_no_valid_percentage(self) -> None:
        """A contact gap beyond maximum range is not reported as 100% success."""
        estimate = estimate_contact_strength(_world(0.9), "ai-piece")

        self.assertIsNone(estimate.strength_percent)

    def test_small_positive_gap_respects_minimum_flick_impulse(self) -> None:
        """A short contact estimate still produces an engine-valid flick."""
        ball_x = (
            0.25
            + (PIECE_RADIUS_MM + BALL_RADIUS_MM + 0.01) / PITCH_LENGTH_MM
        )
        estimate = estimate_contact_strength(_world(ball_x), "ai-piece")

        self.assertAlmostEqual(
            estimate.strength_percent,
            100.0 * MIN_FLICK_DRAG_MM / MAX_DRAG_MM,
        )


class TrainingBrainTests(unittest.TestCase):
    """Check headless AI navigation toward target areas."""

    def test_training_move_avoids_obstacles(self) -> None:
        """The AI reaches the target without crossing a blocking rectangle."""
        obstacle = Obstacle(center=Vector2(0.5, 0.5), size=Vector2(0.18, 0.18))
        target = TargetArea(center=Vector2(0.8, 0.5), radius=0.06)
        position = Vector2(0.25, 0.5)

        for _ in range(100):
            waypoint = choose_training_waypoint(position, target, [obstacle])
            if waypoint is None:
                break
            self.assertFalse(
                _segment_crosses_obstacle(position, waypoint, obstacle)
            )
            position = waypoint

        self.assertTrue(target.contains(position))

    def test_target_area_contains_piece_inside_circle(self) -> None:
        """A target area marks a reachable circle for the training AI."""
        target = TargetArea(center=Vector2(0.8, 0.5), radius=0.06)
        self.assertTrue(target.contains(Vector2(0.8, 0.5)))
        self.assertFalse(target.contains(Vector2(0.87, 0.5)))

    def test_training_waypoint_stops_inside_target_area(self) -> None:
        """The AI does not keep stepping once it reaches the target area."""
        target = TargetArea(center=Vector2(0.8, 0.5), radius=0.06)
        waypoint = choose_training_waypoint(Vector2(0.81, 0.5), target)
        self.assertIsNone(waypoint)

    def test_training_flick_strength_is_conservative(self) -> None:
        """Flick power maps a waypoint distance to a sub-maximal impulse."""
        strength = training_flick_strength(
            Vector2(0.2, 0.5),
            Vector2(0.3, 0.5),
        )
        self.assertGreater(strength, 0.0)
        self.assertLess(strength, 1.0)

    def test_ball_flick_plan_routes_around_obstacle(self) -> None:
        """The ball waypoint and approach avoid a blocking obstacle."""
        piece_position = Vector2(0.45, 0.5)
        ball_position = Vector2(0.5, 0.5)
        blocker = Obstacle(
            center=Vector2(0.65, 0.5),
            size=Vector2(0.08, 0.12),
            padding=0.0,
        )
        plan = plan_training_ball_flick(
            piece_position,
            ball_position,
            [blocker],
        )

        self.assertIsNotNone(plan)
        self.assertFalse(
            _segment_crosses_obstacle(ball_position, plan.ball_target, blocker)
        )
        self.assertFalse(
            _segment_crosses_obstacle(piece_position, plan.piece_target, blocker)
        )
        self.assertGreater(plan.ball_target.x, ball_position.x)
        self.assertLessEqual(
            distance_between_mm(ball_position, plan.ball_target),
            180.0,
        )

    def test_ball_flick_plan_rejects_unreachable_contact(self) -> None:
        """The AI does not launch a ball-mode flick outside contact range."""
        plan = plan_training_ball_flick(
            Vector2(0.0, 0.5),
            Vector2(0.5, 0.5),
        )

        self.assertIsNone(plan)

    def test_ball_training_uses_a_short_contact_flick(self) -> None:
        """A routine advance stays controlled and keeps the piece near the ball."""
        piece = Body(
            body_id="ai-piece",
            position=Vector2(0.45, 0.5),
            radius_mm=PIECE_RADIUS_MM,
            mass=22.0,
            team=HOME,
            friction_mm_s2=PIECE_FRICTION_MM_S2,
        )
        ball = Body(
            body_id="ball",
            position=Vector2(0.5, 0.5),
            radius_mm=BALL_RADIUS_MM,
            mass=2.7,
            kind="ball",
        )
        world = PhysicsWorld([piece], ball)
        plan = plan_training_ball_flick(piece.position, ball.position)
        self.assertIsNotNone(plan)
        self.assertLessEqual(
            distance_between_mm(ball.position, plan.ball_target),
            30.001,
        )
        ball_position_before = ball.position
        self.assertTrue(
            flick_toward_target(
                world,
                "ai-piece",
                plan.piece_target,
                plan.strength,
            )
        )

        for _ in range(1000):
            world.step(1.0 / 120.0)
            if piece.velocity.length == 0.0 and ball.velocity.length == 0.0:
                break

        self.assertGreater(ball.position.x, ball_position_before.x)
        self.assertLess(
            distance_between_mm(piece.position, ball.position),
            60.0,
        )

    def test_second_piece_is_used_for_a_pass_after_two_flicks(self) -> None:
        """The third flick passes to a teammate instead of forcing progress."""
        piece_position = Vector2(0.55, 0.5)
        ball_position = Vector2(0.62, 0.5)
        receiver_position = Vector2(0.72, 0.5)
        plan = plan_training_ball_flick(
            piece_position,
            ball_position,
            piece_touches_used=2,
            teammates=[("ai-piece-2", receiver_position)],
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.receiver_piece_id, "ai-piece-2")
        self.assertEqual(plan.action, "pass")
        self.assertGreater(plan.ball_target.x, receiver_position.x)

    def test_second_touch_cannot_be_followed_by_another_advance(self) -> None:
        """Without a teammate or eligible shot, the AI refuses a third advance."""
        plan = plan_training_ball_flick(
            Vector2(0.55, 0.5),
            Vector2(0.62, 0.5),
            piece_touches_used=2,
        )

        self.assertIsNone(plan)

    def test_eligible_shot_takes_priority_over_pass_after_two_flicks(self) -> None:
        """A clear eligible shot remains the top priority on the third flick."""
        plan = plan_training_ball_flick(
            Vector2(0.82, 0.5),
            Vector2(0.85, 0.5),
            piece_touches_used=2,
            teammates=[("ai-piece-2", Vector2(0.5, 0.5))],
        )

        self.assertIsNotNone(plan)
        self.assertIsNone(plan.receiver_piece_id)
        self.assertEqual(plan.action, "shot")
        self.assertEqual(plan.ball_target, Vector2(1.02, 0.5))

    def test_fourth_consecutive_piece_flick_is_never_planned(self) -> None:
        """A piece cannot exceed the three-consecutive-touch rule."""
        plan = plan_training_ball_flick(
            Vector2(0.55, 0.5),
            Vector2(0.62, 0.5),
            piece_touches_used=3,
            teammates=[("ai-piece-2", Vector2(0.72, 0.5))],
        )

        self.assertIsNone(plan)

    def test_team_planner_switches_to_piece_behind_ball_diagonally(self) -> None:
        """A teammate behind the ball can take over from a diagonal approach."""
        plan = plan_training_team_ball_flick(
            [
                ("ai-piece", Vector2(0.8, 0.5), 3),
                ("ai-piece-2", Vector2(0.5, 0.62), 0),
            ],
            Vector2(0.65, 0.5),
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.flicking_piece_id, "ai-piece-2")
        self.assertEqual(plan.action, "advance")

    def test_team_planner_can_switch_before_piece_uses_touch_limit(self) -> None:
        """A nearby teammate may be chosen while the active piece has touches left."""
        plan = plan_training_team_ball_flick(
            [
                ("ai-piece", Vector2(0.25, 0.18), 1),
                ("ai-piece-2", Vector2(0.59, 0.59), 0),
            ],
            Vector2(0.65, 0.5),
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.flicking_piece_id, "ai-piece-2")

    def test_team_planner_rejects_an_approach_through_a_teammate(self) -> None:
        """A blocked candidate is skipped in favor of a clear teammate route."""
        plan = plan_training_team_ball_flick(
            [
                ("ai-piece", Vector2(0.5, 0.5), 0),
                ("ai-piece-2", Vector2(0.56, 0.5), 3),
                ("ai-piece-3", Vector2(0.52, 0.7), 0),
            ],
            Vector2(0.65, 0.5),
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.flicking_piece_id, "ai-piece-3")

    def test_team_planner_allows_a_near_miss_of_a_teammate(self) -> None:
        """A nearby teammate does not block a path that clears its base."""
        plan = plan_training_team_ball_flick(
            [
                ("ai-piece", Vector2(0.5, 0.5), 0),
                ("ai-piece-2", Vector2(0.56, 0.53), 3),
            ],
            Vector2(0.65, 0.5),
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.flicking_piece_id, "ai-piece")

    def test_team_planner_preserves_eligible_shot_priority(self) -> None:
        """An eligible shot outranks an available progress flick."""
        plan = plan_training_team_ball_flick(
            [
                ("ai-piece", Vector2(0.82, 0.5), 0),
                ("ai-piece-2", Vector2(0.72, 0.62), 0),
            ],
            Vector2(0.9, 0.5),
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.action, "shot")

    def test_team_planner_uses_third_touch_to_open_teammate_route(self) -> None:
        """A third-touch setup can clear the flicker's body for a teammate."""
        plan = plan_training_team_ball_flick(
            [
                ("ai-piece", Vector2(0.55, 0.5), 2),
                ("ai-piece-2", Vector2(0.25, 0.25625), 0),
                ("ai-piece-3", Vector2(0.25, 0.74375), 0),
            ],
            Vector2(0.59, 0.5),
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.action, "pass")
        self.assertEqual(plan.flicking_piece_id, "ai-piece")
        self.assertIn(plan.receiver_piece_id, {"ai-piece-2", "ai-piece-3"})
        self.assertNotEqual(plan.ball_target, Vector2(0.59, 0.5))
        self.assertLessEqual(
            distance_between_mm(Vector2(0.59, 0.5), plan.ball_target),
            15.001,
        )

    def test_third_touch_setup_enables_teammate_to_continue(self) -> None:
        """The setup makes contact and leaves a safe next flick for its receiver."""
        player_positions = [
            ("ai-piece", Vector2(0.55, 0.5), 2),
            ("ai-piece-2", Vector2(0.25, 0.25625), 0),
            ("ai-piece-3", Vector2(0.25, 0.74375), 0),
        ]
        pieces = [
            Body(
                body_id=piece_id,
                position=position,
                radius_mm=PIECE_RADIUS_MM,
                mass=22.0,
                team=HOME,
                friction_mm_s2=PIECE_FRICTION_MM_S2,
            )
            for piece_id, position, _ in player_positions
        ]
        ball = Body(
            body_id="ball",
            position=Vector2(0.59, 0.5),
            radius_mm=BALL_RADIUS_MM,
            mass=2.7,
            kind="ball",
            friction_mm_s2=BALL_FRICTION_MM_S2,
        )
        world = PhysicsWorld(pieces, ball)
        plan = plan_training_team_ball_flick(player_positions, ball.position)

        self.assertIsNotNone(plan)
        self.assertTrue(
            flick_toward_target(
                world,
                plan.flicking_piece_id,
                plan.piece_target,
                plan.strength,
            )
        )

        flicker_contacted_ball = False
        for _ in range(5000):
            world.step(1.0 / 120.0)
            flicker_contacted_ball |= (
                plan.flicking_piece_id in world.last_ball_contacts
            )
            if (
                all(piece.velocity.length == 0.0 for piece in world.pieces)
                and ball.velocity.length == 0.0
            ):
                break

        self.assertTrue(flicker_contacted_ball)
        ball_travel_mm = distance_between_mm(
            ball.position,
            Vector2(0.59, 0.5),
        )
        self.assertGreater(ball_travel_mm, 3.0)
        self.assertLessEqual(ball_travel_mm, 30.001)
        next_plan = plan_training_team_ball_flick(
            [
                (
                    piece.body_id,
                    piece.position,
                    3 if piece.body_id == plan.flicking_piece_id else 0,
                )
                for piece in world.pieces
            ],
            ball.position,
        )

        self.assertIsNotNone(next_plan)
        self.assertEqual(next_plan.flicking_piece_id, plan.receiver_piece_id)

    def test_planned_pass_contacts_teammate(self) -> None:
        """The planned pass physically reaches the second player piece."""
        piece = Body(
            body_id="ai-piece",
            position=Vector2(0.55, 0.5),
            radius_mm=PIECE_RADIUS_MM,
            mass=22.0,
            team=HOME,
            friction_mm_s2=PIECE_FRICTION_MM_S2,
        )
        teammate = Body(
            body_id="ai-piece-2",
            position=Vector2(0.72, 0.5),
            radius_mm=PIECE_RADIUS_MM,
            mass=22.0,
            team=HOME,
            friction_mm_s2=PIECE_FRICTION_MM_S2,
        )
        ball = Body(
            body_id="ball",
            position=Vector2(0.62, 0.5),
            radius_mm=BALL_RADIUS_MM,
            mass=2.7,
            kind="ball",
        )
        world = PhysicsWorld([piece, teammate], ball)
        plan = plan_training_ball_flick(
            piece.position,
            ball.position,
            piece_touches_used=2,
            teammates=[(teammate.body_id, teammate.position)],
        )
        self.assertIsNotNone(plan)
        ball_position_before = ball.position
        self.assertTrue(
            flick_toward_target(
                world,
                piece.body_id,
                plan.piece_target,
                plan.strength,
            )
        )
        teammate_contacted = False

        for _ in range(1000):
            world.step(1.0 / 120.0)
            teammate_contacted |= (
                distance_between_mm(ball.position, ball_position_before) > 3.0
                and teammate.body_id in world.last_ball_contacts
            )
            if (
                piece.velocity.length == 0.0
                and teammate.velocity.length == 0.0
                and ball.velocity.length == 0.0
            ):
                break

        self.assertTrue(teammate_contacted)
        self.assertLessEqual(
            distance_between_mm(ball.position, teammate.position),
            PIECE_RADIUS_MM + BALL_RADIUS_MM + 25.0,
        )
        return_plan = plan_training_ball_flick(
            teammate.position,
            ball.position,
            teammates=[(piece.body_id, piece.position)],
        )
        self.assertIsNotNone(return_plan)
        self.assertEqual(return_plan.receiver_piece_id, piece.body_id)

    def test_training_reaches_target_within_two_or_three_touches(self) -> None:
        """A clear route uses the final allowed touch to cover the last gap."""
        for max_touches in (2, 3):
            with self.subTest(max_touches=max_touches):
                piece = Body(
                    body_id="ai-piece",
                    position=Vector2(280 / PITCH_LENGTH_MM, 0.5),
                    radius_mm=PIECE_RADIUS_MM,
                    mass=22.0,
                    team=HOME,
                    friction_mm_s2=PIECE_FRICTION_MM_S2,
                )
                ball = Body(
                    body_id="ball",
                    position=Vector2(-1.0, -1.0),
                    radius_mm=BALL_RADIUS_MM,
                    mass=2.7,
                    movable=False,
                    kind="ball",
                )
                world = PhysicsWorld([piece], ball)
                target = TargetArea(center=Vector2(0.85, 0.5), radius=0.06)

                for touch_index in range(max_touches):
                    if target.contains(piece.position):
                        break
                    waypoint = choose_training_waypoint(piece.position, target)
                    if waypoint is None:
                        self.fail("Expected a route to the target")
                    remaining_touches = max_touches - touch_index
                    strength = training_flick_strength(
                        piece.position,
                        waypoint,
                        piece.friction_mm_s2,
                        touches_remaining=remaining_touches,
                    )
                    if touch_index == 0:
                        self.assertGreater(strength, 0.9)
                    if remaining_touches == 1:
                        conservative_strength = training_flick_strength(
                            piece.position,
                            waypoint,
                            piece.friction_mm_s2,
                        )
                        self.assertGreater(strength, conservative_strength)
                    self.assertTrue(
                        flick_toward_target(
                            world,
                            "ai-piece",
                            waypoint,
                            strength,
                        )
                    )
                    for _ in range(5000):
                        world.step(1 / 120)
                        if piece.velocity.length == 0.0:
                            break

                self.assertTrue(target.contains(piece.position))

    def test_training_replans_after_each_physics_flick_stops(self) -> None:
        """The AI reaches the target through separate physical flicks."""
        world = _world(0.95)
        piece = world.pieces[0]
        obstacle = Obstacle(
            center=Vector2(0.5, 0.5),
            size=Vector2(0.14, 0.14),
        )
        target = TargetArea(center=Vector2(0.8, 0.5), radius=0.06)

        for _ in range(20):
            if target.contains(piece.position):
                break
            waypoint = choose_training_waypoint(piece.position, target, [obstacle])
            if waypoint is None:
                self.fail("Expected a route to the target")
            strength = training_flick_strength(
                piece.position,
                waypoint,
                piece.friction_mm_s2,
            )
            self.assertTrue(
                flick_toward_target(world, "ai-piece", waypoint, strength)
            )
            for _ in range(1000):
                world.step(1 / 120)
                if piece.velocity.length == 0.0:
                    break
            self.assertEqual(piece.velocity.length, 0.0)
            self.assertFalse(obstacle.contains(piece.position, clearance=0.012))

        self.assertTrue(target.contains(piece.position))


def _segment_crosses_obstacle(
    start: Vector2,
    end: Vector2,
    obstacle: Obstacle,
) -> bool:
    """Return whether a normalized line segment enters an obstacle clearance."""
    for step in range(1, 101):
        fraction = step / 100
        point = Vector2(
            start.x + (end.x - start.x) * fraction,
            start.y + (end.y - start.y) * fraction,
        )
        if obstacle.contains(point, clearance=0.012):
            return True
    return False


if __name__ == "__main__":
    unittest.main()
