"""Focused tests for headless AI flick aiming and power control."""

import unittest

from sim_ai_flick import (
    aim_target_position,
    distance_between_mm,
    flick_toward_target,
)
from sim_physics import (
    HOME,
    MAX_FLICK_SPEED_MM_S,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    BALL_RADIUS_MM,
    Body,
    PhysicsWorld,
    Vector2,
)


def _world(piece_position: Vector2) -> PhysicsWorld:
    """Create a world with one movable player piece and a stationary ball."""
    piece = Body(
        body_id="ai-piece",
        position=piece_position,
        radius_mm=9.25,
        mass=22.0,
        team=HOME,
        friction_mm_s2=0.0,
    )
    ball = Body(
        body_id="ball",
        position=Vector2(0.5, 0.5),
        radius_mm=BALL_RADIUS_MM,
        mass=2.7,
        kind="ball",
        friction_mm_s2=0.0,
    )
    return PhysicsWorld([piece], ball)


class AIFlickTests(unittest.TestCase):
    """Check that the AI helper aims and scales its impulses correctly."""

    def test_flick_points_toward_target_with_selected_strength(self) -> None:
        """A half-strength flick aims at the marker with half maximum speed."""
        world = _world(Vector2(0.25, 0.5))

        applied = flick_toward_target(
            world,
            "ai-piece",
            Vector2(0.75, 0.5),
            0.5,
        )

        self.assertTrue(applied)
        velocity = world.pieces[0].velocity
        self.assertGreater(velocity.x, 0.0)
        self.assertAlmostEqual(velocity.y, 0.0)
        self.assertAlmostEqual(velocity.length, MAX_FLICK_SPEED_MM_S * 0.5)

    def test_diagonal_flick_uses_pitch_aspect_ratio(self) -> None:
        """The normalized target direction is converted using pitch dimensions."""
        world = _world(Vector2(0.25, 0.25))
        target = Vector2(0.5, 0.75)

        flick_toward_target(world, "ai-piece", target, 1.0)

        velocity = world.pieces[0].velocity
        expected_x = 0.25 * PITCH_LENGTH_MM
        expected_y = 0.5 * PITCH_WIDTH_MM
        self.assertAlmostEqual(velocity.x / velocity.y, expected_x / expected_y)

    def test_zero_strength_or_coincident_target_does_not_flick(self) -> None:
        """No impulse is applied at zero power or when the target overlaps."""
        world = _world(Vector2(0.25, 0.5))

        self.assertFalse(
            flick_toward_target(world, "ai-piece", Vector2(0.75, 0.5), 0.0)
        )
        self.assertFalse(
            flick_toward_target(world, "ai-piece", Vector2(0.25, 0.5), 1.0)
        )
        self.assertEqual(world.pieces[0].velocity, Vector2(0.0, 0.0))

    def test_strength_outside_slider_range_is_rejected(self) -> None:
        """Invalid power values fail explicitly rather than being clamped."""
        world = _world(Vector2(0.25, 0.5))

        for strength in (-0.01, 1.01):
            with self.subTest(strength=strength):
                with self.assertRaises(ValueError):
                    flick_toward_target(
                        world,
                        "ai-piece",
                        Vector2(0.75, 0.5),
                        strength,
                    )

    def test_aim_mode_selects_marker_or_current_ball_position(self) -> None:
        """The two modes resolve to the marker or the ball's live position."""
        world = _world(Vector2(0.25, 0.5))
        marker = Vector2(0.8, 0.3)
        world.ball.position = Vector2(0.55, 0.7)

        self.assertEqual(aim_target_position(world, marker, "marker"), marker)
        self.assertEqual(
            aim_target_position(world, marker, "ball"),
            world.ball.position,
        )

    def test_distance_between_positions_uses_physical_pitch_dimensions(self) -> None:
        """Travel measurements convert normalized X and Y to millimeters."""
        distance = distance_between_mm(
            Vector2(0.25, 0.25),
            Vector2(0.5, 0.5),
        )

        self.assertAlmostEqual(
            distance,
            ((0.25 * PITCH_LENGTH_MM) ** 2 + (0.25 * PITCH_WIDTH_MM) ** 2)
            ** 0.5,
        )
