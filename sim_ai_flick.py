"""Headless helpers for AI-controlled Subbuteo player-piece flicks."""

from math import isfinite
from typing import Literal

from sim_physics import (
    MAX_DRAG_MM,
    PITCH_LENGTH_MM,
    PITCH_WIDTH_MM,
    PhysicsWorld,
    Vector2,
)

AimMode = Literal["marker", "ball"]


def distance_between_mm(start: Vector2, end: Vector2) -> float:
    """Measure the pitch-plane distance between normalized positions.

    Args:
        start: The starting pitch position in normalized coordinates.
        end: The ending pitch position in normalized coordinates.

    Returns:
        float: Euclidean distance in millimeters.
    """
    return Vector2(
        (end.x - start.x) * PITCH_LENGTH_MM,
        (end.y - start.y) * PITCH_WIDTH_MM,
    ).length


def aim_target_position(
    world: PhysicsWorld,
    marker_position: Vector2,
    aim_mode: AimMode,
) -> Vector2:
    """Return the active AI aim target.

    Args:
        world: Physics world containing the ball.
        marker_position: Target marker location in normalized pitch coordinates.
        aim_mode: Whether the AI should aim at the marker or ball.

    Returns:
        Vector2: The active target location in normalized pitch coordinates.

    Raises:
        ValueError: If the aim mode is not supported.
    """
    if aim_mode == "marker":
        return marker_position
    if aim_mode == "ball":
        return world.ball.position
    raise ValueError(f"Unknown AI aim mode: {aim_mode}")


def flick_toward_target(
    world: PhysicsWorld,
    piece_id: str,
    target_position: Vector2,
    strength: float,
) -> bool:
    """Flick a player piece toward a normalized pitch target.

    Args:
        world: Physics world containing the player piece.
        piece_id: Identifier of the piece to flick.
        target_position: Target location in normalized pitch coordinates.
        strength: Flick strength from 0.0 (no impulse) to 1.0 (maximum).

    Returns:
        bool: Whether the physics engine applied a flick.

    Raises:
        ValueError: If strength is outside the inclusive range [0.0, 1.0] or
            the piece identifier is unknown.
    """
    if not isfinite(strength) or not 0.0 <= strength <= 1.0:
        raise ValueError("Flick strength must be between 0.0 and 1.0.")

    piece = next(
        (body for body in world.pieces if body.body_id == piece_id),
        None,
    )
    if piece is None:
        raise ValueError(f"Unknown piece: {piece_id}")

    direction_mm = Vector2(
        (target_position.x - piece.position.x) * PITCH_LENGTH_MM,
        (target_position.y - piece.position.y) * PITCH_WIDTH_MM,
    )
    if strength == 0.0 or direction_mm.length == 0.0:
        return False

    pull_mm = direction_mm.normalized() * (-MAX_DRAG_MM * strength)
    return world.flick(piece_id, pull_mm)
