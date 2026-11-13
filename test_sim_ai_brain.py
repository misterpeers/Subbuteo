"""Focused tests for headless AI player distance and contact estimates."""

import unittest
from math import sqrt

from sim_ai_brain import estimate_contact_strength
from sim_physics import (
    BALL_RADIUS_MM,
    HOME,
    MAX_FLICK_SPEED_MM_S,
    MAX_DRAG_MM,
    MIN_FLICK_DRAG_MM,
    PIECE_FRICTION_MM_S2,
    PIECE_RADIUS_MM,
    PITCH_LENGTH_MM,
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


if __name__ == "__main__":
    unittest.main()
