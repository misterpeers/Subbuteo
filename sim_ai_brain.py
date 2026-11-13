"""Headless AI player calculations for basic ball-contact decisions."""

from dataclasses import dataclass
from math import sqrt

from sim_ai_flick import distance_between_mm
from sim_physics import (
    MAX_DRAG_MM,
    MAX_FLICK_SPEED_MM_S,
    MIN_FLICK_DRAG_MM,
    PhysicsWorld,
)


@dataclass(frozen=True)
class ContactEstimate:
    """Describe the gap and flick strength estimated for first ball contact."""

    gap_mm: float
    strength_percent: float | None


def estimate_contact_strength(
    world: PhysicsWorld,
    piece_id: str,
) -> ContactEstimate:
    """Estimate the strength needed to roll a player piece into the ball.

    The calculation assumes a straight, unobstructed path and constant
    piece-friction deceleration. It excludes rebounds and other collisions.

    Args:
        world: Physics world containing the player piece and ball.
        piece_id: Identifier of the player piece to evaluate.

    Returns:
        ContactEstimate: Edge-to-edge gap and required strength percentage.
            A ``None`` strength means the estimated gap exceeds maximum range.

    Raises:
        ValueError: If the piece identifier is unknown or its friction is
            negative.
    """
    piece = next(
        (body for body in world.pieces if body.body_id == piece_id),
        None,
    )
    if piece is None:
        raise ValueError(f"Unknown piece: {piece_id}")
    if piece.friction_mm_s2 < 0.0:
        raise ValueError("Piece friction must not be negative.")

    center_distance_mm = distance_between_mm(piece.position, world.ball.position)
    gap_mm = max(
        0.0,
        center_distance_mm - piece.radius_mm - world.ball.radius_mm,
    )
    if gap_mm == 0.0:
        return ContactEstimate(gap_mm, 0.0)

    minimum_strength_percent = 100.0 * MIN_FLICK_DRAG_MM / MAX_DRAG_MM
    if piece.friction_mm_s2 == 0.0:
        return ContactEstimate(gap_mm, minimum_strength_percent)

    required_speed_mm_s = sqrt(2.0 * piece.friction_mm_s2 * gap_mm)
    if required_speed_mm_s > MAX_FLICK_SPEED_MM_S:
        return ContactEstimate(gap_mm, None)

    strength_percent = max(
        minimum_strength_percent,
        100.0 * required_speed_mm_s / MAX_FLICK_SPEED_MM_S,
    )
    return ContactEstimate(gap_mm, strength_percent)
