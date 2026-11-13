"""Headless physics for flicking Subbuteo pieces and the ball."""

from dataclasses import dataclass
from math import ceil, hypot


PITCH_LENGTH_MM = 1200.0
PITCH_WIDTH_MM = 800.0
BALL_RADIUS_MM = 11.0
PIECE_RADIUS_MM = 9.25
GOAL_WIDTH_MM = 120.0
GOAL_DEPTH_MM = 60.0
SHOOTING_AREA_DEPTH_MM = 280.0
WALL_RESTITUTION = 0.65
PIECE_RESTITUTION = 0.6
NET_RESTITUTION = 0.3
MAX_FLICK_SPEED_MM_S = 1200.0
MAX_DRAG_MM = 300.0
MIN_FLICK_DRAG_MM = 4.0
PIECE_FRICTION_MM_S2 = 1200.0
BALL_FRICTION_MM_S2 = 900.0
FIXED_STEP_S = 1.0 / 120.0

HOME = "home"
AWAY = "away"


@dataclass(frozen=True)
class Vector2:
    """A small immutable 2D vector used by the headless physics engine."""

    x: float
    y: float

    def __add__(self, other: "Vector2") -> "Vector2":
        """Return the sum of this vector and another vector."""
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2") -> "Vector2":
        """Return the difference between this vector and another vector."""
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2":
        """Return this vector scaled by a scalar."""
        return Vector2(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: float) -> "Vector2":
        """Return this vector divided by a scalar."""
        return Vector2(self.x / scalar, self.y / scalar)

    @property
    def length(self) -> float:
        """Return this vector's magnitude."""
        return hypot(self.x, self.y)

    def normalized(self) -> "Vector2":
        """Return a unit vector, or the zero vector when this vector is empty."""
        magnitude = self.length
        if magnitude == 0:
            return Vector2(0.0, 0.0)
        return self / magnitude

    def dot(self, other: "Vector2") -> float:
        """Return the dot product with another vector."""
        return self.x * other.x + self.y * other.y


@dataclass
class Body:
    """A circular physical body whose position is normalized to the pitch."""

    body_id: str
    position: Vector2
    radius_mm: float
    mass: float
    team: str | None = None
    velocity: Vector2 = Vector2(0.0, 0.0)
    movable: bool = True
    kind: str = "piece"
    friction_mm_s2: float = PIECE_FRICTION_MM_S2

    @property
    def position_mm(self) -> Vector2:
        """Return the normalized position converted to pitch millimeters."""
        return Vector2(
            self.position.x * PITCH_LENGTH_MM,
            self.position.y * PITCH_WIDTH_MM,
        )


@dataclass(frozen=True)
class GoalEvent:
    """Describe a goal scored by one team."""

    scoring_team: str
    goal_side: str


class PhysicsWorld:
    """Advance piece and ball motion without importing a graphics library."""

    def __init__(self, pieces: list[Body], ball: Body) -> None:
        """Create a physics world from field pieces and a ball.

        Args:
            pieces: The movable field pieces and stationary goalkeepers.
            ball: The ball body.
        """
        self.pieces = pieces
        self._starting_piece_positions = {
            piece.body_id: piece.position for piece in pieces
        }
        self.ball = ball
        self.possession: str | None = None
        self.home_score = 0
        self.away_score = 0
        self.last_goal: GoalEvent | None = None
        self.ball_in_net: str | None = None
        self.last_flick_team: str | None = None
        self._shot_start_x: float | None = None

    @classmethod
    def demo_match(cls) -> "PhysicsWorld":
        """Create a default 11-a-side layout for the physics match demo."""
        pieces: list[Body] = []
        for index in range(10):
            y = 0.1 + index * (0.8 / 9)
            pieces.append(
                Body(
                    body_id=f"home-{index}",
                    position=Vector2(0.25, y),
                    radius_mm=PIECE_RADIUS_MM,
                    mass=22.0,
                    team=HOME,
                    friction_mm_s2=PIECE_FRICTION_MM_S2,
                )
            )
            pieces.append(
                Body(
                    body_id=f"away-{index}",
                    position=Vector2(0.75, y),
                    radius_mm=PIECE_RADIUS_MM,
                    mass=22.0,
                    team=AWAY,
                    friction_mm_s2=PIECE_FRICTION_MM_S2,
                )
            )

        pieces.extend(
            (
                Body(
                    body_id="home-goalkeeper",
                    position=Vector2(22.0 / PITCH_LENGTH_MM, 0.5),
                    radius_mm=10.5,
                    mass=30.0,
                    team=HOME,
                    movable=False,
                    kind="goalkeeper",
                ),
                Body(
                    body_id="away-goalkeeper",
                    position=Vector2(1.0 - 22.0 / PITCH_LENGTH_MM, 0.5),
                    radius_mm=10.5,
                    mass=30.0,
                    team=AWAY,
                    movable=False,
                    kind="goalkeeper",
                ),
            )
        )
        ball = Body(
            body_id="ball",
            position=Vector2(0.5, 0.5),
            radius_mm=BALL_RADIUS_MM,
            mass=2.7,
            kind="ball",
            friction_mm_s2=BALL_FRICTION_MM_S2,
        )
        return cls(pieces, ball)

    def flick(self, piece_id: str, pull_mm: Vector2) -> bool:
        """Apply a drag-and-release flick to one field piece.

        The pull vector points from the piece toward the cursor; the piece moves
        in the opposite direction when released.

        Args:
            piece_id: Identifier of the field piece to flick.
            pull_mm: Drag vector in pitch millimeters.

        Returns:
            bool: Whether a flick impulse was applied.

        Raises:
            ValueError: If the identifier is unknown or refers to a goalkeeper.
        """
        piece = next(
            (body for body in self.pieces if body.body_id == piece_id),
            None,
        )
        if piece is None:
            raise ValueError(f"Unknown piece: {piece_id}")
        if not piece.movable:
            raise ValueError("Goalkeeper pieces cannot be flicked.")

        pull_length = pull_mm.length
        if pull_length < MIN_FLICK_DRAG_MM:
            return False

        drag = pull_mm if pull_length <= MAX_DRAG_MM else (
            pull_mm * (MAX_DRAG_MM / pull_length)
        )
        self.last_flick_team = piece.team
        self._shot_start_x = self.ball.position.x
        self.possession = piece.team
        self.ball_in_net = None
        piece.velocity = piece.velocity - (
            drag.normalized()
            * (drag.length * MAX_FLICK_SPEED_MM_S / MAX_DRAG_MM)
        )
        return True

    def step(self, elapsed_seconds: float) -> None:
        """Advance the world in small steps and resolve collisions.

        Args:
            elapsed_seconds: Wall-clock seconds to simulate. Non-positive values
                do not advance the world.
        """
        self.last_goal = None
        if elapsed_seconds <= 0:
            return

        step_count = max(1, ceil(elapsed_seconds / FIXED_STEP_S))
        step_seconds = elapsed_seconds / step_count
        for _ in range(step_count):
            self._step_once(step_seconds)

    def reset_ball(self) -> None:
        """Place a stationary ball at the center spot for a restart."""
        self.ball.position = Vector2(0.5, 0.5)
        self.ball.velocity = Vector2(0.0, 0.0)
        self.ball_in_net = None
        self.last_flick_team = None
        self._shot_start_x = None

    def reset_pieces(self) -> None:
        """Restore every game piece to its starting position and stop it."""
        for piece in self.pieces:
            piece.position = self._starting_piece_positions[piece.body_id]
            piece.velocity = Vector2(0.0, 0.0)

    def reset_pieces_and_ball(self) -> None:
        """Restore the game pieces and place a stationary ball at center."""
        self.reset_pieces()
        self.reset_ball()

    def _step_once(self, elapsed_seconds: float) -> None:
        for body in (*self.pieces, self.ball):
            if body.movable:
                body.position = Vector2(
                    body.position.x
                    + body.velocity.x * elapsed_seconds / PITCH_LENGTH_MM,
                    body.position.y
                    + body.velocity.y * elapsed_seconds / PITCH_WIDTH_MM,
                )
                body.velocity = self._apply_friction(
                    body.velocity,
                    body.friction_mm_s2 * elapsed_seconds,
                )

        for index, first in enumerate(self.pieces):
            for second in self.pieces[index + 1 :]:
                self._resolve_collision(first, second)
            self._resolve_collision(first, self.ball)

        for piece in self.pieces:
            self._resolve_field_boundaries(piece)
        self._resolve_ball_boundaries()

    @staticmethod
    def _apply_friction(velocity: Vector2, drop: float) -> Vector2:
        """Reduce speed by rolling friction without reversing direction."""
        speed = velocity.length
        if speed <= drop:
            return Vector2(0.0, 0.0)
        return velocity * ((speed - drop) / speed)

    @staticmethod
    def _resolve_collision(first: Body, second: Body) -> None:
        """Separate overlapping circles and apply a restitution impulse."""
        first_position = first.position_mm
        second_position = second.position_mm
        offset = first_position - second_position
        distance = offset.length
        minimum_distance = first.radius_mm + second.radius_mm
        if distance >= minimum_distance:
            return

        normal = offset.normalized()
        if distance == 0:
            normal = Vector2(1.0, 0.0)
        inverse_first = 1.0 / first.mass if first.movable else 0.0
        inverse_second = 1.0 / second.mass if second.movable else 0.0
        inverse_total = inverse_first + inverse_second
        if inverse_total == 0:
            return

        overlap = minimum_distance - distance
        first_position = first_position + normal * (
            overlap * inverse_first / inverse_total
        )
        second_position = second_position - normal * (
            overlap * inverse_second / inverse_total
        )
        first.position = Vector2(
            first_position.x / PITCH_LENGTH_MM,
            first_position.y / PITCH_WIDTH_MM,
        )
        second.position = Vector2(
            second_position.x / PITCH_LENGTH_MM,
            second_position.y / PITCH_WIDTH_MM,
        )

        relative_velocity = first.velocity - second.velocity
        speed_along_normal = relative_velocity.dot(normal)
        if speed_along_normal >= 0:
            return

        restitution = PIECE_RESTITUTION
        impulse = -(1.0 + restitution) * speed_along_normal / inverse_total
        impulse_vector = normal * impulse
        if first.movable:
            first.velocity = first.velocity + impulse_vector * inverse_first
        if second.movable:
            second.velocity = second.velocity - impulse_vector * inverse_second

    @staticmethod
    def _reflect_velocity(body: Body, axis: str, restitution: float) -> None:
        """Reflect one velocity component using the requested restitution."""
        component = body.velocity.x if axis == "x" else body.velocity.y
        reflected = -component * restitution
        if axis == "x":
            body.velocity = Vector2(reflected, body.velocity.y)
        else:
            body.velocity = Vector2(body.velocity.x, reflected)

    def _resolve_field_boundaries(self, body: Body) -> None:
        """Keep a field piece inside the pitch with perimeter rebound."""
        if not body.movable:
            return
        radius_x = body.radius_mm / PITCH_LENGTH_MM
        radius_y = body.radius_mm / PITCH_WIDTH_MM
        if body.position.x < radius_x:
            body.position = Vector2(radius_x, body.position.y)
            if body.velocity.x < 0:
                self._reflect_velocity(body, "x", WALL_RESTITUTION)
        elif body.position.x > 1.0 - radius_x:
            body.position = Vector2(1.0 - radius_x, body.position.y)
            if body.velocity.x > 0:
                self._reflect_velocity(body, "x", WALL_RESTITUTION)
        if body.position.y < radius_y:
            body.position = Vector2(body.position.x, radius_y)
            if body.velocity.y < 0:
                self._reflect_velocity(body, "y", WALL_RESTITUTION)
        elif body.position.y > 1.0 - radius_y:
            body.position = Vector2(body.position.x, 1.0 - radius_y)
            if body.velocity.y > 0:
                self._reflect_velocity(body, "y", WALL_RESTITUTION)

    def _resolve_ball_boundaries(self) -> None:
        """Resolve touchline, goal-line, and post-goal net contacts."""
        ball = self.ball
        radius_x = ball.radius_mm / PITCH_LENGTH_MM
        radius_y = ball.radius_mm / PITCH_WIDTH_MM
        goal_half_opening = (GOAL_WIDTH_MM / 2.0 - ball.radius_mm)
        ball_y_mm = ball.position.y * PITCH_WIDTH_MM
        in_goal_mouth = abs(ball_y_mm - PITCH_WIDTH_MM / 2.0) <= goal_half_opening

        if ball.position.y < radius_y:
            ball.position = Vector2(ball.position.x, radius_y)
            if ball.velocity.y < 0:
                self._reflect_velocity(ball, "y", WALL_RESTITUTION)
        elif ball.position.y > 1.0 - radius_y:
            ball.position = Vector2(ball.position.x, 1.0 - radius_y)
            if ball.velocity.y > 0:
                self._reflect_velocity(ball, "y", WALL_RESTITUTION)

        if self.ball_in_net is not None:
            self._resolve_net_boundaries()
            return

        if ball.position.x < 0.0 and ball.velocity.x < 0:
            if in_goal_mouth:
                self._handle_goal_line("home")
            else:
                ball.position = Vector2(radius_x, ball.position.y)
                self._reflect_velocity(ball, "x", WALL_RESTITUTION)
                self._transfer_possession()
        elif ball.position.x > 1.0 and ball.velocity.x > 0:
            if in_goal_mouth:
                self._handle_goal_line("away")
            else:
                ball.position = Vector2(1.0 - radius_x, ball.position.y)
                self._reflect_velocity(ball, "x", WALL_RESTITUTION)
                self._transfer_possession()

        if ball.position.x >= 0.0 and ball.velocity.x < 0:
            if ball.position.x < radius_x and not in_goal_mouth:
                ball.position = Vector2(radius_x, ball.position.y)
                self._reflect_velocity(ball, "x", WALL_RESTITUTION)
                self._transfer_possession()
        elif ball.position.x <= 1.0 and ball.velocity.x > 0:
            if ball.position.x > 1.0 - radius_x and not in_goal_mouth:
                ball.position = Vector2(1.0 - radius_x, ball.position.y)
                self._reflect_velocity(ball, "x", WALL_RESTITUTION)
                self._transfer_possession()

    def _handle_goal_line(self, goal_side: str) -> None:
        """Score a valid goal or rebound an ineligible goal-mouth attempt."""
        target_team = HOME if goal_side == "home" else AWAY
        own_goal = self.last_flick_team == target_team
        shot_start_x = self._shot_start_x
        if self.last_flick_team is None:
            valid_goal = False
        elif own_goal:
            valid_goal = True
        elif shot_start_x is None:
            valid_goal = False
        elif self.last_flick_team == HOME:
            valid_goal = (
                shot_start_x
                > 1.0 - SHOOTING_AREA_DEPTH_MM / PITCH_LENGTH_MM
            )
        else:
            valid_goal = shot_start_x < SHOOTING_AREA_DEPTH_MM / PITCH_LENGTH_MM

        if valid_goal:
            scoring_team = AWAY if target_team == HOME else HOME
            if scoring_team == HOME:
                self.home_score += 1
            else:
                self.away_score += 1
            self.last_goal = GoalEvent(scoring_team, goal_side)
            self.ball_in_net = goal_side
        else:
            radius_x = self.ball.radius_mm / PITCH_LENGTH_MM
            x = radius_x if goal_side == "home" else 1.0 - radius_x
            self.ball.position = Vector2(x, self.ball.position.y)
            self._reflect_velocity(self.ball, "x", WALL_RESTITUTION)
            self._transfer_possession()

    def _resolve_net_boundaries(self) -> None:
        """Apply damped rebounds inside the goal net."""
        goal_side = self.ball_in_net
        if goal_side is None:
            return

        ball = self.ball
        radius_x = ball.radius_mm / PITCH_LENGTH_MM
        half_net_width = (GOAL_WIDTH_MM / 2.0 - ball.radius_mm) / PITCH_WIDTH_MM
        lower_y = 0.5 - half_net_width
        upper_y = 0.5 + half_net_width
        if ball.position.y < lower_y:
            ball.position = Vector2(ball.position.x, lower_y)
            if ball.velocity.y < 0:
                self._reflect_velocity(ball, "y", NET_RESTITUTION)
        elif ball.position.y > upper_y:
            ball.position = Vector2(ball.position.x, upper_y)
            if ball.velocity.y > 0:
                self._reflect_velocity(ball, "y", NET_RESTITUTION)

        if goal_side == "home":
            back_wall = (-GOAL_DEPTH_MM + ball.radius_mm) / PITCH_LENGTH_MM
            if ball.position.x < back_wall:
                ball.position = Vector2(back_wall, ball.position.y)
                if ball.velocity.x < 0:
                    self._reflect_velocity(ball, "x", NET_RESTITUTION)
            elif ball.position.x > 0.0:
                self.ball_in_net = None
        else:
            back_wall = 1.0 + (GOAL_DEPTH_MM - ball.radius_mm) / PITCH_LENGTH_MM
            if ball.position.x > back_wall:
                ball.position = Vector2(back_wall, ball.position.y)
                if ball.velocity.x > 0:
                    self._reflect_velocity(ball, "x", NET_RESTITUTION)
            elif ball.position.x < 1.0:
                self.ball_in_net = None

    def _transfer_possession(self) -> None:
        """Give possession to the player opposing the last flicking team."""
        if self.last_flick_team is not None:
            self.possession = AWAY if self.last_flick_team == HOME else HOME
