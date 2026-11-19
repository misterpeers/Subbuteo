"""Focused tests for headless AI flick aiming and power control."""

import unittest
from unittest.mock import Mock, patch

import pygame

from demo_ai_flick import (
    DEFAULT_BALL_TRAINING_PIECE_POSITION,
    DEFAULT_TEAMMATE_POSITION,
    DEFAULT_THIRD_PIECE_POSITION,
    DummyPiece,
    TRAINING_PIECE_NUMBERS,
    _add_dummy_body,
    _coordinate_rows,
    _create_training_world,
    _create_world,
    _draw_coordinates,
    _draw_ruler,
    _draw_training_player,
    _training_player_pieces,
)
from sim_ai_flick import (
    aim_target_position,
    distance_between_mm,
    flick_toward_target,
)
from sim_pitch import PENALTY_AREA_WIDTH_MM
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

    def test_three_pieces_are_limited_to_ball_possession_training(self) -> None:
        """Only ball-enabled training creates the two extra player pieces."""
        free_play = _create_world()
        target_training = _create_training_world()
        ball_training = _create_training_world(include_ball=True)

        self.assertEqual(len(free_play.pieces), 1)
        self.assertEqual(len(_training_player_pieces(target_training)), 1)
        ball_player_pieces = _training_player_pieces(ball_training)
        self.assertEqual(len(ball_player_pieces), 3)
        expected_positions = [
            DEFAULT_BALL_TRAINING_PIECE_POSITION,
            DEFAULT_TEAMMATE_POSITION,
            DEFAULT_THIRD_PIECE_POSITION,
        ]
        self.assertEqual(
            [piece.position for piece in ball_player_pieces],
            expected_positions,
        )
        expected_edge_y = (
            PITCH_WIDTH_MM - PENALTY_AREA_WIDTH_MM
        ) / (2 * PITCH_WIDTH_MM)
        self.assertAlmostEqual(
            DEFAULT_TEAMMATE_POSITION.y,
            expected_edge_y,
        )
        self.assertAlmostEqual(
            DEFAULT_THIRD_PIECE_POSITION.y,
            1.0 - expected_edge_y,
        )

    def test_coordinate_rows_use_stable_numbers_and_exclude_dummies(self) -> None:
        """Positions follow piece IDs, update after movement, and hide an absent ball."""
        world = _create_training_world(include_ball=True)
        _add_dummy_body(world, DummyPiece(Vector2(0.7, 0.5), "x"), 0)
        world.pieces.reverse()
        piece = next(piece for piece in world.pieces if piece.body_id == "ai-piece-2")
        piece.position = Vector2(0.1234, 0.8765)

        rows = _coordinate_rows(world, ball_enabled=True)

        self.assertEqual([label for label, _ in rows], ["P1", "P2", "P3", "Ball"])
        self.assertEqual(rows[1][1], Vector2(0.1234, 0.8765))
        self.assertEqual(rows[-1][1], world.ball.position)
        self.assertEqual(_coordinate_rows(world, ball_enabled=False)[-1], ("Ball", None))
        self.assertEqual(TRAINING_PIECE_NUMBERS[piece.body_id], 2)

    def test_training_number_and_coordinate_panel_render(self) -> None:
        """Draw the number and both coordinate units, including ball-off state."""
        pygame.font.init()
        field = pygame.Rect(30, 30, 522, 348)
        surface = pygame.Surface((640, 480))
        world = _create_training_world(include_ball=True)
        real_font = pygame.font.Font(None, 12)
        font = Mock(wraps=real_font)
        with patch("demo_ai_flick.pygame.font.Font", return_value=font):
            _draw_training_player(surface, field, world.pieces[1].position, 2)
            _draw_coordinates(surface, field, world, ball_enabled=True)
            _draw_coordinates(surface, field, world, ball_enabled=False)
        rendered = [call.args[0] for call in font.render.call_args_list]
        self.assertIn("2", rendered)
        self.assertIn("0.2500 / 300.0", rendered)
        self.assertIn("0.5000 / 400.0", rendered)
        self.assertIn("OFF", rendered)

    def test_coordinate_panel_shows_pitch_behind_it(self) -> None:
        """The coordinate panel blends with whatever is behind its background."""
        pygame.font.init()
        field = pygame.Rect(30, 30, 522, 348)
        surfaces = [pygame.Surface((640, 480)) for _ in range(2)]
        surfaces[0].fill((20, 170, 50))
        surfaces[1].fill((20, 40, 200))
        world = _create_world()

        for surface in surfaces:
            _draw_coordinates(surface, field, world, ball_enabled=True)

        position = (field.right - 8, field.top + 12)
        green_pixel = surfaces[0].get_at(position)
        blue_pixel = surfaces[1].get_at(position)
        self.assertGreater(green_pixel.g, blue_pixel.g)
        self.assertLess(green_pixel.b, blue_pixel.b)

    def test_rulers_cover_both_pitch_axes(self) -> None:
        """The Y ruler runs top-to-bottom and the existing X ruler remains."""
        pygame.font.init()
        field = pygame.Rect(30, 30, 600, 400)
        surface = pygame.Surface((660, 460))
        with patch("demo_ai_flick.pygame.draw.line", wraps=pygame.draw.line) as line:
            _draw_ruler(surface, field)
        segments = [(call.args[2], call.args[3]) for call in line.call_args_list]
        self.assertEqual(len(segments), 25 + 17)
        self.assertTrue(any(start[0] == field.left + 2 and start[1] == field.top for start, _ in segments))
        self.assertTrue(any(start[0] == field.left + 2 and start[1] == field.bottom - 1 for start, _ in segments))
        self.assertTrue(any(start[1] == field.bottom - 2 and start[0] == field.right - 1 for start, _ in segments))

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
