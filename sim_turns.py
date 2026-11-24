"""Headless turn controller for AI-played attacking sequences.

The controller owns everything about a sequence of flicks that is not drawing:
touch counts, the active piece, contact tracking, pass reception, possession
changes, goals, and the pause between flicks. A demo or match view only steps
it, renders the world, and reacts to the events it returns.
"""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

from sim_ai_brain import FlickPlan, Obstacle, plan_team_flick
from sim_ai_flick import distance_between_mm, flick_toward_target
from sim_ai_verify import (
    CONTACT_TOLERANCE_MM,
    PASS_MOVEMENT_THRESHOLD_MM,
    plan_verified_team_flick,
)
from sim_physics import (
    HOME,
    Body,
    PhysicsWorld,
    Vector2,
    attack_direction,
    opposing_team,
)

DEFAULT_FLICK_DELAY_SECONDS = 1.0
MAX_CONSECUTIVE_TOUCHES = 3

TurnEventKind = Literal[
    "flick",
    "pass_received",
    "goal",
    "possession_lost",
    "no_plan",
    "flick_failed",
]
PossessionLossReason = Literal[
    "missed_flick",
    "opponent_contact",
    "possession_transfer",
]


@dataclass(frozen=True)
class TurnEvent:
    """Describe something that happened during one controller update.

    Attributes:
        kind: The type of event.
        team: The team the event concerns. For ``possession_lost`` this is the
            team that lost the ball; for ``goal`` it is the scoring team.
        piece_id: The player piece involved, if any.
        plan: The flick plan that was launched, for ``flick`` events.
        reason: Why possession was lost, for ``possession_lost`` events.
    """

    kind: TurnEventKind
    team: str
    piece_id: str | None = None
    plan: FlickPlan | None = None
    reason: PossessionLossReason | None = None


@dataclass
class DecisionStats:
    """Record how each flick decision was made and how long it took.

    Attributes:
        durations_seconds: Time taken by each decision, in order.
        planned: Decisions that used a geometric planner candidate.
        sampled: Decisions that fell back to a sampled flick.
        none: Decisions that found no usable flick.
    """

    durations_seconds: list[float] = field(default_factory=list)
    planned: int = 0
    sampled: int = 0
    none: int = 0

    @property
    def decisions(self) -> int:
        """Return the number of decisions recorded."""
        return len(self.durations_seconds)

    def record(self, duration_seconds: float, source: str) -> None:
        """Add one decision.

        Args:
            duration_seconds: How long the decision took.
            source: ``"planned"``, ``"sampled"`` or ``"none"``.

        Raises:
            ValueError: If the source is not recognised.
        """
        if source == "planned":
            self.planned += 1
        elif source == "sampled":
            self.sampled += 1
        elif source == "none":
            self.none += 1
        else:
            raise ValueError(f"Unknown decision source: {source}")
        self.durations_seconds.append(duration_seconds)


class TurnController:
    """Drive one team's attack, flick by flick, over a physics world.

    The controller is independent of Pygame and of any scenario editor. It
    plans each flick with the shared AI planner, applies it through the shared
    physics engine, and decides when the attack has ended. It records where
    the ball stood before each flick of the current attack in ``ball_stops``,
    so the planner can avoid returning the ball to the same place in a loop.
    """

    def __init__(
        self,
        world: PhysicsWorld,
        attacking_team: str = HOME,
        *,
        flick_delay_seconds: float = DEFAULT_FLICK_DELAY_SECONDS,
        hand_over_on_loss: bool = False,
        verify_flicks: bool = True,
    ) -> None:
        """Create a controller and start an attack for the given team.

        Args:
            world: The physics world to play in.
            attacking_team: The team that holds possession initially.
            flick_delay_seconds: Pause between a settled flick and the next.
            hand_over_on_loss: When ``True``, a lost possession passes the
                attack to the opposing team and play continues. When
                ``False``, the loss ends the sequence and is recorded in
                ``outcome``.
            verify_flicks: When ``True``, each planned flick is simulated on a
                cloned world first and rejected if it would lose possession.
                When ``False``, the planner's first choice is used unchecked.

        Raises:
            ValueError: If the delay is negative or the team is unknown.
        """
        if flick_delay_seconds < 0.0:
            raise ValueError("Flick delay must not be negative.")
        attack_direction(attacking_team)
        self.world = world
        self.flick_delay_seconds = flick_delay_seconds
        self.hand_over_on_loss = hand_over_on_loss
        self.verify_flicks = verify_flicks
        self.decision_stats = DecisionStats()
        self.attacking_team = attacking_team
        self.reset(attacking_team)

    @property
    def delay_remaining(self) -> float:
        """Return the seconds left before the next flick may be planned."""
        return self._delay_remaining

    @property
    def finished(self) -> bool:
        """Return whether the sequence has ended with a recorded outcome."""
        return self.outcome is not None

    def attacking_pieces(self) -> list[Body]:
        """Return the flickable field pieces of the attacking team."""
        return [
            piece
            for piece in self.world.pieces
            if piece.team == self.attacking_team
            and piece.movable
            and piece.kind == "piece"
        ]

    def reset(self, attacking_team: str | None = None) -> None:
        """Clear all sequence state and give possession to a team.

        Piece and ball positions are left as they are.

        Args:
            attacking_team: The team to attack; defaults to the current one.

        Raises:
            ValueError: If the team is unknown.
        """
        if attacking_team is not None:
            attack_direction(attacking_team)
            self.attacking_team = attacking_team
        self.outcome: TurnEvent | None = None
        self.flicks_taken = 0
        self.touch_counts: dict[str, int] = {
            piece.body_id: 0 for piece in self.world.pieces
        }
        attackers = self.attacking_pieces()
        self.active_piece_id: str | None = (
            attackers[0].body_id if attackers else None
        )
        self.world.possession = self.attacking_team
        self._delay_remaining = 0.0
        self._pending_piece_id: str | None = None
        self._pending_contacted = False
        self._pending_ball_start: Vector2 | None = None
        self._pending_pass_received_by: str | None = None
        self._pending_touch_reset_piece_id: str | None = None
        self._opponent_contact = False
        self.ball_stops: list[Vector2] = []

    def update(
        self,
        elapsed_seconds: float,
        obstacles: list[Obstacle] | None = None,
    ) -> list[TurnEvent]:
        """Advance the world and, when appropriate, launch the next flick.

        Args:
            elapsed_seconds: Time to simulate.
            obstacles: Areas the AI should avoid when planning the next flick.

        Returns:
            list[TurnEvent]: Events produced by this update, in order.
        """
        events: list[TurnEvent] = []
        if self.finished:
            return events

        self.world.step(elapsed_seconds)
        self._track_contacts()

        goal = self.world.last_goal
        if goal is not None:
            event = TurnEvent("goal", goal.scoring_team)
            self.outcome = event
            events.append(event)
            return events

        if not self._world_is_settled():
            return events

        completed_piece_id = self._pending_piece_id
        if completed_piece_id is not None:
            self._pending_piece_id = None
            self._delay_remaining = self.flick_delay_seconds
            if not self._pending_contacted:
                self._lose_possession("missed_flick", events)
            elif self._opponent_contact:
                self._lose_possession("opponent_contact", events)
            elif self.world.possession != self.attacking_team:
                self._lose_possession("possession_transfer", events)
            if self.finished:
                return events
            if events:
                return events

            receiver_id = self._pending_pass_received_by
            if receiver_id is not None:
                self.touch_counts[completed_piece_id] = 0
                self.active_piece_id = receiver_id
                events.append(
                    TurnEvent(
                        "pass_received",
                        self.attacking_team,
                        piece_id=receiver_id,
                    )
                )
            self._pending_ball_start = None
            self._pending_pass_received_by = None
            return events

        if self._delay_remaining > 0.0:
            self._delay_remaining = max(
                0.0,
                self._delay_remaining - elapsed_seconds,
            )
            if self._delay_remaining > 0.0:
                return events

        self._launch_next_flick(obstacles or [], events)
        return events

    def _track_contacts(self) -> None:
        """Record this frame's ball contacts against the pending flick."""
        contacts = self.world.last_ball_contacts
        pending_id = self._pending_piece_id
        if pending_id is None:
            return

        if pending_id in contacts:
            self._pending_contacted = True
            reset_id = self._pending_touch_reset_piece_id
            if reset_id is not None:
                self.touch_counts[reset_id] = 0
                self._pending_touch_reset_piece_id = None

        for body_id in contacts:
            body = self._body(body_id)
            if body.team is not None and body.team != self.attacking_team:
                self._opponent_contact = True

        if (
            self._pending_ball_start is not None
            and self._pending_pass_received_by is None
            and distance_between_mm(
                self.world.ball.position,
                self._pending_ball_start,
            )
            > PASS_MOVEMENT_THRESHOLD_MM
        ):
            for piece in self.attacking_pieces():
                if piece.body_id != pending_id and piece.body_id in contacts:
                    self._pending_pass_received_by = piece.body_id
                    break

    def _world_is_settled(self) -> bool:
        """Return whether every movable piece and the ball have stopped."""
        return self.world.ball.velocity.length == 0.0 and all(
            piece.velocity.length == 0.0
            for piece in self.world.pieces
            if piece.movable
        )

    def _body(self, body_id: str) -> Body:
        """Look up a world body by identifier."""
        return next(
            body for body in self.world.pieces if body.body_id == body_id
        )

    def _lose_possession(
        self,
        reason: PossessionLossReason,
        events: list[TurnEvent],
    ) -> None:
        """End the sequence, or hand the attack over, after a lost ball."""
        event = TurnEvent(
            "possession_lost",
            self.attacking_team,
            reason=reason,
        )
        events.append(event)
        if not self.hand_over_on_loss:
            self.outcome = event
            return
        flicks_taken = self.flicks_taken
        self.reset(opposing_team(self.attacking_team))
        self.flicks_taken = flicks_taken
        self._delay_remaining = self.flick_delay_seconds

    def _launch_next_flick(
        self,
        obstacles: list[Obstacle],
        events: list[TurnEvent],
    ) -> None:
        """Plan and apply the next flick, or end the sequence if none exists."""
        attackers = self.attacking_pieces()
        started = perf_counter()
        source = "planned"
        self.ball_stops.append(self.world.ball.position)
        if self.verify_flicks:
            verified = plan_verified_team_flick(
                self.world,
                self.attacking_team,
                self.touch_counts,
                obstacles,
                visited_ball_positions=self.ball_stops,
            )
            plan = verified.plan if verified is not None else None
            if verified is not None:
                source = verified.source
        else:
            plan = plan_team_flick(
                [
                    (
                        piece.body_id,
                        piece.position,
                        self.touch_counts.get(piece.body_id, 0),
                    )
                    for piece in attackers
                ],
                self.world.ball.position,
                obstacles,
                attack_direction=attack_direction(self.attacking_team),
            )
        usable = plan is not None and plan.flicking_piece_id is not None
        self.decision_stats.record(
            perf_counter() - started,
            source if usable else "none",
        )
        if plan is None or plan.flicking_piece_id is None:
            self.outcome = TurnEvent("no_plan", self.attacking_team)
            events.append(self.outcome)
            return

        piece = self._body(plan.flicking_piece_id)
        previous_piece_id = self.active_piece_id
        self._pending_touch_reset_piece_id = (
            previous_piece_id
            if previous_piece_id is not None
            and previous_piece_id != piece.body_id
            else None
        )
        self.active_piece_id = piece.body_id

        if not flick_toward_target(
            self.world,
            piece.body_id,
            plan.piece_target,
            plan.strength,
        ):
            self._pending_touch_reset_piece_id = None
            self.outcome = TurnEvent(
                "flick_failed",
                self.attacking_team,
                piece_id=piece.body_id,
                plan=plan,
            )
            events.append(self.outcome)
            return

        self.flicks_taken += 1
        self.touch_counts[piece.body_id] = (
            self.touch_counts.get(piece.body_id, 0) + 1
        )
        self._opponent_contact = False
        self._pending_piece_id = piece.body_id
        self._pending_contacted = (
            distance_between_mm(piece.position, self.world.ball.position)
            <= piece.radius_mm
            + self.world.ball.radius_mm
            + CONTACT_TOLERANCE_MM
        )
        self._pending_ball_start = self.world.ball.position
        self._pending_pass_received_by = None
        events.append(
            TurnEvent(
                "flick",
                self.attacking_team,
                piece_id=piece.body_id,
                plan=plan,
            )
        )
