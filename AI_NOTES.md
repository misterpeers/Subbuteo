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
`CLAUDE.md` (carried over from `.github/copilot-instructions.md`, which is
kept). This section holds only the task and the baselines, and is rewritten
when the user says "EXECUTE ORDER 66".

**Commands and baselines** (current at the end of the session on 2026-11-24):

| Command | Expected |
|---|---|
| `python -m unittest discover -p "test_*.py"` | 109 tests passing (about 7 s) |
| `python sim_scenarios.py --count 100 --seed 0 --team home` | 93% goal rate, 12.7 mean flicks per goal, 5 `no_plan`, 2 `flick_limit`; failing seeds 22, 24, 59, 69, 77, 84, 91 (about 80 s) |

Decision time at that baseline: mean about 53 ms, median 12 ms, p95 about
264 ms, max about 400 ms (timings vary by a few percent between runs). The
away team (`--team away`) gives the same 93% and 12.7.

**Task: the user chooses the next step.** Step 2 is **paused** at the user's
request (most of it is done; see "Planned work"). At the start of the session:

1. Run the commands above and say whether the results match.
2. The user is tracking a visual check of the animation fix in
   `demo_ai_flick.py` themselves (it was verified headlessly only; see "Known
   issues"). Do not ask about it; act only if the user reports a problem.
3. Offer the choices below and wait for the user's decision before changing
   code. Recommend one, briefly.
   - **Resume step 2:** the "isolated forward" lookahead for the last five
     `no_plan` seeds (22, 24, 69, 77, 84), then close step 2.
   - **Step 3:** remove hard-coded geometry (shot aim, `BALL_ADVANCE_MM = 30`,
     merged planning logic, deliberate bank shots per Q7). This also speeds up
     slow attacks (seeds 59 and 91).
   - **Step 4:** defenders. Needs the user's answers to **Q13** and **Q14**
     first; the rest of its questions are answered.
4. Whatever is chosen: give a short plan, wait for approval, then implement in
   small steps. After each step, run the tests and the harness and report goal
   rate, flicks per goal and decision times against the baseline above.

If the user gives a different instruction, follow it.

## Working agreements

- Do not commit or push. Summarise changes and let the user commit.
- Documentation, session start and session end rules are in `CLAUDE.md`. In
  short: edit only this file and `AI_QUERIES.md`, and say so if other
  documentation is out of date. The user may ask for the rules file to be
  updated, as on 2026-11-24.
- Docstrings are required on all code objects (multi-line, with args, returns
  and raises where relevant).
- Core `sim_*` modules are named for their responsibility, never for a mode
  such as "training". Only `demo_ai_flick.py` keeps training terminology.
- Keep physics and AI headless; convert to pixels only when drawing.
- Terminology: **player** is the AI decision-maker; **player piece** is a
  flicked figure.
- Barlow fonts in `assets/fonts/` for UI text.
- Tests: `python -m unittest discover -p "test_*.py"` (109 passing, about 7 s).
  Pyflakes and the Pylance MCP server were not available in earlier sessions; a
  temporary `pip install --target` of pyflakes into the temp folder worked for
  linting.
- The 100-scenario harness run takes about 80 seconds with verification on.
- Environment (checked 2026-11-24): Python 3.13.5, pygame 2.6.1. pymunk is not
  installed and nothing imports it.
- Tooling note for Claude Code on this machine: multi-line Python passed to the
  Bash tool through a heredoc fails when it contains triple quotes; write the
  script to the scratchpad and run the file instead.

## Where things stand

Done in earlier sessions:

- Core names made neutral (`Scenario`, `FlickPlan`, `plan_team_flick`,
  `plan_piece_flick`, `choose_waypoint`, `waypoint_flick_strength`).
- Attack-direction support (`attack_direction`, `opposing_team` in
  `sim_physics`; mirrored planning in `sim_ai_brain`).
- `sim_turns.TurnController`: headless turn logic, extracted from the demo.
- `sim_scenarios.py`: seeded headless harness.
- `demo_ai_flick.py` ball mode drives `TurnController`.
- Step 1, simulation-verified planning: `PhysicsWorld.clone()`,
  `PhysicsWorld.last_piece_contacts`, `sim_ai_verify.py` with
  `simulate_flick`, `FlickOutcome`, `plan_verified_team_flick()` and the
  sampled fallback (`sample_flick_candidates()` in `sim_ai_brain.py`),
  `plan_team_flick_candidates()`, decision statistics in the controller and
  harness, and `--no-verify`.

Done in the session on 2026-11-24 (first session in Claude Code, moved over
from GitHub Copilot; `CLAUDE.md` added):

- The user answered Q6, Q7, Q10, Q12, Q15 to Q19 and Q21 to Q23. Q21 to Q23 were
  new follow-up questions. At the user's request, `SUBBUTEO_SIM_RULES.md` was
  updated with these decisions and with the step 2 implementation status, and
  `MODULES.md` was updated for step 2 and the demo's frame-time cap.
- Step 2 sub-steps 2.1 to 2.4 implemented (see "Planned work"), raising the
  harness from 74% to 93%.
- The animation problem in `USER_NOTES.md` was diagnosed and fixed with a
  frame-time cap in `demo_ai_flick.py` (see "Known issues").

Files changed in that session: `sim_ai_verify.py`, `sim_turns.py`,
`demo_ai_flick.py`, `test_sim_ai_verify.py`, `test_sim_turns.py`,
`SUBBUTEO_SIM_RULES.md`, `MODULES.md`, `AI_QUERIES.md`, this file, and
`CLAUDE.md` (new).

Baseline history (`python sim_scenarios.py --count 100 --seed 0 --team home`,
3 pieces):

| | Goal rate | Mean flicks per goal | Failures |
|---|---|---|---|
| Original planner (`--no-verify`) | 23% | 9.6 | 68 no_plan, 8 missed flick, 1 possession transfer |
| Planner flicks simulated first | 29% | 9.4 | 71 no_plan |
| Plus sampled fallback (step 1) | 74% | 14.2 | 18 no_plan, 8 flick_limit |
| Plus step 2.1 to 2.4 (2026-11-24) | **93%** | **12.7** | 5 no_plan, 2 flick_limit |

Things learned:

- Simulating only the planner's own candidates gave 29%. Most failures were
  cases where the planner proposed nothing, so the sampled fallback produced
  the large gain.
- Counting the flicking piece as a nearby teammate (while it has touches left)
  matters: excluding it dropped the goal rate from 74% to 63%.
- The old `no_plan` runs all came from a third touch that left the spent piece
  resting against the ball, blocking every teammate's route (or with teammates
  out of range). A "riskier flick" fallback could not have rescued them: the
  only remaining flicks were fouls. Prevention (the next-contact check) fixed
  them.
- Small ranking changes alter whole sequences, so individual seeds flip
  between goal and `flick_limit` from one change to the next. Judge changes
  on the totals and on the failure causes, not on single seeds.
- Home and away no longer match exactly over long sequences, because mirroring
  rounds positions slightly and physics amplifies the difference; they match
  over the first few flicks, and the totals agree (93% both).

## User decisions already made

- Build for **both teams** (HOME and AWAY) in the controller, attacker and
  defender.
- Defender block-flick is a **real capped-strength flick resolved to rest, then
  validated for legality** (not an instant reposition). The 0.10 s window is
  decision time (Q9).
- A block-flicked defending piece **stays where it ends**.
- "Near the shooting area" for the shot-blocking priority means the 280 mm
  shooting depth plus a margin.
- When the ball hits a defender, the **controller supports hand-over** to the
  defending team, but the **training UI ends the drill** and counts a block.
- Training defenders start at **default spots in the defending half and are
  draggable** in the editor.
- Two defenders against the attackers in training, to keep the advantage with
  the attack.
- A ball ending near a teammate is **preferred, not required**; sampled flicks
  may move the ball backward only when no forward candidate is safe.
- A decision time in the tens of milliseconds is acceptable; the user will say
  if the demo feels slow in physical testing.
- Long-term goal: retire training mode and build a full match sequence on the
  same physics, planner and turn controller.

Answered on 2026-11-24 in `AI_QUERIES.md` (all now in the rules file):

- **Q6:** clear lanes are judged by simulating the flick ("simulate and see"),
  for now; no explicit clearance rule.
- **Q7:** bank shots and bank passes are proposed only when no direct shot or
  pass survives simulation.
- **Q10:** formation lines with unspecified Y use even spacing, for now. The
  rules write this as `Y = k / (n + 1)` for `n` figures in a line; the user may
  want to confirm the formula.
- **Q12:** same-instant tie-break: a defending piece's touch wins.
- **Q15 and Q22:** block-flick cap option A: grows with the piece's distance
  from the ball (starting figures 20% within 100 mm, rising to 60% at 400 mm or
  more, to tune). The defender moves the piece **closest to the ball** that can
  reach a legal blocking spot.
- **Q16:** a defender counts as displaced (smashing) if it ends 5 mm or more
  from its start once everything has stopped, for now.
- **Q17:** (1) a deliberate step back is the standard fallback; riskier flicks
  are a later per-team play-style option, not the default. (2) settled by Q21.
  (3) **No flick limit** in the rules; the harness's 30-flick cut-off is a test
  stop only.
- **Q18:** the match clock is all real time, including planning time.
- **Q19 and Q23:** first full match is 5-a-side, 2-2 for both teams, even Y
  spacing, for review in testing.
- **Q21:** no "give up" option. A stuck attacker makes a block-flick style move
  (one piece, capped, no ball contact) to obstruct the opponent; having missed
  the ball, it loses possession as normal. Built with the defenders (step 4),
  reusing the block-flick planner; until then a stuck attack reports `no_plan`.

Other decisions on 2026-11-24:

- Pause step 2 for now (lookahead for the isolated forward not started).
- Keep the frame-time cap in the demo now; consider removing the planning pause
  later, at step 5 (options A to C recorded there).

## Planned work, in order

### 1. Simulation-verified planning (done)

Remaining ideas that were not done: share more of the planner's constants with
the simulation (the hand-tuned `/ 1.3`, `1.02`, `0.25` and `0.88` factors still
exist in the geometric planner but no longer decide whether a flick is used),
and a cheaper clone if decision time becomes a problem.

### 2. No-move fallback and wandering runs (paused, mostly done)

Approved by the user and implemented on 2026-11-24 in `sim_ai_verify.py` and
`sim_turns.py`, with 13 new tests. Harness results after each sub-step (home,
100 seeds from 0):

| Sub-step | Goal rate | Flicks per goal | no_plan | flick_limit | Decision ms (mean / p95 / max) |
|---|---|---|---|---|---|
| Before step 2 | 74% | 14.2 | 18 | 8 | 47 / 246 / 420 |
| 2.1 next-contact check | 86% | 14.1 | 5 | 9 | 45 / 245 / 399 |
| 2.2 backward passes as step back | 91% | 13.7 | 5 | 4 | 45 / 235 / 395 |
| 2.3 loop guard, purposeful step back | 91% | 13.5 | 6 | 3 | 60 / 270 / 574 |
| 2.4 goal-mouth progress in shooting area | **93%** | **12.7** | 5 | 2 | 53 / 264 / 403 |

What was built:

- **2.1 Next-contact check.** `FlickOutcome.next_contact_available`, computed
  by `has_next_contact()`: after the simulated flick, at least one piece that
  may flick next (touches left, or the receiver, or the flicker after a pass)
  must have the ball within flick range (600 mm at full strength) on a straight
  path that no other piece blocks. Planned and sampled flicks without it are
  rejected, unless they score.
- **2.2 Step back.** `_rank_key` puts a flick that moves the ball more than
  `STEP_BACK_MM` (50 mm) back into `STEP_BACK_CATEGORY`, after every other
  planned flick.
- **2.3 Loop guard and purposeful step back.** `TurnController.ball_stops`
  records the ball position before each flick of the attack (cleared on
  `reset`) and is passed as `visited_ball_positions`. A flick ending within
  `REPEAT_RADIUS_MM` (8 mm) of one is a repeat and ranks last. Planned and
  sampled flicks share four levels (`LEVEL_GOAL`, `LEVEL_ADVANCE`,
  `LEVEL_STEP_BACK`, `LEVEL_REPEAT`); sampling runs when the best planned flick
  is below "advance", and the better level wins (planned on a tie).
  `FlickOutcome.forward_contact_available` (a next-contact piece behind the
  ball) is the second rank key, so a step back sets up a forward move.
- **2.4 Shooting-area progress.** When the ball starts inside the shooting
  area, `ball_progress_mm` is the reduction in distance to the goal-mouth
  center (`_ball_progress_mm`), so sliding the ball along the goal line toward
  the goal counts as progress.

Remaining failures (home): `no_plan` 22, 24, 69, 77, 84; `flick_limit` 59, 91.

- **Isolated forward (`no_plan`, all five), the paused sub-step 2.5:** one
  piece is far ahead with the ball and its teammates are more than 600 mm
  (full flick range) from it. After two short touches it cannot reach the
  shooting area for a shot on touch 3, and it cannot pass back because it
  stands behind the ball. Proposed fix: lookahead on touches 1 and 2, preferring
  moves that either reach the shooting area by touch 3 or bring the ball within
  range of another piece. In a match, Q21's stuck-attacker move will also cover
  the position once step 4 exists.
- **Still progressing (`flick_limit`, 59 and 91):** both were advancing steadily
  when the harness's 30-flick cut-off stopped them. By the rules (no flick
  limit) these are slow attacks, not loops. Slow progress is step 3 work
  (`BALL_ADVANCE_MM = 30`).

Design decisions in force (from Q17, Q21): fallback order is normal move, then
deliberate step back, then (from step 4) a block-flick style move that loses
possession; until step 4 the last stage is `no_plan`. No riskier-flick fallback
by default (a later per-team style). No repositioning without touching the
ball. The harness keeps its 30-flick cut-off, reported as `flick_limit`, as a
test stop only.

Notes: `_plan_piece_flick` still rejects any advance with
`plan.ball_target.x < ball_position.x`, and the advance waypoints are fixed
points near the opponent's goal.

### 3. Remove remaining hard-coded geometry

Decided: **Q6** clear lanes are judged by simulation; **Q7** bank shots and
passes are proposed only when no direct shot or pass survives simulation.

- Shot aim is always `Vector2(1.02, 0.5)` (the goal centre). Aim across the
  120 mm goal mouth for the best clear point.
- `BALL_ADVANCE_MM = 30` limits every advance. The user asked when longer
  movements apply. Add a style or risk parameter allowing longer moves when the
  lane is clear and no defender is near. This should also help seeds 59 and 91.
- Bank shots and passes (Q7): propose rebound routes off a touchline or a goal
  line outside the goal mouth only when no direct route survives simulation.
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

Questions: Q6, Q12, Q15/Q22 and Q16 are answered (see "User decisions").
**Q13** (may a defender stand in the shooting area or in front of the goal
mouth; default yes, anywhere not overlapping another piece) and **Q14** (how a
weaker team skips its block-flick; a skill value per team, and whether the
choice is seeded) are still open.

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
- Strength cap grows with the piece's distance from the ball (Q22: 20% within
  100 mm rising to 60% at 400 mm or more). Choose the defending piece closest
  to the ball that can reach a legal blocking spot, reusing
  `waypoint_flick_strength` and `choose_waypoint`.
- The same block-flick planner gives a stuck attacker its last-resort move
  (Q21): obstruct the opponent's next move, then possession changes. This
  replaces the `no_plan` outcome in a match.
- Smashing foul: a defender counts as displaced if it ends 5 mm or more from
  its start (Q16). Same-instant events: a defending touch wins (Q12).

Required engine changes:

- `PhysicsWorld.last_ball_contacts` is an unordered set, and
  `last_piece_contacts` is also per step. Add an ordered contact log (which
  body the flicking piece or ball touched first, and when). This is also the
  placeholder for time-of-contact ordering (Q3, tie-break Q12). The verifier
  already detects "flicker hit a piece before the ball" at step granularity
  using `last_piece_contacts`; reuse that for fouls in play.
- Detect outcomes: ball hits a defender (block, possession transfers); flicking
  piece touches a defender or teammate before the ball (foul, possession
  transfers); flick displaces two or more defenders in their half and is not a
  shot (smashing foul). Currently only `opponent_contact`, a missed flick and a
  possession transfer are handled in `sim_turns.py`, and `sim_ai_verify.py`
  only uses the foul checks to reject its own candidates.
- The verifier clones the world, so it already sees defender pieces as bodies.
  Defenders make shots and passes verify correctly without extra geometry, as
  long as they are real bodies in the world and not only `Obstacle`s. Moving
  dummies in the demo are static in a clone.
- Extend `TurnController` with the response window and block-flick validation.
  The 0.10 s window is decision time; resolve the capped flick to rest before
  the next attack.
- Training UI (`demo_ai_flick.py`): two draggable defenders in away colours with
  D1 and D2 labels, window timer and outcome messages, counters for goals,
  blocks, misses and fouls, and an `Obstacle`-style hand-off so the attacker's
  planner sees defenders.
- `_training_player_pieces` in the demo filters by `TRAINING_PIECE_NUMBERS`;
  split attackers and defenders by team.

Suggested sub-order: defenders as static bodies and obstacles, then the ordered
contact log and foul outcomes, then defender target selection with no movement,
then block-flick execution and validation, then the stuck-attacker move, then
the turn cycle and UI, then tuning with harness metrics.

Tests to add: each outcome including contact order, an illegal block being
reverted, the touch-count reset, defender selection and placement, the skip
case, the stuck-attacker move, and an attacker-versus-two-defenders scenario in
the harness.

### 5. Toward a full match

Decided: even Y spacing (Q10), real-time clock including planning time (Q18),
5-a-side (Q19) in a 2-2 for both teams (Q23), no flick limit (Q17), and a stuck
attacker makes a block-flick move then loses possession (Q21). The goalkeeper
stage depends on **Q11** (collision thickness, 6 mm or 8 mm), still open.

- `TurnController` with `hand_over_on_loss=True` already supports alternating
  attacks; the demo does not use it.
- Add match flow in a new module (for example `sim_match.py`): kick-off at the
  start of each half and after goals, the 2-2 formation with
  `Y = k / (n + 1)` spacing, the 15-minute real-time halves and match clock,
  scores, and restarts. Render with `sim_pitch.py` and `sim_scorebug.py`,
  which already follow the design standard.
- **Remove the planning pause** (user asked for this to be recorded here, to
  consider later). Today verified planning runs on the main loop and can take
  up to about 0.4 s; the demo caps simulated time per frame
  (`MAX_FRAME_SECONDS = 1/30`), so the picture pauses while the AI thinks and
  the flick then plays smoothly. Options:
  - **A. Plan during the wait.** The controller plans as soon as play settles,
    while nothing moves, stores the plan, and launches it when the 1 s delay
    ends. The freeze still happens but while everything is at rest, so it is
    barely visible. Catch: the plan goes stale if the board changes during the
    wait (moving demo dummies; in a match, the defender's block-flick). Then
    re-check it with one simulation (about 10 to 30 ms) and re-plan fully only
    if it fails. About 30 to 50 lines in `sim_turns.py` plus tests; harness
    unaffected. Suits training; does not help a match, because the attacker
    can only plan after the defender's block-flick.
  - **B. Plan in the background.** The controller hands a cloned world to a
    worker and polls each frame; the drawing loop stays at 60 fps throughout,
    and the flick launches when the plan is ready and any wait or defender
    window is over. Thread version: simple, but Python's GIL means planning
    shares time with drawing, so it slows (perhaps 0.5 to 0.8 s) while
    animation stays smooth. Process version (a persistent
    `ProcessPoolExecutor`): full speed on a second core, but the world must be
    copied across and Windows has a start-up cost. The harness keeps synchronous
    planning so results stay reproducible. The match clock (Q18, real time)
    must run on uncapped real time, separate from the capped physics step, so
    thinking time costs match time as a real opponent's would. About 150 lines
    plus careful timing tests. **Recommended for the match**, starting with the
    thread version and moving to a process only if planning becomes too slow.
  - **C. Make planning faster.** Simulate fewer candidates, stop earlier once
    a good flick is found, or make `PhysicsWorld.clone()` cheaper. Shortens the
    pause but never removes it; worth doing alongside A or B.
- Goalkeeper behaviour (rectangular collision, touch rules) is a separate later
  stage.
- Once match flow exists, retire the training mode in `demo_ai_flick.py`.

## Open questions for the user

`AI_QUERIES.md` is the single list of questions and the place where the user
records answers. Do not keep a second list here. Read it at the start of every
session, because the user may have answered questions since this file was
written, and an answer there overrides any default or assumption in this file.

Open at the end of the session on 2026-11-24 (see the status table at the top
of `AI_QUERIES.md`):

| ID | Topic | Needed for |
|---|---|---|
| Q13 | Defenders near the goal and in the shooting area | Step 4 |
| Q14 | Defender skipping a move on purpose | Step 4 |
| Q11 | Goalkeeper collision thickness | Goalkeeper stage |
| Q20 | Numeric rule for a setup pass (optional) | Nothing blocked |

All others (Q1 to Q10, Q12, Q15 to Q19, Q21 to Q23) are answered and recorded
in "User decisions already made" above or in earlier sessions.

If a question comes up that is not in `AI_QUERIES.md`, add it there (next free
number, Q24 at the time of writing; suggested default; `**Your response: TBD**`
line; and a row in its status table), and also ask in the session if it blocks
the current task. Never change a response the user has written.

## Known issues and notes

- **Animation (from `USER_NOTES.md`), fixed but not seen by the user yet:**
  pieces jumped instead of moving smoothly. Cause: verified planning runs
  inside `controller.update()` on the demo's main loop and takes up to about
  0.4 s; the next `clock.tick(60)` returned that whole stall as `elapsed`, and
  the world stepped through it in one frame just as the flick launched
  (measured headlessly: 130 to 234 mm in one frame against about 20 mm
  normally). Fix: `elapsed = min(clock.tick(60) / 1000.0, MAX_FRAME_SECONDS)`
  with `MAX_FRAME_SECONDS = 1.0 / 30.0` in `demo_ai_flick.py`; measured with
  the cap, the largest per-frame move is about 30 mm. The picture now pauses
  briefly during planning; removing the pause is recorded under step 5. The
  user has noted to check the fix in the real window themselves, and can then
  clear `USER_NOTES.md`.
- `__pycache__/*.pyc` files are tracked in git and show as modified. Suggest a
  `.gitignore` entry to the user.
- Pre-existing lint warnings: unused `radius_x` in `sim_physics.py`
  (`_resolve_net_boundaries`) and an unused `PITCH_WIDTH_MM` import in
  `test_sim_ai_brain.py`.
- The demo ends a run when possession is lost only after play settles.
- The simulated team in training is always HOME; `_new_turn_controller` in
  `demo_ai_flick.py` hard-codes it.
- The simulation runs a candidate at 1/60 s updates, while the demo's frame
  time varies (now capped at 1/30 s), so a real flick can differ slightly from
  its simulation. Over 100 scenarios no run lost possession after
  verification.
- Mirroring a scenario for the away team rounds positions slightly, so long
  sequences diverge from the home result; compare only the first few flicks.
- `SCENARIO_NOTES.md` is no longer in the folder, so its old "Remove goal kick
  restart pending" note no longer applies.
- `NOTES.md` (shot-blocking drill ideas) and `SCENARIO_TEMPLATE.md` (manual
  scenario record template) are the user's reference files; they need no
  action.
