# Module guide

This guide lists every Python module in the project, what it does, and how the
modules depend on each other. For game rules and terminology see
[SUBBUTEO_SIM_RULES.md](SUBBUTEO_SIM_RULES.md).

## Design principles

- **Headless core:** `sim_*` modules never need a window, except the rendering
  helpers listed below. Physics, planning, turn control and scenario runs work
  without Pygame.
- **Normalized coordinates:** Positions are floats in `[0, 1]`. Conversion to
  pixels happens only in rendering code.
- **Mode-neutral names:** Core modules describe a responsibility, not a mode.
  Training, the physics demo and the future match all share the same core.
- **Demos are thin:** `demo_*.py` files draw and forward input to `sim_*`
  modules. They do not duplicate core logic.
- **Terminology:** A *player* is the AI decision-maker; a *player piece* is a
  flicked figure on the pitch.

## Dependency overview

```text
                    sim_physics            (no project imports)
                   /     |      \
        sim_ai_flick     |       sim_pitch    sim_scorebug    sim_menu
              |          |         (render)     (render)      (render)
              +-----> sim_ai_brain
              |            |
              +-----> sim_ai_verify
                           |
                      sim_turns
                           |
                    sim_scenarios
```

Arrows point from a module to the modules it imports. `sim_ai_verify` imports
`sim_ai_brain`, `sim_ai_flick` and `sim_physics`; `sim_turns` imports all
three of those and `sim_ai_verify`. Lower layers never import higher ones. The
demos sit above everything:

| Demo | Uses |
|---|---|
| `demo_ai_flick.py` | `sim_ai_flick`, `sim_ai_brain`, `sim_physics`, `sim_pitch`, `sim_turns` |
| `demo_physics.py` | `sim_physics`, `sim_pitch`, `sim_scorebug`, `sim_menu` |
| `demo_pitch.py` | `sim_pitch`, `sim_scorebug` |
| `demo_scorebug.py` | `sim_pitch`, `sim_scorebug` |

## Core modules

### `sim_physics.py` (headless)

The physics engine and shared constants.

- `Vector2`: immutable 2D vector.
- `Body`: circular body (player piece, goalkeeper, ball, dummy) with position,
  velocity, mass, team, kind and friction.
- `PhysicsWorld`: steps motion at a fixed sub-step, applies friction, resolves
  piece-piece and piece-ball collisions, wall rebounds, goal-line handling, net
  rebounds, goals and own goals, and records `last_ball_contacts`,
  `last_piece_contacts` (pairs of pieces that overlapped during the last
  step), `possession`, scores and the last goal. `flick()` applies a
  drag-and-release impulse. `clone()` returns an independent copy for what-if
  simulation.
- Constants for pitch, ball, piece and goal dimensions, restitution, friction
  and flick limits.
- Team helpers: `HOME`, `AWAY`, `opposing_team()` and `attack_direction()`
  (`ATTACK_TOWARD_INCREASING_X` / `ATTACK_TOWARD_DECREASING_X`).

### `sim_ai_flick.py` (headless)

Low-level flick helpers between the AI and the physics.

- `distance_between_mm()`: physical distance between normalized points.
- `aim_target_position()`: choose a marker or the ball as the aim point.
- `flick_toward_target()`: convert a target and a 0-1 strength into a physics
  flick.

Imports: `sim_physics`.

### `sim_ai_brain.py` (headless)

The attacking AI planner. It decides what to do, but never applies a flick.

- Data types: `Obstacle`, `TargetArea`, `Scenario`, `FlickPlan` (piece target,
  ball target, strength, action `advance` / `pass` / `shot` / `setup`, receiver
  and flicking piece).
- Navigation: `choose_waypoint()` finds an obstacle-avoiding path and a safe
  stopping point; `waypoint_flick_strength()` converts distance to strength.
- Ball planning: `plan_piece_flick()` plans one piece; `plan_team_flick()`
  picks the best piece and action for a team. Priority is shot, then setup
  pass, then advance or pass, preferring lower strength and shorter travel.
  `plan_team_flick_candidates()` returns the whole ranked list, best first
  (`plan_team_flick()` returns its first entry).
- Sampled flicks: `sample_flick_candidates()` generates exploratory flicks from
  one piece, aimed beside the ball's center at several strengths. It has no
  direction of its own; callers judge the result by simulating it.
- Direction: the planners take `attack_direction`. They plan in the
  increasing-X frame and mirror inputs and outputs for the other team.
- `estimate_contact_strength()`: strength needed for a piece to reach the ball.

Imports: `sim_ai_flick`, `sim_physics`.

### `sim_ai_verify.py` (headless)

What-if simulation of flicks. It never changes the world it is given.

- `simulate_flick()` / `simulate_plan()`: clone the world, apply a flick through
  the normal flick code, run physics until everything stops, and return a
  `FlickOutcome`: whether the flicker touched the ball, whether it hit another
  piece before the ball (a foul), whether the ball touched an opposing piece,
  whether possession was kept, goal, receiving teammate, where the ball
  stopped, forward progress, and the gap to the nearest teammate who can flick
  next. `FlickOutcome.keeps_possession` is the combined legality check.
- `plan_verified_team_flick()`: simulates the planner's candidates, rejects any
  that lose the ball or foul, and ranks the rest as goal, setup pass, advance
  or pass, then a non-scoring shot. Within a group it prefers a ball that stops
  within 100 mm of a teammate, then lower strength, then shorter travel. If no
  planner candidate survives it simulates sampled flicks instead, which may go
  forward, sideways or backward; a non-forward move is only accepted if it
  leaves the ball near a teammate or inside the shooting area. The result is a
  `VerifiedFlick` whose `source` is `planned` or `sampled`.
- Limits: 12 planner candidates and 40 sampled candidates per decision, each
  simulated for at most 600 steps of 1/60 s.

Imports: `sim_ai_brain`, `sim_ai_flick`, `sim_physics`.

### `sim_turns.py` (headless)

The turn controller. It runs one team's attack flick by flick.

- `TurnController.update(elapsed, obstacles)`: steps the world, tracks contacts,
  detects goals and lost possession, waits out the pause between flicks, asks
  `plan_verified_team_flick` for the next flick (or `plan_team_flick` when
  `verify_flicks=False`) and applies it.
- State: attacking team, active piece, per-piece touch counts, flick count and
  outcome.
- `decision_stats` (`DecisionStats`): the duration of every flick decision and
  how many came from a planner candidate, a sampled flick, or found no move.
- `hand_over_on_loss`: when `False` a lost ball ends the sequence (training);
  when `True` the attack passes to the other team and play continues (match).
- `TurnEvent` kinds: `flick`, `pass_received`, `goal`, `possession_lost`
  (reason `missed_flick`, `opponent_contact` or `possession_transfer`),
  `no_plan`, `flick_failed`.

Imports: `sim_ai_brain`, `sim_ai_flick`, `sim_ai_verify`, `sim_physics`.

### `sim_scenarios.py` (headless)

The scenario harness for measuring the AI without a window.

- `ScenarioSetup`, `build_world()`, `run_scenario()`: build and play one
  attack to its outcome.
- `random_setup()`: seeded random start, mirrored for the away team.
- `run_batch()` and `format_summary()`: aggregate many seeds into goal rate,
  mean flicks per goal, outcome counts, failing seeds, and decision statistics
  (how many decisions used a planner candidate, a sampled fallback, or found no
  move, and the mean, median, 95th percentile and maximum decision time).
- Command line: `python sim_scenarios.py --count 100 --seed 0 --team home`.
  Add `--no-verify` to use the planner's first choice without simulating it,
  for comparison.

Imports: `sim_ai_brain`, `sim_physics`, `sim_turns`.

## Rendering modules (Pygame)

These draw only. They hold no match rules or state.

| Module | Purpose |
|---|---|
| `sim_pitch.py` | Draws the board, frame, turf bands, markings, goals and penalty and goal areas; returns the playing-area rectangle. Holds the render dimensions and colors. |
| `sim_scorebug.py` | Draws the score pill, team badges and names, and the match-timer pill using the bundled Barlow fonts. |
| `sim_menu.py` | Draws the start menu and exposes the start button rectangle. |

## Demos

| File | Purpose |
|---|---|
| `demo_ai_flick.py` | Interactive AI tester with three modes. Free-play flicks a piece with a chosen strength. Training without a ball navigates a piece to a target around obstacles and moving dummies. Training with a ball plays an attack toward the right-hand goal through `TurnController`. The scenario editor and drawing live here; game logic does not. |
| `demo_physics.py` | Untimed physics sandbox with an 11-a-side layout, score bug and a start menu. |
| `demo_pitch.py` | Previews the empty pitch and the match-setup piece rendering. |
| `demo_scorebug.py` | Standalone preview of the score bug and timer. |

## Tests

Run all tests with `python -m unittest discover -p "test_*.py"`.

| File | Covers |
|---|---|
| `test_sim_physics.py` | Boundaries, goals, possession transfers, net damping, collisions, flick strength, piece-contact record and world cloning. |
| `test_sim_ai_flick.py` | Aiming and strength limits, plus the training UI's coordinate panel and rulers. |
| `test_sim_ai_brain.py` | Waypoints, contact planning, passes, setup passes, touch limits, attack direction, candidate ordering and sampled flicks. |
| `test_sim_ai_verify.py` | Simulated outcomes, foul-before-ball detection, verified selection and the sampled fallback. |
| `test_sim_turns.py` | Controller outcomes, hand-over, direction, the three-touch limit and decision statistics. |
| `test_sim_scenarios.py` | Seed reproducibility, home and away symmetry over a short horizon, and report content. |

## How a flick flows through the modules

1. `TurnController.update()` calls `PhysicsWorld.step()`.
2. When everything has settled, it calls `plan_verified_team_flick()` with the
   world, the attacking team, touch counts and obstacles.
3. That asks `plan_team_flick_candidates()` for ranked `FlickPlan`s, using the
   team's `attack_direction()`. The planner returns normalized coordinates and
   does not touch the world.
4. Each candidate is simulated on a `PhysicsWorld.clone()`. Candidates that
   miss the ball, foul, hit an opposing piece or lose possession are rejected.
   If none survive, `sample_flick_candidates()` supplies exploratory flicks,
   which are simulated and ranked the same way.
5. The controller applies the chosen plan to the real world with
   `flick_toward_target()`, which calls `PhysicsWorld.flick()`.
6. Physics runs. The controller reads `last_ball_contacts`, `last_goal` and
   `possession` to detect a pass, a goal or a lost ball, and updates touch
   counts.
7. The controller returns `TurnEvent`s. A demo turns them into messages; the
   scenario harness turns them into results and decision statistics.

## Planned modules

- A defender planner (for example `sim_ai_defence.py`) for the response window
  and block-flick, and match flow (kick-off, halves, clock, formations) built on
  `TurnController` with `hand_over_on_loss=True`. See the implementation status
  in the rules file.

Other files: `AI_QUERIES.md` (open design questions), `NOTES.md` (drill ideas),
`SCENARIO_NOTES.md` and `SCENARIO_TEMPLATE.md` (recording failing scenarios),
and the `*.bat` helpers for git.
