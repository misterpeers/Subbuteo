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

**Commands and baselines** (confirmed at the end of the session on
2026-11-27, after step 3.4; all runs 100 seeds from 0, home team):

| Command | Expected |
|---|---|
| `python -m unittest discover -p "test_*.py"` | 148 tests passing (about 7 s) |
| `python sim_scenarios.py --count 100 --seed 0 --team home` | 100% goal rate, 5.4 mean flicks per goal, 0 `no_plan`, 0 `flick_limit` (about 35 s) |
| `python sim_scenarios.py --count 100 --seed 0 --team home --pieces 4` | 100% goal rate, 5.4 mean flicks per goal, 0 `no_plan`, 0 `flick_limit` (about 50 s) |
| `python sim_scenarios.py --count 100 --seed 0 --team home --blockers 2` | 100% goal rate, 5.6 mean flicks per goal (about 65 s) |
| `python sim_scenarios.py --count 100 --seed 0 --team home --pieces 4 --blockers 2` | 100% goal rate, 5.7 mean flicks per goal (about 85 s) |

Decision time (mean / median / p95 / max), runs made two at a time: 3
pieces about 63 / 40 / 288 / 489 ms; 4 pieces about 91 / 65 / 329 / 652 ms;
with 2 blockers about 110 / 63 / 515 / 842 ms (3 pieces) and 148 / 103 /
618 / 1094 ms (4 pieces). Timings vary by several percent between runs, the
max much more. Planned / sampled decisions: 487 / 54 (3 pieces), 500 / 41
(4 pieces), 502 / 62 and 519 / 47 with blockers. The 4-piece run is the
5-a-side reference. Report the two standard runs after every sub-step, and
the blocker runs when a change affects blocked routes. `--blockers N` adds N
static opposing pieces ahead of the ball (testing only; a full match does
not use them). Run harness commands with `run_in_background`.

**Task: step 3 continues. Next is 3.5 (pieces as circles in the planner)
or 3.6 (setup-pass search that scales), depending on the user's answer to
Q32.** The user approved step 3 and its sub-steps on 2026-11-26; 3.0 to
3.4 are done (3.3 longer advances under the balanced, possession-first
rule; 3.4 bank passes, no bank shots). Details of both remaining sub-steps
are under "Planned work", step 3. At the start of the session:

1. Run the five commands above and say whether the results match.
2. The user is tracking a visual check of the animation fix in
   `demo_ai_flick.py` themselves (verified headlessly only; see "Known
   issues"). Do not ask about it; act only if the user reports a problem.
3. Read Q32 in `AI_QUERIES.md`. The user said on 2026-11-27 that they would
   review it. 3.5 was measured that day: with static blockers the
   planner's blind spot costs little (4 pieces, 4 blockers: 6% of planner
   suggestions rejected for hitting a piece, 2.5% of decisions fell back,
   still 100%), but real defenders will cost more. Options: A build 3.5
   now, B defer until after the step 4 defenders and re-measure (suggested),
   C drop.
   - If A: plan 3.5 (every outfield piece of both teams as a circle in the
     planner's path checks; goalkeeper rectangle later, after Q11).
   - If B or C, or no answer yet: say so and plan 3.6 (only receivers in
     flick range, closest first, stop at a setup that leads to a shot;
     check 4-piece decision time, p95 about 330 ms today).
   Either way, give the plan and wait for the user's go-ahead before
   changing code.
4. The rules and `MODULES.md` are up to date for 3.3 and 3.4. Tell the user
   if a change makes them out of date, and update them only when asked.
5. After step 3: step 4, defenders for equal AI players, two in training.
   All its questions are answered. The "exposed" check (3.3),
   `block_flick_cap` and the `--blockers` option are ready for it. If Q32
   is B, re-measure the planner's piece rejections once defenders exist.

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
- Tests: `python -m unittest discover -p "test_*.py"` (148 passing, about 7 s).
- Never use `git stash` to compare with the committed code: running Python
  rewrites the tracked `__pycache__/*.pyc` files and blocks `git stash pop`
  (it happened on 2026-11-27 and was recovered with `git checkout --
  __pycache__` then `git stash pop`). Use `git show HEAD:<file>` into the
  scratchpad instead.
- Pyflakes and the Pylance MCP server were not available in earlier sessions; a
  temporary `pip install --target` of pyflakes into the temp folder worked for
  linting. The 2026-11-27 changes were not linted.
- A 100-scenario harness run takes about 35 s (3 pieces) to 50 s (4 pieces)
  since step 3.3, longer with blockers. Run harness commands with
  `run_in_background` and wait for the notification; do not start them as a
  detached shell job (`&`), which gives no notification.
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
| Plus step 2.1 to 2.4 (2026-11-24) | 93% | 12.7 | 5 no_plan, 2 flick_limit |
| Plus step 2.5 dead-end lookahead (2026-11-26) | 98% | 12.2 | 2 flick_limit |
| Plus step 3.1 merge and 3.2 shot aims (2026-11-26) | 98% | 11.7 | 2 flick_limit |
| Plus step 3.3 longer advances (2026-11-27) | 100% | 5.5 | none |
| Plus step 3.4 bank passes (2026-11-27) | **100%** | **5.4** | none |

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
  over the first few flicks, and the totals agree (98% both since step 2.5).
- (2026-11-26) Tracing failing seeds flick by flick with a small scratch
  script (`TurnController` stepped at 1/60 s, printing pieces, ball and touch
  counts at each `flick` event) found the step 2.5 causes quickly; the
  "obvious" fix (in shooting area = safe) was not enough, and seed 84 showed
  why. Trace before fixing.
- (2026-11-26) The sampled fallback's strengths scale from the strength
  needed to reach the ball, so a piece already touching the ball can only
  sample weak flicks (at most 0.35); longer moves need explicit strengths.

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
- **Q7:** bank passes are proposed only when no direct pass survives
  simulation (bank shots were later ruled out, Q31).
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

Session on 2026-11-26: step 2.5 implemented and step 2 closed (98% home and
away, 0 `no_plan`). At the user's request, `SUBBUTEO_SIM_RULES.md`
("Implementation status": reference result, new "Lone forward lookahead"
item, "No-move outcome") and `MODULES.md` (`sim_ai_verify.py`, tests table,
flick flow) were updated for step 2.5. Files changed: `sim_ai_verify.py`,
`test_sim_ai_verify.py`, `SUBBUTEO_SIM_RULES.md`, `MODULES.md`,
`AI_QUERIES.md` (one status line), this file. Later the same day: step 3
approved; 3.0 to 3.2 done in `sim_ai_brain.py`, `test_sim_ai_brain.py` and
`test_sim_ai_verify.py`. At the user's request, `SUBBUTEO_SIM_RULES.md`
(harness reference result with the 4-piece figure; shot aim points under
"Attacking AI") and `MODULES.md` (`sim_ai_brain.py` merged planning and shot
aim, `--pieces` and `--max-flicks`, tests table) were updated for 3.1 and
3.2. (The rules' strength-first wording was replaced by the balanced,
possession-first rule on 2026-11-27, at the user's request.)

Session on 2026-11-27: start-of-session baselines matched (121 tests; 98% /
11.7 and 99% / 12.5). The user approved the 3.3 plan and it was built in
`sim_ai_brain.py`, `sim_ai_verify.py`, `test_sim_ai_brain.py` and
`test_sim_ai_verify.py` (results under step 3). At the user's request,
`SUBBUTEO_SIM_RULES.md` was then updated for 3.3: a "balanced advance rule
(possession first)" bullet replaces the "lower strength, then shorter
travel" wording under "Attacking flicks", attacker priority 2 and the
touches 1-2 line refer to it, and "Implementation status" has the advance
distances, the exposure test and the new reference figures (100%, 5.5 and
5.3; no scenario reaches the 30-flick stop). `MODULES.md` was updated for
the advance functions, `block_flick_cap`, `is_exposed`, the new ranking
order and the tests table. A 3.4 plan was proposed (step 3). The user
ruled out bank shots (Q31) and asked for "bank shot" to be renamed "bank
pass" in the docs, which was done (rules, queries, this file). The user then
approved 3.4 as amended, with static opposing pieces for testing; it was
built in `sim_ai_brain.py`, `sim_ai_verify.py`, `sim_scenarios.py` and the
three matching test files. At the user's request, the rules'
"Implementation status" (new "Bank passes" item, harness reference figures
with the blocker results, "Clear-lane logic" in place of "Clear-lane and
bank-pass logic") and `MODULES.md` (`FlickPlan.bank`, the bank-pass
functions, the bank stage, limits, `--blockers` and blocker placement, the
tests table, the flick flow) were then updated for 3.4. Then 3.5 was
measured (step 3) and the user was asked Q32 (build now, defer, or drop);
the user is reviewing it. Session ended with "EXECUTE ORDER 66" after the
final test and harness runs.

Files changed on 2026-11-27: `sim_ai_brain.py`, `sim_ai_verify.py`,
`sim_scenarios.py`, `test_sim_ai_brain.py`, `test_sim_ai_verify.py`,
`test_sim_scenarios.py`, `SUBBUTEO_SIM_RULES.md`, `MODULES.md`,
`AI_QUERIES.md` (Q31, Q32, notes under Q7 and T1, status table), this file,
and the tracked `__pycache__` files.

Decisions on 2026-11-27:

- **Q31 (revises Q7):** no deliberate bank shots on goal; bank passes are
  allowed (only when no direct pass works); accidental rebounds from
  exploratory flicks are still accepted. At the user's request the rules
  now say **bank pass** throughout: the section is "Clear lanes and bank
  passes", the dictionary defines "Bank pass", attacker priority 2 and the
  implementation status use it, and a "No bank shots" rule was added. Use
  "bank pass" in code and discussion.
- Static opposing pieces may be used in the harness for testing; a full
  match does not need them.

Decisions on 2026-11-26:

- The user resumed step 2 to finish sub-step 2.5 (the isolated forward). They
  approved the "dead end" approach: a flick that leaves the current piece on
  its final touch, outside the shooting area, with no other piece within
  flick range of the ball, ranks below every other flick but is not
  rejected. The user then asked for the rules file and `MODULES.md` to be
  updated for it, which was done.
- **Q13 answered:** at kick-off all field pieces are outside the scoring
  areas, in formation (matches the rules already); during play a defending
  piece may go anywhere on the pitch. Follow-up Q24 is answered below.
- **Q14 answered:** each AI player will have traits, rated 0 to 1 (0 to 100
  shown), in the spirit of old FIFA team ratings. The first is
  **intelligence**. Skipping the block-flick is a smart decision ("do I need
  to move, or am I already in a good position?"): high intelligence favours
  it, low intelligence tends to always move. Follow-ups Q25 and Q27 are
  answered below.
- The user chose **step 3** as the next piece of work.
- **Player traits are a separate, later stage** (stage 6 below), after a full
  match works with **equal AI players**. Until then no traits, trait profile
  or per-team skill values are built. Tunable behaviour stays in named
  settings that a trait can drive later.
- **Q7 addition:** a high-intelligence player would try bank passes more
  (traits stage, T1; bank shots ruled out by Q31). No code change now; step 3 builds bank passes for equal
  players, only when no direct route survives, with that trigger as one named
  setting.
- **Q25 answered:** 0.0 to 1.0 in code, 0 to 100 on screen; skip probability
  equal to intelligence, seeded (traits stage); all players equal for now.
  Point 2 (which "good position" test) was settled by Q27 (no skip test
  needed until traits).
- **Q26 answered:** yes to a `risk` trait, at the traits stage (T2); step 3
  uses one fixed rule for longer moves.
- **Q24 answered:** in the training editor defenders may be placed anywhere
  (not overlapping another piece); player pieces never enter the net, only
  the ball (the physics already does this).
- **Q27 answered:** until traits exist, a defender **never chooses to skip**;
  it always makes a block-flick. The "good position" test moves to the traits
  stage.
- **Q28 answered:** if a piece already blocks, the defender blocks the next
  most useful route with a different piece; it does not move only when no
  legal block exists. The user wonders whether this should stay the standard
  even with traits (noted in T1, for the traits stage).
- At the user's request, `SUBBUTEO_SIM_RULES.md` was updated with Q13, Q24,
  Q27 and Q28 (player pieces never enter the net; defending pieces may go
  anywhere in play; equal AI players never skip and cover the next route) and
  a "Player traits" line under "Not yet implemented". `MODULES.md` needed no
  change.
- Confirmed with the user: step 4 starts with **two defenders** in training
  (D1, D2) against the three attacking pieces, as decided earlier.
- The user asked for a log of possible
  traits: written as "Player traits (later stage)" in `AI_QUERIES.md` (G1 to
  G4, T1 to T13, each to keep, change or remove at that stage).

Other decisions on 2026-11-24:

- Pause step 2 for now (superseded: resumed and closed on 2026-11-26).
- Keep the frame-time cap in the demo now; consider removing the planning pause
  later, at step 5 (options A to C recorded there).

## Planned work, in order

### 1. Simulation-verified planning (done)

Remaining ideas that were not done: share more of the planner's constants with
the simulation (the hand-tuned `/ 1.3`, `1.02`, `0.25` and `0.88` factors still
exist in the geometric planner but no longer decide whether a flick is used),
and a cheaper clone if decision time becomes a problem.

### 2. No-move fallback and wandering runs (done)

Approved by the user and implemented on 2026-11-24 (2.1 to 2.4, in
`sim_ai_verify.py` and `sim_turns.py`, 13 new tests) and 2026-11-26 (2.5, in
`sim_ai_verify.py`, 9 new tests). Harness results after each sub-step (home,
100 seeds from 0):

| Sub-step | Goal rate | Flicks per goal | no_plan | flick_limit | Decision ms (mean / p95 / max) |
|---|---|---|---|---|---|
| Before step 2 | 74% | 14.2 | 18 | 8 | 47 / 246 / 420 |
| 2.1 next-contact check | 86% | 14.1 | 5 | 9 | 45 / 245 / 399 |
| 2.2 backward passes as step back | 91% | 13.7 | 5 | 4 | 45 / 235 / 395 |
| 2.3 loop guard, purposeful step back | 91% | 13.5 | 6 | 3 | 60 / 270 / 574 |
| 2.4 goal-mouth progress in shooting area | 93% | 12.7 | 5 | 2 | 53 / 264 / 403 |
| 2.5 dead end, long reach, shot check | **98%** | **12.2** | 0 | 2 | 55 / 269 / 689 |

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

- **2.5 Isolated forward (dead end).** Cause of the last five `no_plan`
  seeds (22, 24, 69, 77, 84): a lone piece far ahead, teammates more than
  600 mm (full flick range) from the ball, made two short planned advances
  (`BALL_ADVANCE_MM = 30`) and was left on its final touch outside the
  shooting area, unable to shoot or pass. Built in `sim_ai_verify.py`:
  - `FlickOutcome.dead_end`: the flick did not score or pass, the flicker will
    be on its final touch (only one piece can be partway through its touches,
    as the user confirmed), the ball is outside the shooting area, and no
    other team piece is within flick range of the ball (blocked or not). New
    lowest level `LEVEL_DEAD_END` (`DEAD_END_CATEGORY` for planned flicks,
    tier 4 for sampled), below a repeat. Ranked last, never rejected, so it
    cannot create a new `no_plan`.
  - `FlickOutcome.needs_shot_check`: the same, but with the ball inside the
    shooting area. `_ShotChecker` simulates the flick and plans the next one
    on the result; the flick keeps its rank only if that next touch is a
    verified goal, otherwise `_select` re-keys it as a dead end. At most
    `MAX_SHOT_CHECKS = 3` looks per decision (each is a full planning run;
    this is what raised the max decision time). Seed 84 needed this: touch 2
    reached the area beside the touchline, where no shot survived.
  - Long reach: when nothing better than a dead end exists, the sampled
    contact points are tried again at `LONG_SAMPLE_STRENGTHS = (0.5, 0.7,
    0.9)`; the usual sampled strengths top out at 3.5 x 0.1 for a piece
    touching the ball, too weak to carry it about 170 mm into the area (seed
    69).
  - `simulate_flick` now wraps `_run_flick`, which also returns the settled
    clone for the lookahead. `_within_flick_range` is shared with
    `has_next_contact`.
  - The touch-1 lookahead (planned as 2.5c) was not needed: all five seeds
    score.

Remaining failures at the end of step 2 (home): `flick_limit` 59, 91, slow
attacks stopped by the 30-flick cut-off. Resolved by step 3.3 (longer
advances): every seed now scores.

Design decisions in force (from Q17, Q21): fallback order is normal move, then
deliberate step back (then repeat, then dead end, as ranking levels), then
(from step 4) a block-flick style move that loses
possession; until step 4 the last stage is `no_plan`. No riskier-flick fallback
by default (a later per-team style). No repositioning without touching the
ball. The harness keeps its 30-flick cut-off, reported as `flick_limit`, as a
test stop only.

Notes: `_plan_piece_flick` still rejects any advance with
`plan.ball_target.x < ball_position.x`, and the advance waypoints are fixed
points near the opponent's goal.

### 3. Remove remaining hard-coded geometry (approved 2026-11-26; 3.0 to 3.4 done; 3.5 waits on Q32, then 3.6)

Results so far (100 seeds from 0, home):

| Sub-step | Pieces | Goal rate | Flicks per goal | flick_limit | Decision ms (mean / median / p95 / max) |
|---|---|---|---|---|---|
| 3.0 baseline (after step 2) | 3 | 98% | 12.2 | 2 | 55 / 12 / 269 / 689 |
| 3.0 baseline (after step 2) | 4 | 99% | 12.7 | 1 (seed 67) | 79 / 22 / 430 / 889 (CPU shared with tests) |
| 3.1 merge + 3.2 shot aims | 3 | 98% | 11.7 | 2 | 53 / 12 / 266 / 723 |
| 3.1 merge + 3.2 shot aims | 4 | 99% | 12.5 | 1 (seed 67) | 76 / 23 / 403 / 610 |
| 3.3 longer advances | 3 | **100%** | **5.5** | 0 | 62 / 38 / 295 / 407 |
| 3.3 longer advances | 4 | **100%** | **5.3** | 0 | 95 / 63 / 407 / 709 |
| 3.3, with 2 blockers | 3 | 100% | 5.8 | 0 | 118 / 66 / 571 / 837 |
| 3.3, with 2 blockers | 4 | 100% | 5.5 | 0 | 163 / 104 / 717 / 1222 |
| 3.4 bank passes | 3 | **100%** | **5.4** | 0 | 60 / 38 / 259 / 410 |
| 3.4 bank passes | 4 | **100%** | **5.4** | 0 | 89 / 64 / 321 / 597 |
| 3.4, with 2 blockers | 3 | 100% | 5.6 (8 of 564 decisions banked) | 0 | 111 / 65 / 527 / 810 |
| 3.4, with 2 blockers | 4 | 100% | 5.7 (13 of 566 decisions banked) | 0 | 150 / 102 / 609 / 1050 |

What was built:

- **3.4** (2026-11-27, bank passes only, Q31). In `sim_ai_brain.py`:
  `FlickPlan.bank`; `_ball_contact_plan` takes an optional
  `ball_launch_speed_mm_s`; `bank_bounce_point()` (mirror image at the
  target's wall distance / `WALL_RESTITUTION`; refuses opposite sides,
  bounces within `BANK_WALL_MARGIN_MM` = 20 mm of a corner, and goal-line
  bounces within the goal-area span plus that margin); `_bank_walls()`
  (both touchlines and the attacked goal line, never the own goal line);
  `_bank_pass_plans()` (launch speed covers both legs and the speed kept
  at the bounce; offered at `BANK_STRENGTH_FACTORS` = 0.9, 1.0, 1.15);
  `bank_pass_candidates()` (every piece with touches left to every
  teammate, mirrored per team, weakest first). `_mirror_plan` now uses
  `dataclasses.replace` so new fields carry over. In `sim_ai_verify.py`:
  `BANK_ONLY_WHEN_NO_DIRECT = True`, `MAX_BANK_CANDIDATES = 20`, and a
  bank stage in `plan_verified_team_flick` (parameter
  `bank_only_when_no_direct`) that runs when no planned entry has a
  category below `STEP_BACK_CATEGORY`, simulates the bank passes and adds
  them to the planned entries before `_select`. In `sim_scenarios.py`:
  `ScenarioSetup.blocker_positions`, `random_setup(..., blocker_count)`
  (separate `Random(f"blockers:{seed}")`, ahead of the ball up to
  `BLOCKER_MAX_X` = 0.92, at least `BLOCKER_MIN_BALL_GAP_MM` = 60 mm from
  it), opposing bodies in `build_world`, `run_batch(blocker_count=...)` and
  `--blockers`. 13 new tests (7 brain, 3 verify, 3 scenarios).
- Learned: a passer straight behind the ball cannot bank it sharply off a
  touchline (the contact angle is too oblique), so bank passes come from
  pieces diagonally behind the ball. The bank stage also runs when the best
  direct flick is only a step back, which is why the standard runs changed
  slightly (5.5 to 5.4, and 5.3 to 5.4 with four pieces). With two random
  blockers, bank passes are used in about 1.5 to 2.5% of decisions. The
  bank count came from a scratch script that wraps
  `sim_turns.plan_verified_team_flick`; the harness itself does not report
  it.

- **3.3** (2026-11-27, approved by the user the same day). In
  `sim_ai_brain.py`: `ADVANCE_DISTANCES_MM = (30, 60, 100)`,
  `MAX_ADVANCE_MM = 100` (the balanced limit; a later `risk` trait or style
  sets it, T2), `PROGRESS_STEP_MM = 10`. `_ball_advance_waypoints` places a
  target at each distance toward each progress area (deduplicated).
  `_piece_advance_plans` lists one piece's advances; `_advances_by_distance`
  keeps the weakest advance per distance, so team candidates offer up to
  three advances per piece, listed by progress (`progress_steps`, 10 mm
  steps capped at 100 mm) then strength. `plan_piece_flick` (single plan)
  still returns the weakest advance. `BALL_ADVANCE_MM = 30` remains for the
  setup-pass receiver check (`_angled_advance_waypoints`).
  `block_flick_cap(distance_mm)` gives the Q22 cap (20% to 60%, linear
  from 100 to 400 mm), for reuse by step 4. In `sim_ai_verify.py`:
  `FlickOutcome.exposed` from `is_exposed()` (the nearest next piece
  behind the ball, else the nearest next piece; exposed if any opposing
  field piece's base could slide onto the piece-to-ball segment within
  `_flick_reach_mm(block_flick_cap(...))`; it does not check that block's
  own legality). `_rank_key` and `_sampled_rank_key` are now (category,
  forward contact, near teammate, exposed, -progress steps, strength,
  travel), type `_RankKey`. 14 new tests (6 in `test_sim_ai_brain.py`, 8
  in `test_sim_ai_verify.py`).
- Learned: with progress before strength, advances run about 60 to 100 mm
  and flicks per goal halved; no seed hits the 30-flick cut-off any more,
  so the harness no longer separates small changes by `flick_limit`.
  Decisions simulate more candidates (median time up from 13 to 38 ms with
  3 pieces), but the 4-piece p95 is unchanged at about 400 ms.

- **3.1** `_ball_followup_plan` removed. `_plan_piece_flick` is the single
  shot / pass / advance decision; the setup-pass search calls it with
  `_angled_advance_waypoints()` (straight and 30 degrees either side,
  `BALL_ADVANCE_MM`), which reproduces the old follow-up behaviour exactly.
- **3.2** `_shot_plans()` aims at `SHOT_AIM_OFFSETS_MM` = 0, -20, 20, -38,
  38 mm across the goal mouth, `SHOT_AIM_DEPTH_MM` = 24 mm behind the goal
  line (the old `Vector2(1.02, 0.5)` is the 0 mm aim). 38 mm keeps the ball
  11 mm inside the posts. `plan_piece_flick` still returns the centre shot
  first; team candidates offer every aim, and simulation picks one that
  scores. 3 new tests (two in `test_sim_ai_brain.py`, one in
  `test_sim_ai_verify.py` with an opposing piece on the centre line).

Decided: **Q6** clear lanes are judged by simulation; **Q7** with **Q31**:
bank passes are proposed only when no direct pass survives simulation, and
there are no bank shots.
**Q29** answered: a standard **balanced** style for equal players
(possession and counter-attack styles later, with traits); the user is
concerned that a long advance lets a defender get between attacker and ball.
**Q30** answered: the balanced rule as proposed, "possession is key".
Ranking order: possession safety first (piece behind the ball, ball near a
teammate, and from step 4 not "exposed", that is no defending piece able to
block-flick into the gap between the next attacking piece and the ball
within its cap), then progress up to 100 mm, then lower strength. Built in
3.3; the rules text was updated to match on 2026-11-27.

Context from the user (2026-11-26, extended 2026-11-27): rectangular
obstacles exist only for the training test of flicking around large
obstacles; in a full match the only rectangular piece is the goalkeeper. So
3.5 is about treating real pieces as circles in the planner's pre-check
(see 3.5 and Q32).

Sub-steps approved by the user (each followed by the tests and both harness
runs, 3 and 4 pieces):

- 3.0 4-piece baseline: **done**.
- 3.1 Merge the duplicated shot / advance / pass logic: **done**.
- 3.2 Shot aim across the goal mouth: **done**.
- 3.3 **Longer advances: done 2026-11-27** (see "What was built"). Agreed
  design, as built:
  - Offer advances at several distances toward each target (for example 30,
    60 and 100 mm). `BALL_ADVANCE_MM` becomes the balanced limit, 100 mm, a
    named setting (a later style or `risk` trait sets it per team, T2).
    `_ball_advance_waypoints` aims at fixed areas near the goal; the
    advance must still not move the ball backward (`_plan_piece_flick`
    rejects `ball_target.x < ball_position.x`).
  - Ranking (`_rank_key` and `_sampled_rank_key` in `sim_ai_verify.py`, and
    the planner's own ordering): possession safety first (forward contact
    available, ball near a teammate, and "not exposed"), then more forward
    progress, then lower strength. Today the key is category, forward
    contact, near teammate, strength, travel, so progress must be inserted
    before strength.
  - "Exposed": some opposing piece could block-flick into the segment from
    the next attacking piece to the ball within its cap (Q22: 20% of a full
    flick within 100 mm of the ball, rising to 60% at 400 mm or more). With
    no opposing pieces in training or the harness it has no effect yet; test
    it with a static opposing piece.
  - Tests: a longer safe advance beats a short one; the 100 mm limit holds;
    an exposed advance ranks below an unexposed one.
  - Expected: fewer flicks per goal; seeds 59, 91 (3 pieces) and 67
    (4 pieces) finishing.
  - Afterwards tell the user that the rules' "prefer lower strength, then
    shorter travel" wording is out of date.
- 3.4 **Bank passes: done 2026-11-27** (Q7; **Q31: no bank shots**, bank passes
  allowed, accidental rebounds allowed). Original wording, now superseded
  for shots: only when no direct shot or pass survives
  simulation (trigger as one named setting, T1 may widen it later). Aim at
  the target's reflection in a touchline, or a goal line outside the mouth,
  with the target's distance from the wall divided by the 0.65 restitution;
  simulation confirms the path. The physics scales only the velocity
  component across the wall by `WALL_RESTITUTION` (`_reflect_velocity`), so
  the 1/0.65 mirror is exact apart from friction.
  Amended plan, approved and built 2026-11-27: `FlickPlan.bank` flag
  (action stays `pass`); `bank_pass_plans` in `sim_ai_brain.py` (bounce
  line offset by the ball radius, strength from the two legs with the
  speed lost at the bounce, offered at 0.9x, 1x and 1.15x); walls are the
  touchlines and the attacked goal line outside the goal-area span (never
  the team's own goal line, to avoid own goals); a bank stage in
  `plan_verified_team_flick` after the planned candidates, controlled by
  `BANK_ONLY_WHEN_NO_DIRECT = True`, run when nothing planned survives or
  the best planned flick is below advance level, capped at
  `MAX_BANK_CANDIDATES`; same ranking as other flicks. No bank shot code;
  a test confirms no planned shot is aimed off a wall. Harness: new
  `--blockers N` option (approved by the user for testing only, not
  needed in a full match) adds N static opposing pieces from a separate
  seeded generator, so `--blockers 0` reproduces today's results exactly.
- 3.5 **Circle obstacles, next.** User clarification (2026-11-27): in a full
  match the only rectangular piece is the goalkeeper; there are no static
  rectangles as in training. So in a match the planner's pre-check would
  otherwise see nothing but the goalkeeper, which makes 3.5 likely needed
  (lean toward building it; measure first with `--blockers` for a
  before/after figure). Scope: every outfield piece of both teams as a
  circle of its real radius; the goalkeeper as an axis-aligned rectangle
  (the existing `Obstacle` shape fits) at the goalkeeper stage, once Q11
  (thickness) is answered; training rectangles kept until training mode is
  retired.
  **Measured 2026-11-27** (scratch script wrapping
  `sim_turns.plan_verified_team_flick` and `sim_ai_verify.simulate_plan`,
  100 seeds from 0, home; a "piece rejection" is a planner suggestion
  rejected because the ball touched an opposing piece or the flicking piece
  touched a piece before the ball):

  | Pieces / blockers | Suggestions | Piece rejections | Decisions affected | Fell back (sampled or bank) after one | Flicks per goal |
  |---|---|---|---|---|---|
  | 3 / 0 | 2672 | 0 | 0 of 541 | 0 | 5.4 |
  | 3 / 2 | 2728 | 55 (2%)* | 24 of 564 | 2 | 5.6 |
  | 4 / 0 | 3260 | 0 | 0 of 541 | 0 | 5.4 |
  | 4 / 2 | 3361 | 109 (3%) | 40 of 566 (7%) | 9 (1.6%) | 5.7 |
  | 4 / 4 | 3423 | 207 (6%) | 75 of 593 (13%) | 15 (2.5%) | 5.9 |

  \* The 3-piece blocker run counted a piece that hit a blocker and never
  reached the ball as a miss, so it undercounts (the 4-piece rows use the
  corrected order). Goal rate 100% in every run. The 12-suggestion cap cut
  suggestions in 8 to 20 decisions per run, with or without blockers.
  Reading: the cost grows with the number of opposing pieces but is still
  small with static, randomly placed blockers; real defenders that stand in
  lanes on purpose and move will cost more, so these are a lower bound.
  Recommendation to the user: defer 3.5 to step 4 and re-measure with real
  defenders (Q32). Original note: treat real pieces as circles in the planner's
  pre-check (rectangles are only for the training test). May be dropped if
  simulation alone is enough with defenders.
- 3.6 Setup-pass search that scales: only receivers within flick range of
  the ball's new position, closest first, stop at a setup that leads to a
  shot. The search currently tries every receiver x 2 offsets x 12
  directions with a full follow-up plan each time. Check decision time with
  4 pieces (today p95 about 400 ms).
- Deferred unless needed: carrying plan intent across turns (for example
  "this setup is for piece 3"), so a later plan does not undo a setup.

### 4. Defenders

New module (suggested name `sim_ai_defence.py`), headless, mirroring the
attacker planner and direction-aware.

Questions: Q6, Q12, Q13, Q14, Q15/Q22 and Q16 are answered (see "User
decisions"), as are Q24 (drill placement anywhere; pieces never enter the
net), Q27 (never skip until traits exist) and Q28 (if a piece already blocks,
block the next route with another piece; no move only when no legal block
exists). Q25 applies at the traits stage. No traits in step 4. Nothing open
blocks step 4.

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
  uncontrolled attacking piece. Never skip by choice (Q27). If a piece
  already blocks the chosen route, block the next most useful route with a
  different piece; no move only when no legal block exists (Q28).
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
  planner sees defenders (or, if Q32 is answered A or later built under B,
  the circle obstacles from 3.5 instead). After the defenders work,
  re-measure the planner's piece rejections as in 3.5 if Q32 is B.
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

### 6. Player traits (after the full match)

Decided by the user on 2026-11-26: traits are a fine-tuning stage for realism
and depth, built only once a full match works with equal AI players. The
candidate list is the "Player traits (later stage)" section of
`AI_QUERIES.md` (G1 to G4 general questions, T1 to T13 traits). Start the
stage by going through that list with the user, keeping, changing or removing
each item. Decided so far: 0.0 to 1.0 in code, 0 to 100 on screen (Q25);
defender skip probability equal to intelligence, seeded (Q25); more bank
passes with higher intelligence (Q7; widen `BANK_ONLY_WHEN_NO_DIRECT`; no
bank shots, Q31); a `risk` trait (Q26, driving `MAX_ADVANCE_MM`).

## Open questions for the user

`AI_QUERIES.md` is the single list of questions and the place where the user
records answers. Do not keep a second list here. Read it at the start of every
session, because the user may have answered questions since this file was
written, and an answer there overrides any default or assumption in this file.

Open as of 2026-11-27 (see the status table at the top of `AI_QUERIES.md`):

| ID | Topic | Needed for |
|---|---|---|
| Q11 | Goalkeeper collision thickness | Goalkeeper stage |
| Q20 | Numeric rule for a setup pass (optional) | Nothing blocked |
| Q32 | Build 3.5 now, defer to after step 4, or drop | Step 3.5 |
| G1 to G4, T1 to T13 | Player traits log | Traits stage (6) |

All others (Q1 to Q10, Q12 to Q19, Q21 to Q31) are answered and recorded
in "User decisions already made" above or in earlier sessions.

If a question comes up that is not in `AI_QUERIES.md`, add it there (next free
number, Q33 at the time of writing; trait ideas go in the traits log as T14
onward; suggested default; `**Your response: TBD**`
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
