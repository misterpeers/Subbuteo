# AI notes: handover and plan

This file hands the project over to a new agent or session. Read it together
with [SUBBUTEO_SIM_RULES.md](SUBBUTEO_SIM_RULES.md) (rules and terminology,
including the "Implementation status" section), [MODULES.md](MODULES.md)
(module guide) and [AI_QUERIES.md](AI_QUERIES.md) (the decisions the user
still has to make, and the answers already given). Nothing has been committed;
the user reviews and commits manually.

## Next task

The agent works from this section when the user opens a session with "HELLO
THERE". The start and end of session procedures are written once, in
`.github/copilot-instructions.md`. This section holds only the task and the
baselines, and is rewritten when the user says "EXECUTE ORDER 66".

**Commands and baselines** (current at the end of the last session):

| Command | Expected |
|---|---|
| `python -m unittest discover -p "test_*.py"` | 96 tests passing (about 10 s) |
| `python sim_scenarios.py --count 100 --seed 0 --team home` | 74% goal rate, 14.2 mean flicks per goal, 18 `no_plan`, 8 `flick_limit` (about 80 s) |

**Task: step 2, the no-move fallback and the wandering runs**

1. Diagnose the 26 failing seeds from the harness (for example 2, 12, 13, 14 and
   17). For each, say whether it ends in `no_plan` or `flick_limit` and why.
2. Give a short design: what the fallback does, in what order, and how
   sideways and backward moves are stopped from looping.
3. Use the user's answer to Q17 in `AI_QUERIES.md` if one is recorded; otherwise
   use the suggested defaults there and say so. Ask only what is not already in
   `AI_QUERIES.md`, and add any new question to it.
4. Wait for the user's approval before changing any code.
5. When approved, implement in small steps. After each step run the tests and
   the harness, and report goal rate, flicks per goal and decision times against
   the baseline.

If the user would rather start with a different step, follow their instruction
(for example step 4, defenders, which also depends on their answers to Q13 to
Q16).

## Working agreements

- Do not commit or push. Summarise changes and let the user commit.
- Documentation, session start and session end rules are in
  `.github/copilot-instructions.md`. In short: edit only this file and
  `AI_QUERIES.md`, and say so if other documentation is out of date.
- Docstrings are required on all code objects (multi-line, with args, returns
  and raises where relevant).
- Core `sim_*` modules are named for their responsibility, never for a mode
  such as "training". Only `demo_ai_flick.py` keeps training terminology.
- Keep physics and AI headless; convert to pixels only when drawing.
- Terminology: **player** is the AI decision-maker; **player piece** is a
  flicked figure.
- Barlow fonts in `assets/fonts/` for UI text.
- Run tests with `python -m unittest discover -p "test_*.py"` (96 passing at
  handover, about 10 seconds). Pyflakes and the Pylance MCP server were not
  available; a temporary `pip install --target` of pyflakes into the temp
  folder worked for linting.
- The 100-scenario harness run takes about 80 seconds with verification on.

## Where things stand

Done in earlier sessions:

- Core names made neutral (`Scenario`, `FlickPlan`, `plan_team_flick`,
  `plan_piece_flick`, `choose_waypoint`, `waypoint_flick_strength`).
- Attack-direction support (`attack_direction`, `opposing_team` in
  `sim_physics`; mirrored planning in `sim_ai_brain`).
- `sim_turns.TurnController`: headless turn logic, extracted from the demo.
- `sim_scenarios.py`: seeded headless harness.
- `demo_ai_flick.py` ball mode drives `TurnController`.

Done in the latest session (plan steps 1 and 5):

- `PhysicsWorld.clone()` and `PhysicsWorld.last_piece_contacts` (pairs of
  pieces that overlapped during the last step).
- `sim_ai_verify.py`: simulates a flick on a clone and reports a
  `FlickOutcome`. `plan_verified_team_flick()` simulates the planner's ranked
  candidates, rejects those that miss the ball, hit a piece before the ball,
  touch an opposing piece or lose possession, and falls back to sampled flicks
  (`sample_flick_candidates()` in `sim_ai_brain.py`) when none survive.
- `plan_team_flick_candidates()` returns the whole ranked candidate list.
- `TurnController` verifies flicks by default (`verify_flicks=False` turns it
  off) and records `decision_stats` (decision times and source counts).
- The harness reports decision counts and times and has `--no-verify`.
- The demo has not been run interactively since the verifier was added. It
  uses `TurnController`, so it picks up verification automatically.

Current baseline (`python sim_scenarios.py --count 100 --seed 0 --team home`,
3 pieces, 96 tests passing):

| | Goal rate | Mean flicks per goal | Failures |
|---|---|---|---|
| Original planner (`--no-verify`) | 23% | 9.6 | 68 no_plan, 8 missed flick, 1 possession transfer |
| Planner flicks simulated first | 29% | 9.4 | 71 no_plan |
| Current (plus sampled fallback) | **74%** | 14.2 | 18 no_plan, 8 flick_limit |

Current decisions: 1479 in 100 scenarios (1197 planned, 264 sampled fallback,
18 no move). Decision time: mean 48 ms, median 12 ms, p95 252 ms, max 410 ms.
The away team scores 78% on the same seeds. Home and away no longer match
exactly over long sequences, because mirroring rounds positions slightly and
physics amplifies the difference; they do match over the first few flicks.
First failing seeds (home): 2, 12, 13, 14, 17, 22, 23, 24, 26, 33.

Things learned:

- Simulating only the planner's own candidates gave 29%. Most failures were
  cases where the planner proposed nothing, so the sampled fallback produced
  the large gain.
- Counting the flicking piece as a nearby teammate (while it has touches left)
  matters: excluding it dropped the goal rate from 74% to 63%. It matches the
  rules, which treat a piece with touches left as friendly.
- Longer sequences come from sideways and backward moves. The 8 `flick_limit`
  runs probably wander, and nothing yet stops a loop.

## User decisions already made

- Build for **both teams** (HOME and AWAY) in the controller, attacker and
  defender.
- Defender block-flick is a **real capped-strength flick resolved to rest, then
  validated for legality** (not an instant reposition).
- A block-flicked defending piece **stays where it ends** (now also recorded in
  the rules file).
- "Near the shooting area" for the shot-blocking priority means the 280 mm
  shooting depth plus a margin (the user agreed to this measurement).
- When the ball hits a defender, the **controller supports hand-over** to the
  defending team, but the **training UI ends the drill** and counts a block.
- Training defenders start at **default spots in the defending half and are
  draggable** in the editor.
- Two defenders against the attackers, to keep the advantage with the attack.
- A ball ending near a teammate is **preferred, not required**; sampled flicks
  may move the ball backward only when no forward candidate is safe.
- A decision time in the tens of milliseconds is acceptable; the user will say
  if the demo feels slow in physical testing.
- Long-term goal: retire training mode and build a full match sequence on the
  same physics, planner and turn controller.

## Planned work, in order

### 1. Simulation-verified planning (done)

Implemented as described under "Where things stand". Remaining ideas that were
not done: share more of the planner's constants with the simulation (the
hand-tuned `/ 1.3`, `1.02`, `0.25` and `0.88` factors still exist in the
geometric planner but no longer decide whether a flick is used), and a
cheaper clone if decision time becomes a problem.

### 2. No-move fallback and wandering runs (next)

Where this stands: the sampled fallback already covers sideways and backward
moves and the harness counts how often it is used (264 of 1479 decisions). What
is left is the 18 `no_plan` runs and the 8 `flick_limit` runs out of 100.

Start by diagnosing the failing seeds (home: 2, 12, 13, 14, 17, 22, 23, 24, 26,
33 are the first ten). For each, find out whether the cause is:

- no piece can reach the ball at all (a piece out of range, or all pieces on
  three touches);
- every sampled flick is rejected (for example the ball is against a wall or in
  a corner, or the only route passes through another piece);
- a loop, where pieces pass the ball between them or nudge it back and forth
  without progress (the likely cause of `flick_limit`).

Then design the fallback. Candidate ideas, in priority order:

1. Loop protection: remember recent ball positions or piece and ball states, and
   penalise or reject a flick that returns to one already seen.
2. A "two steps back to go one step forward" move that is chosen on purpose,
   not by accident.
3. Reposition a piece without touching the ball, if the rules allow it. This
   needs a user decision; the rules currently do not describe it.
4. Only then accept a riskier flick or end the sequence with `no_plan`.

Keep the fallback decision inside the planner and verifier, not the controller,
and keep the harness counters.

Depends on **Q17** in `AI_QUERIES.md` (fallback order, whether a piece may move
without touching the ball, and the maximum flicks per attack). The suggested
defaults there are: a deliberate step back that leaves the ball near another
piece, then a riskier flick, then end the attack; no repositioning without
touching the ball; a 30-flick safety limit (the same limit the harness uses).
Use the user's answer if one is recorded; otherwise say which default you used.
Note `_plan_piece_flick` still rejects any advance with
`plan.ball_target.x < ball_position.x`, and the advance waypoints are fixed
points near the opponent's goal.

### 3. Remove remaining hard-coded geometry

Related questions: **Q6** (is "simulate it and see" enough as the clear-lane
rule, or should an explicit clearance be written down) and **Q7** (should bank
shots be deliberate). Both are still open.

- Shot aim is always `Vector2(1.02, 0.5)` (the goal centre). Aim across the
  120 mm goal mouth for the best clear point.
- `BALL_ADVANCE_MM = 30` limits every advance. The user asked when longer
  movements apply. Add a style or risk parameter allowing longer moves when the
  lane is clear and no defender is near.
- Obstacles are axis-aligned rectangles with padding; pieces are circles. Add
  circle obstacles, needed for defenders whose positions change.
- `_plan_piece_flick` and `_ball_followup_plan` repeat similar shot, advance
  and pass logic. Merge them to avoid drift.
- The setup-pass search loops over every receiver, offset and direction and runs
  a full follow-up plan each time; it will not scale to 6 or 11 pieces.
- Plans do not carry intent across turns (for example "this setup is for piece
  3"), so a later plan can undo a setup.

### 4. Defenders

New module (suggested name `sim_ai_defence.py`), headless, mirroring the
attacker planner and direction-aware.

Depends on these questions in `AI_QUERIES.md`, all still open. Suggested
defaults are in the file; use the user's answer if one is recorded.

- **Q13:** may a defender stand in the shooting area or in front of the goal
  mouth (default: yes, anywhere not overlapping another piece).
- **Q14:** how a weaker team skips its block-flick (a skill value per team, and
  whether the choice is seeded).
- **Q15:** the strength cap for a block-flick (default 50%).
- **Q16:** how far a defender must move to count as displaced for the smashing
  foul (default 5 mm from its start once everything has stopped).
- **Q12:** the tie-break for events at exactly the same moment, needed once the
  ordered contact log is added.
- **Q6:** the clear-lane rule, which the defender shares with the attacker.

Rules to implement (from `SUBBUTEO_SIM_RULES.md`):

- After the attack settles, the defender gets a 0.10 s response window to move
  **one** field piece with a block-flick, or skip.
- The block-flick must not touch the ball or an attacking piece. An illegal
  one is invalidated: restore the piece's position, reset **all** attacking
  field-piece touch counts to 0, and return play to the attacker. This is not a
  possession change.
- Priorities: (1) avoid illegal contact; (2) when the ball is in or near the
  shooting area, place a piece on the line from the ball to the goal-mouth
  centre; (3) otherwise place a piece between the ball and the nearest
  uncontrolled attacking piece; (4) otherwise skip.
- Choose the defender needing the least flick strength, reusing
  `waypoint_flick_strength` and `choose_waypoint`.

Required engine changes:

- `PhysicsWorld.last_ball_contacts` is an unordered set, and
  `last_piece_contacts` (added in the latest session) is also per step. Add an
  ordered contact log (which body the flicking piece or ball touched first, and
  when). This is also the placeholder for time-of-contact ordering (Q3). The
  verifier already detects "flicker hit a piece before the ball" at step
  granularity using `last_piece_contacts`; reuse that for fouls in play.
- Detect outcomes: ball hits a defender (block, possession transfers); flicking
  piece touches a defender or teammate before the ball (foul, possession
  transfers); flick displaces two or more defenders in their half and is not a
  shot (smashing foul). Currently only `opponent_contact` (ball hits an
  opposing piece), a missed flick and a possession transfer are handled in
  `sim_turns.py`, and `sim_ai_verify.py` only uses the foul checks to reject
  its own candidates.
- The verifier clones the world, so it already sees defender pieces as bodies.
  Defenders therefore make shots and passes verify correctly without extra
  geometry, as long as they are real bodies in the world and not only
  `Obstacle`s. Moving dummies in the demo are static in a clone.
- Extend `TurnController` with the response window and block-flick validation.
  `0.10 s` is too short for a physical flick to finish, so treat the window as
  decision time and resolve the capped flick to rest before the next attack.
  Confirm this with the user if it matters for pacing.
- Training UI (`demo_ai_flick.py`): two draggable defenders in away colours with
  D1 and D2 labels, window timer and outcome messages, counters for goals,
  blocks, misses and fouls, and an `Obstacle`-style hand-off so the attacker's
  planner sees defenders.
- `_training_player_pieces` in the demo filters by `TRAINING_PIECE_NUMBERS`;
  split attackers and defenders by team.

Suggested sub-order: defenders as static bodies and obstacles, then the ordered
contact log and foul outcomes, then defender target selection with no movement,
then block-flick execution and validation, then the turn cycle and UI, then
tuning with harness metrics.

Tests to add: each outcome including contact order, an illegal block being
reverted, the touch-count reset, defender selection and placement, the skip
case, and an attacker-versus-two-defenders scenario in the harness.

### 5. Toward a full match

Depends on **Q10** (formation Y-coordinates), **Q18** (how match time advances)
and **Q19** (squad size and formation for the first match; suggested start is
5-a-side), all still open. The goalkeeper stage depends on **Q11**
(collision thickness, 6 mm or 8 mm).

- `TurnController` with `hand_over_on_loss=True` already supports alternating
  attacks; the demo does not use it.
- Add match flow in a new module (for example `sim_match.py`): kick-off at the
  start of each half and after goals, formations (Y-coordinates are still open,
  Q10), the 15-minute halves and match clock, scores, and restarts. Render with
  `sim_pitch.py` and `sim_scorebug.py`, which already follow the design
  standard.
- Goalkeeper behaviour (rectangular collision, touch rules) is a separate later
  stage.
- Once match flow exists, retire the training mode in `demo_ai_flick.py`.

## Open questions for the user

`AI_QUERIES.md` is the single list of questions and the place where the user
records answers. Do not keep a second list here. Read it at the start of every
session, because the user may have answered questions since this file was
written, and an answer there overrides any default or assumption in this file.

Open at the time of writing (see the status table at the top of
`AI_QUERIES.md`):

| ID | Topic | Needed for |
|---|---|---|
| Q17 | No-move fallback, repositioning, flick limit per attack | Step 2 (next) |
| Q6 | Clear shooting and passing lanes | Steps 3 and 4 |
| Q7 | Bank shots | Step 3 |
| Q13 | Defenders near the goal and in the shooting area | Step 4 |
| Q14 | Defender skipping a move on purpose | Step 4 |
| Q15 | Strength cap for a block-flick | Step 4 |
| Q16 | What counts as displacing defenders (smashing) | Step 4 |
| Q12 | Same-time-of-contact tie-break | Step 4 |
| Q10 | Formation Y-coordinates | Step 5 |
| Q18 | How match time advances | Step 5 |
| Q19 | Squad size and formation for the first match | Step 5 |
| Q11 | Goalkeeper collision thickness | Goalkeeper stage |
| Q20 | Numeric rule for a setup pass (optional) | Nothing blocked |

Already answered and recorded in "User decisions already made" above: block-flick
timing and persistence (Q9), the shooting-area measurement, the preference for
a ball ending near a teammate, backward sampled flicks, and acceptable decision
time. Q1 to Q5 and Q8 are also answered in `AI_QUERIES.md`.

If a question comes up that is not in `AI_QUERIES.md`, add it there (next free
number, suggested default, `**Your response: TBD**` line, and a row in its
status table), and also ask in the session if it blocks the current task. Never
change a response the user has written.

## Known issues and notes

- `__pycache__/*.pyc` files are tracked in git and show as modified.
- Pre-existing lint warnings: unused `radius_x` in `sim_physics.py`
  (`_resolve_net_boundaries`) and an unused `PITCH_WIDTH_MM` import in
  `test_sim_ai_brain.py`.
- The demo ends a run when possession is lost only after play settles. Earlier
  code ended it the moment possession flipped.
- The simulated team in training is always HOME; `_new_turn_controller` in
  `demo_ai_flick.py` hard-codes it.
- Planning now takes up to about 0.4 s in the worst case. The demo calls it on
  the main loop, so a long decision can briefly freeze the window.
- The simulation runs a candidate at 1/60 s updates, while the demo's frame
  time varies, so a real flick can differ slightly from its simulation. Over
  100 scenarios no run lost possession after verification.
- Mirroring a scenario for the away team rounds positions slightly, so long
  sequences diverge from the home result; compare only the first few flicks.
- `SCENARIO_NOTES.md` still lists "Remove goal kick restart pending"; the demo
  message has been removed, so this note can be cleared by the user.
