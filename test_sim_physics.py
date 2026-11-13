"""Focused headless tests for the Subbuteo physics engine."""

import unittest

from sim_physics import (
    AWAY,
    HOME,
    BALL_FRICTION_MM_S2,
    BALL_RADIUS_MM,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    Body,
    PhysicsWorld,
    Vector2,
)


def _empty_world(ball_position: Vector2) -> PhysicsWorld:
    """Create a physics world without pieces for isolated boundary tests."""
    ball = Body(
        body_id="ball",
        position=ball_position,
        radius_mm=BALL_RADIUS_MM,
        mass=2.7,
        kind="ball",
        friction_mm_s2=0.0,
    )
    return PhysicsWorld([], ball)


class PhysicsWorldTests(unittest.TestCase):
    """Verify collisions, boundary responses, and goal eligibility."""

    def test_touchline_bounce_preserves_possession(self) -> None:
        """A touchline rebound uses wall restitution without changing possession."""
        world = _empty_world(Vector2(0.5, (BALL_RADIUS_MM + 0.1) / PITCH_WIDTH_MM))
        world.ball.velocity = Vector2(0.0, -100.0)
        world.possession = HOME
        world.last_flick_team = HOME

        world.step(1.0 / 60.0)

        self.assertAlmostEqual(world.ball.velocity.y, 65.0)
        self.assertEqual(world.possession, HOME)

    def test_ineligible_goal_mouth_attempt_rebounds_and_transfers_possession(self) -> None:
        """An out-of-area attempt through the goal mouth rebounds."""
        world = _empty_world(Vector2(1.0 - 0.5 / PITCH_LENGTH_MM, 0.5))
        world.ball.velocity = Vector2(500.0, 0.0)
        world.last_flick_team = HOME
        world._shot_start_x = 0.5

        world.step(1.0 / 60.0)

        self.assertEqual(world.away_score, 0)
        self.assertEqual(world.possession, AWAY)
        self.assertLess(world.ball.velocity.x, 0.0)

    def test_ball_on_shooting_line_is_not_goal_eligible(self) -> None:
        """A ball starting exactly on the shooting line cannot score."""
        world = _empty_world(Vector2(1.0 - 0.5 / PITCH_LENGTH_MM, 0.5))
        world.ball.velocity = Vector2(500.0, 0.0)
        world.last_flick_team = HOME
        world._shot_start_x = 1.0 - 280.0 / PITCH_LENGTH_MM

        world.step(1.0 / 60.0)

        self.assertEqual(world.away_score, 0)
        self.assertEqual(world.possession, AWAY)

    def test_goal_line_outside_goal_mouth_rebounds_with_possession_transfer(
        self,
    ) -> None:
        """A non-mouth goal-line contact rebounds and transfers possession."""
        world = _empty_world(Vector2(0.5 / PITCH_LENGTH_MM, 0.2))
        world.ball.velocity = Vector2(-100.0, 0.0)
        world.possession = HOME
        world.last_flick_team = HOME

        world.step(1.0 / 60.0)

        self.assertEqual(world.possession, AWAY)
        self.assertAlmostEqual(world.ball.velocity.x, 65.0)

    def test_eligible_shot_scores_and_enters_damped_net(self) -> None:
        """An eligible attempt scores once and enters the goal net."""
        world = _empty_world(Vector2(1.0 - 0.5 / PITCH_LENGTH_MM, 0.5))
        world.ball.velocity = Vector2(500.0, 0.0)
        world.last_flick_team = HOME
        world._shot_start_x = 0.8

        world.step(1.0 / 60.0)

        self.assertEqual(world.home_score, 1)
        self.assertEqual(world.last_goal.scoring_team, HOME)
        self.assertEqual(world.ball_in_net, AWAY)

    def test_goal_net_rebound_is_more_damped_than_pitch_wall(self) -> None:
        """A goal-net back wall uses its lower restitution coefficient."""
        world = _empty_world(
            Vector2(1.0 + 48.9 / PITCH_LENGTH_MM, 0.5)
        )
        world.ball_in_net = AWAY
        world.ball.velocity = Vector2(100.0, 0.0)

        world.step(1.0 / 60.0)

        self.assertAlmostEqual(world.ball.velocity.x, -30.0)

    def test_own_goal_scores_for_opponent(self) -> None:
        """An own goal is credited to the other team from any pitch position."""
        world = _empty_world(Vector2(0.5 / PITCH_LENGTH_MM, 0.5))
        world.ball.velocity = Vector2(-500.0, 0.0)
        world.last_flick_team = HOME
        world._shot_start_x = 0.5

        world.step(1.0 / 60.0)

        self.assertEqual(world.away_score, 1)
        self.assertEqual(world.home_score, 0)

    def test_away_shot_scores_for_away_at_home_goal(self) -> None:
        """A valid shot into the home goal is credited to the away team."""
        world = _empty_world(Vector2(0.5 / PITCH_LENGTH_MM, 0.5))
        world.ball.velocity = Vector2(-500.0, 0.0)
        world.last_flick_team = AWAY
        world._shot_start_x = 0.2

        world.step(1.0 / 60.0)

        self.assertEqual(world.away_score, 1)
        self.assertEqual(world.home_score, 0)
        self.assertEqual(world.last_goal.scoring_team, AWAY)

    def test_piece_collision_transfers_motion_to_ball(self) -> None:
        """A moving field piece transfers momentum to a stationary ball."""
        piece = Body(
            body_id="home-0",
            position=Vector2(0.5, 0.5),
            radius_mm=9.25,
            mass=22.0,
            team=HOME,
            velocity=Vector2(200.0, 0.0),
            friction_mm_s2=0.0,
        )
        ball = Body(
            body_id="ball",
            position=Vector2(0.5 + 20.0 / PITCH_LENGTH_MM, 0.5),
            radius_mm=BALL_RADIUS_MM,
            mass=2.7,
            kind="ball",
            friction_mm_s2=0.0,
        )
        world = PhysicsWorld([piece], ball)

        world.step(1.0 / 120.0)

        self.assertGreater(world.ball.velocity.x, 0.0)

    def test_maximum_strength_piece_flick_travels_about_half_pitch(self) -> None:
        """A freely moving player piece should stop after about 600 mm."""
        piece = Body(
            body_id="home-0",
            position=Vector2(0.25, 0.5),
            radius_mm=9.25,
            mass=22.0,
            team=HOME,
        )
        ball = Body(
            body_id="ball",
            position=Vector2(0.95, 0.5),
            radius_mm=BALL_RADIUS_MM,
            mass=2.7,
            kind="ball",
            friction_mm_s2=0.0,
        )
        world = PhysicsWorld([piece], ball)
        world.flick("home-0", Vector2(-300.0, 0.0))

        for _ in range(200):
            if piece.velocity.length == 0.0:
                break
            world.step(1.0 / 120.0)

        travel_mm = (piece.position.x - 0.25) * PITCH_LENGTH_MM
        self.assertAlmostEqual(travel_mm, 600.0, delta=10.0)

    def test_reset_pieces_restores_positions_without_moving_ball(self) -> None:
        """Reset restores game pieces and leaves the ball where it is."""
        world = PhysicsWorld.demo_match()
        starting_positions = [piece.position for piece in world.pieces]
        world.pieces[0].position = Vector2(0.4, 0.4)
        world.pieces[0].velocity = Vector2(100.0, -50.0)
        world.ball.position = Vector2(0.6, 0.6)

        world.reset_pieces()

        self.assertEqual(
            [piece.position for piece in world.pieces],
            starting_positions,
        )
        self.assertEqual(world.pieces[0].velocity, Vector2(0.0, 0.0))
        self.assertEqual(world.ball.position, Vector2(0.6, 0.6))

    def test_reset_pieces_and_ball_restores_center_restart(self) -> None:
        """Combined reset restores pieces and returns the ball to center."""
        world = PhysicsWorld.demo_match()
        starting_positions = [piece.position for piece in world.pieces]
        world.pieces[0].position = Vector2(0.4, 0.4)
        world.ball.position = Vector2(0.6, 0.6)
        world.ball.velocity = Vector2(120.0, -80.0)
        world.ball_in_net = AWAY
        world.last_flick_team = HOME

        world.reset_pieces_and_ball()

        self.assertEqual(
            [piece.position for piece in world.pieces],
            starting_positions,
        )
        self.assertEqual(world.ball.position, Vector2(0.5, 0.5))
        self.assertEqual(world.ball.velocity, Vector2(0.0, 0.0))
        self.assertIsNone(world.ball_in_net)
        self.assertIsNone(world.last_flick_team)

    def test_firm_flick_sends_ball_about_three_quarters_pitch_length(self) -> None:
        """A full-strength hit should stop the ball near 75% of pitch length."""
        piece = Body(
            body_id="home-0",
            position=Vector2(0.25, 0.5),
            radius_mm=9.25,
            mass=22.0,
            team=HOME,
        )
        ball = Body(
            body_id="ball",
            position=Vector2(0.5, 0.5),
            radius_mm=BALL_RADIUS_MM,
            mass=2.7,
            kind="ball",
            friction_mm_s2=BALL_FRICTION_MM_S2,
        )
        world = PhysicsWorld([piece], ball)
        world.flick("home-0", Vector2(-300.0, 0.0))

        for _ in range(120):
            world.step(1.0 / 120.0)
            if ball.velocity.length > 1.0:
                break

        estimated_stop_distance = (
            ball.velocity.length ** 2 / (2 * BALL_FRICTION_MM_S2)
        )
        self.assertGreaterEqual(estimated_stop_distance, 750.0)
        self.assertLessEqual(estimated_stop_distance, 1050.0)


if __name__ == "__main__":
    unittest.main()
