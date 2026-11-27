# AI and simulation questions

This file collects decisions that are not settled by the current rules. Answer
questions in any order, one at a time or several at once. Refer to each item by
its ID.

## How to respond

Replace `Your response` under a question with your decision. You can choose an
option, provide a different rule, or write `TBD` to leave it open for now.
Where a question asks for measurements or conditions, include the units or
trigger when known. For example:

```text
Q1: Use surface-to-surface contact; the pieces collide when their bases overlap.
Q2: TBD
```

## Needs your input

Status as of the latest session. "Answered" means your decision is recorded and
no action is needed from you. "Open" means the work cannot settle it without
you. The last column says what is waiting on each one.

| ID | Topic | Status | Waiting on it |
|---|---|---|---|
| Q1 | Contact geometry, goalkeeper rectangle | Answered; your follow-up question is answered below | Goalkeeper work |
| Q2 | Ball motion, spin and curl | Answered | Nothing |
| Q3 | Simultaneous events | Answered in principle; tie-break is Q12 | Time-of-contact ordering |
| Q4 | Goalkeeper saves | Answered | Nothing (placeholder) |
| Q5 | Teammate contact and fouls | Answered | Nothing |
| Q6 | Clear shooting and passing lanes | Answered: simulate and see, for now | Nothing |
| Q7 | Bank passes (originally "bank shots") | Answered: only when no direct pass works; more with higher intelligence (traits stage, T1); no bank shots (Q31); bank passes built in step 3.4 | Traits stage (T1) |
| Q8 | Setup-pass validity | Answered; optional numeric rule is Q20 | Nothing |
| Q9 | Block-flick timing | Answered; strength cap is Q15 and skipping is Q14 | Defenders |
| Q10 | Formation Y-coordinates | Answered: even spacing, for now | Nothing |
| Q11 | Goalkeeper collision thickness | **Open** | Goalkeeper work |
| Q12 | Same-time-of-contact tie-break | Answered: defending piece wins | Nothing |
| Q13 | Defenders near the goal and shooting area | Answered: outside scoring areas at kick-off, anywhere during play; follow-up Q24 | Nothing |
| Q14 | Defender skipping a move on purpose | Answered: an intelligence trait, 0 to 1; skipping is a smart choice; follow-up Q25 | Nothing |
| Q15 | Strength cap for a block-flick | Answered: context-based, option A in Q22 | Nothing |
| Q16 | What counts as "displacing" defenders (smashing) | Answered: 5 mm, for now | Nothing |
| Q17 | No-move fallback, repositioning and runaway attacks | Answered (part 2 settled by Q21) | Nothing |
| Q18 | How match time advances | Answered: real time | Nothing |
| Q19 | Squad size and formation for the first full match | Answered: 5-a-side, 2-2 (Q23) | Nothing |
| Q20 | Numeric rule for a setup pass | Optional | Nothing is blocked |
| Q21 | What a stuck attacker may do in a match | Answered: a block-flick move, then possession changes | Nothing |
| Q22 | How a context-based block-flick cap works | Answered: option A; prefer the piece closest to the ball | Nothing |
| Q23 | Which 5-a-side formation for the first match | Answered: 2-2 for both teams, for now | Nothing |
| Q24 | Defender placement in drills and at the goal | Answered: anywhere in the editor; pieces never enter the net | Nothing |
| Q25 | How intelligence decides whether to move | Answered for the traits stage; point 2 continues in Q27 | Traits stage |
| Q26 | A risk trait for the step 3 longer-move setting | Answered: yes, at the traits stage (T2); step 3 uses one fixed rule | Nothing |
| Q27 | Step 4 defenders without traits: when to skip | Answered: never skip until traits exist | Nothing |
| Q28 | A defender that always moves: edge cases | Answered: block the next route with another piece; no move only if no legal block | Nothing |
| Q29 | When should an advance move the ball further? | Answered: a standard balanced style; styles later; guard against defenders getting between (Q30) | Nothing |
| Q30 | The balanced advance rule | Answered: as proposed, possession first, progress up to 100 mm | Nothing |
| Q31 | Bank shots and bank passes (revises Q7) | Answered in session: no bank shots; bank passes allowed; accidental rebounds allowed | Nothing |
| Q32 | Build step 3.5 (pieces as circles in the planner) now or after the defenders | **Open** | Step 3.5 |
| T1 to T13, G1 to G4 | Player traits log | Later: review at the traits stage | Traits stage |

Most useful to answer next: **Q32** (whether to build step 3.5 now), then
**Q11** (goalkeeper). Q20 is optional. Nothing else blocks step 3 or step
4. The traits log (T1 to T13, G1 to G4) waits for the traits stage, after
the full match.

## Questions

### Q1 — Contact and collision geometry

What counts as contact between the ball and a player piece, or between two
pieces? Should collision checks use their physical shapes and radii (the ball
radius is 11 mm and the player-piece base radius is 9.25 mm), or another
definition?

**Your response: Q1: Radii is fine, no adjustment is required. Rectangle is correct for the goalkeeper,
what impact does this have on collisions/physics?**

> **AI note (answering your follow-up):** The ball and player pieces are
> circles, so they use a simple distance check. A rectangular goalkeeper needs
> a circle-against-rectangle check instead: find the nearest point on the
> rectangle to the circle's center and rebound along that direction. A hit on
> the front face rebounds straight back, and a hit near a corner rebounds
> diagonally. The goalkeeper is not flicked, so it would not need spin or
> rotation. It slides along its rod across the pitch width and stays inside
> the goal area. Today the goalkeeper is still a circle that does not move.
> The one open choice is the rectangle's thickness, see Q11.

### Q2 — Ball motion and settling

What should slow the ball and determine when it has stopped (for example,
rolling friction and a velocity threshold)? Should spin or curve be simulated
now, or treated as a later enhancement?

**Your response: Q2: No adjustment is required. Spin and curls will be implemented later.** 

### Q3 — Simultaneous events

If a single physics step could count as more than one event—for example, a goal
and a figure collision, or contact with multiple figures—which event takes
precedence? If there is no special precedence, should the simulator resolve
events in their actual time-of-contact order?

**Your response: Q3: Yes, time-of-contact. Add a placeholder to the rules to be 
implemented later.** 

> **AI note:** Not implemented yet. Contacts are still recorded per step as
> sets, so which one happened first is unknown within a step. Q12 asks for the
> tie-break.

### Q4 — Goalkeeper saves

What makes a ball contact a goalkeeper save: any collision with the goalkeeper,
or only contact while the ball is in a specified area or direction? Does a save
count as one of the goalkeeper's three consecutive touches, and what event
resets that count?

**Your response: Q4: Any collision with the goalkeeper. A save does count as a touch, the goalkeepers 
touch count resets the same way as other player pieces; contact with any other player piece. 
Goalkeeper behaviour is not currently incorporated.
Add as a placeholder for now.** 

### Q5 — Flicking-piece movement and teammate contact

Can a flicking piece collide with or move a teammate while approaching the
ball? If so, is that legal, and can the teammate's movement affect possession
or touch counts?

**Your response: Q5: No, an attacking player piece can not collide with anything before making contact with
the ball, after contact with the ball collisions with other pieces is allowed. The sanction for an attacker hitting a teammate before reaching the ball is a change of possession to the opposing team. 
A defender must not touch the ball or an opposing
player's player piece at all. Once the moving ball (hit by the attacker) hits a stationary or moving defending figure (or the goalkeeper), the defender immediately becomes the new attacker and takes over play.** 

### Q6 — Clear shooting and passing lanes

How should the AI decide that a shot or pass has a clear path? Should it test
the ball's full path against the physical footprints of figures and the
goalkeeper, including any expected wall rebounds, or use another rule?

**Your response: Let's go with the below proposal for now and see how it works.** 

> **Current state:** The attacker no longer relies on a geometric lane test
> alone. Each candidate flick is simulated on a copy of the world with the real
> physics, so it already accounts for the footprints of every piece and for
> wall rebounds, and it rejects any flick that hits another piece before the
> ball or loses possession. The geometric planner still assumes straight
> paths when it proposes flicks. **Decision needed:** is "simulate it and see"
> acceptable as the rule, or do you want an explicit lane rule written down
> (for example, a minimum clearance in millimetres from other pieces)? The same
> choice applies to the defender, which will use the same check.

### Q7 — Bank shots

When should the attacker consider a bank shot, and how should it choose one?
For example, should it compare predicted rebound paths against direct shots and
passes, or only use a bank shot when a direct route is blocked?

**Your response: I agree with the suggested default.** 

> **AI note:** Recorded: the planner proposes bank shots and bank passes only
> when no direct shot or pass survives simulation.

> **AI note (answering your question):** Yes. A bank shot is a shot or pass
> that deliberately rebounds off a boundary wall (a touchline or a goal line
> outside the goal mouth) on its way to the goal or to a teammate, like a
> cushion shot in snooker. **Still to decide:** should the planner propose them
> on purpose, and if so only when the direct route is blocked, or compared with
> direct shots and passes every time? Suggested default: only when no direct
> shot or pass survives simulation.

> **Current state:** The planner does not propose bank shots on purpose. The
> exploratory flicks can produce a rebound by accident, and simulation would
> accept it if the result is good. **Decision needed:** should bank shots be a
> deliberate option, and if so, only when the direct route is blocked, or
> compared with direct shots whenever both are available?

**Additional response: In line with incorporating an intelligence trait to the AI player I would expect a player with high intelligence to try bank shots more over a player with lower intelligence.**

> **AI note (2026-11-27):** Revised by Q31: deliberate bank **shots** on
> goal are not allowed; bank **passes** are, under the rule above.

> **AI note:** Recorded for the player traits stage (see T1 under "Player
> traits (later stage)"). No code needs changing now: bank shots are not built
> yet. Step 3 builds them for equal AI players under the rule above (only when
> no direct shot or pass survives simulation), with that trigger kept as one
> named setting so a trait can widen it later.

### Q8 — Setup-pass validity

What makes a setup pass distinct from an ordinary short pass? Must it travel a
minimum distance or create a clear next contact for a different friendly piece,
or are those tactical goals rather than strict validity conditions?

**Your response: Q8: A setup pass is typically used on a player piece's last flick and is
primarily used to touch the ball and ensure they move out of the way of the ball to allow
the next player piece a clear route. Last flick doesn't always mean third flick, a player may decide to change 
player pieces before reaching the three flick cap. An ordinary pass is used to move up the pitch, whereas 
as setup pass is used to set up play with another player piece, it is used when either a player piece is on their final touch
or they are in a position where they cannot make an ordinary pass. ** 

> **Current state:** Implemented as a short third-touch nudge (15 or 30 mm of
> ball movement) that leaves another piece a clear next contact. No numeric
> rule is enforced beyond that. See Q20 if you want one.

### Q9 — Defensive block-flick timing

At what point after an attacking flick does the defender make the block-flick:
after the ball has fully stopped, or at another point in the turn? Does the
block-flicked piece remain where it ends for subsequent play?

**Your response: Q9: Retain current set up, block-flick happening after the attack settles. There is no set wait time in
official Subbuteo but for the purposes of the simulation I am incorporating a 0.10 second period between attacking plays. The 
defender should use this time to make their move.
To clarify the 0.10 seconds is a pause between attacking plays, but the defender is able to move one player piece during this time.
If they don't make a move the play countines as normal, though I wouldn't expect to see it in a simulator unless its a forced trait of
a lower skilled team for example.** 

> **Current state:** Not implemented yet. The agreed design is that the
> block-flick is a real flick, resolved until everything stops, and then
> checked for legality. Because 0.10 seconds is too short for a flick to
> finish, I treat it as the time the defender has to decide, not the time the
> movement takes. The block-flicked piece stays where it ends. Q14 asks how a
> weaker team skips a move, and Q15 how hard a block-flick may be.

### Q10 — Formation Y-coordinates

How should the unspecified Y-coordinates and spacing in the formation
templates be chosen? Should unspecified lines use even spacing across the pitch,
or do you want to specify positions for each squad and formation?

**Your response: Lets go with even spacing for now and see how it works.** 

### Q11 — Goalkeeper collision thickness

The goalkeeper is a rectangle. Its width across the pitch is 21 mm. Its
thickness along the pitch length is undecided: the reference is 6 mm, and the
drawing uses 8 mm as a visual compromise. Which should the collision shape use?

**Your response: TBD** 

### Q12 — Same-time-of-contact tie-break

You chose time-of-contact order for simultaneous events (Q3). If two events
happen at exactly the same moment, which wins? For example, the ball reaches
the goal line at the same instant a defender touches it. Options: a goal always
wins; a defender touch always wins; or the order they appear in the list of
pieces.

**Your response: Lets try prioritising a defending player piece, that seems most fair.** 

> **AI note:** Recorded. When the ball touches a defending piece in the same
> instant as another event (for example reaching the goal line), the defending
> touch wins. Applies once the ordered contact log exists (step 4).

### Q13 — Defenders near the goal and in the shooting area

There is no goalkeeper in training yet. In the first defender drill, may a
defender stand inside the shooting area or in front of the goal mouth? If so,
may it fully block the mouth? The suggested default is yes, anywhere on the
pitch except overlapping another piece, so the drill shows whether the attacker
can still find a lane.

**Your response: If by this you mean from "kick off" then no, all pieces must be outside their respective scoring areas, in linw with their formations. However, during play a defending player piece can go wherever on the pitch it needs to.** 

> **AI note:** Recorded. At kick-off every field piece stays outside the
> scoring areas, in its formation (this already matches the rules). During
> play a defending piece may go anywhere, including the shooting area and in
> front of the goal mouth. Two small follow-ups are in Q24.

### Q14 — A defender skipping a move on purpose

You mentioned that a lower-skilled team might not use its block-flick. How
should this be set? For example, a skill value per team from 0 to 1 giving the
chance of skipping each response, or a fixed list of settings such as
"always responds", "sometimes responds" and "rarely responds". Should the
choice be random (with a fixed seed so runs repeat) or follow a rule?

**Your response: Long term I think the skill value will be 0 to 1 (or 0 to 100), think how the old FIFA computer games would rank their players/teams. Something along those lines. Long term strategy is the AI player will have several traits, one of which will impact on decisions like this. Call it intelligence or something akin. I would want the AI player to make this decision based on intelligent strategy (do I need to move, or am I already in a good position?) A higher intelligence skill would favour this kind of decision making over a lower intelligence skill that is more likely to always move.** 

> **AI note:** Recorded. Each AI player will have traits; the first is
> **intelligence**, from 0 to 1 (0 to 100 when shown). Skipping the
> block-flick is a smart choice, not a weakness: a player with high
> intelligence asks "am I already in a good position?" and skips when it is,
> while a player with low intelligence tends to move anyway. The details
> needed to build this are in Q25, and how the step 3 risk setting fits
> alongside it is in Q26.

### Q15 — Strength cap for a block-flick

A block-flick is a capped-strength flick. What cap should it have, as a
percentage of a full flick? A low cap keeps it a positioning move, while a high
cap lets a defender cross much more of the pitch. The suggested starting point
is 50%.

**Your response: It needs to be context based, i.e. player piece relative position to the ball.** 

> **AI note:** Recorded as a principle. The detail is asked in Q22.

### Q16 — What counts as "displacing" defenders

The smashing foul applies when an attacking flick displaces two or more
defending figures in their half, unless it is a shot. How far must a defender
move to count as displaced: any movement, or a minimum distance such as 5 mm?
Does a piece that is nudged and then comes back count? The suggested default is
a minimum of 5 mm from its start position when everything has stopped.

**Your response: Go with the proposed amount for now and we'll see how it works in testing.** 

### Q17 — No-move fallback, repositioning and runaway attacks

This is the next piece of work. Out of 100 test attacks, 18 end because no safe
flick exists, and 8 run to the 30-flick limit without scoring. Please decide:

1. **Order of fallbacks** when no safe flick exists. The suggested order is: a
   deliberate step back that leaves the ball near another piece, then a riskier
   flick that may lose possession, then ending the attack.
2. **Repositioning:** may a piece move without touching the ball when the
   attacker is stuck? The rules do not describe this, so the answer is no unless
   you say otherwise.
3. **Runaway attacks:** should there be a maximum number of flicks in one
   attack before possession passes to the other team? If so, how many? Real
   Subbuteo has no such limit, but the simulator needs a safety stop. The
   suggested default is 30 flicks.

**Your response: 1. Deliberate step back is the standard, though we might introduce riskier styles of play that favour riskier flicks. 2. If an attacker is stuck then can they at least sabotage the defending teams attempt to take possession, by making a block flick for example. For the purposes of the training mode where there are no defenders this may be a moot point, in a real match it will be more relevant. 3. There is no limit. ** 

> **AI note:** Recorded as: (1) a deliberate step back is the standard
> fallback; riskier flicks become a later per-team play-style setting, not the
> default; (3) no flick limit in the rules. The harness keeps its 30-flick cut-off
> only as a test stop, not as a rule. Part 2 is followed up in Q21; in training
> a stuck attack still ends with `no_plan`.

### Q18 — How match time advances

For the 15-minute halves, does the clock run while the ball and pieces are
moving, during the 0.10-second response window, and during the pauses between
flicks? Or does each flick cost a fixed amount of match time? Is the clock
based on real time or on simulated time?

**Your response: Its all real time.** 

> **AI note:** Recorded: the match clock runs in real time throughout,
> including movement, decision time, the 0.10 s window and pauses. Planning
> time therefore uses match time (currently up to about 0.4 s a flick).

### Q19 — Squad size and formation for the first full match

Which squad size and formation should the first full match use: 5-a-side,
6-a-side or 11-a-side? The suggested start is 5-a-side, because it has the
fewest pieces and the fastest decisions. It needs a decision on which template
to use, for example 2-2 (square), and the Y-coordinates in Q10.

**Your response: Yes, for testing go for 5 a side.** 

> **AI note:** Recorded: 5-a-side (one goalkeeper and four field pieces). The
> formation is asked in Q23.

### Q20 — Numeric rule for a setup pass (optional)

You described a setup pass in words (Q8). Do you want a numeric rule as well,
for example the ball must move at least 10 mm and no more than 60 mm, or must
end within a stated distance of another piece? Skipping this is fine; the
current behaviour is described under Q8.

**Your response: TBD** 

### Q21 — What a stuck attacker may do in a match

In Q17 you asked whether a stuck attacker could "at least sabotage the
defending team's attempt to take possession, by making a block flick". In a
match, when the attacker has no legal flick that touches the ball:

1. Does possession pass to the other team straight away?
2. Before or instead of that, may the stuck attacker make one block-flick style
   move (one piece, capped strength, must not touch the ball or an opposing
   piece) to get in the way of the new attacker? If it does, does possession
   still change afterwards?

Suggested default: possession passes to the other team, and the stuck team
then gets the normal 0.10-second response window as the new defender, so it
can make its block-flick then. No extra move beyond that. Training mode has no
defenders, so a stuck attack there simply ends.

**Your response: If I'm the player and I can't make a flick that will touch the ball, I would attempt to make a block flick. Because I haven't made contact with the ball the normal rules of a change of possesion apply. A player should make some form of move, there isn't a sort of 'give up' option.**

> **AI note:** Recorded: there is no "give up" option. A stuck attacker makes a
> block-flick style move with one piece (a capped flick that does not touch
> the ball), placed to obstruct the opponent's next move. It did not touch the
> ball, so possession passes to the other team as for any missed flick. It
> reuses the defender's block-flick planner, so it is built with the defenders
> (step 4). Until then, training and the harness still report `no_plan`.

### Q22 — How a context-based block-flick cap works

You answered Q15 that the cap should depend on the piece's position relative to
the ball. Which of these do you mean?

- **A.** The cap grows with the piece's distance from the ball, so a distant
  piece may flick harder to get back into play, and a piece near the ball may
  only shuffle (for example 20% within 100 mm of the ball, rising to 60% at
  400 mm or more).
- **B.** The cap shrinks with distance, so only pieces near the ball can make a
  meaningful block.
- **C.** No fixed cap: the strength is whatever is needed to reach the chosen
  blocking spot, and the legality check (no touching the ball or an attacker)
  is the only limit.

Suggested default: A, with the figures above as a starting point to tune.

**Your response: Yes, go with A. Though realistically I'd want to pick the player piece closest to the ball.**

> **AI note:** Recorded: option A (the cap grows with the piece's distance from
> the ball; starting figures 20% within 100 mm rising to 60% at 400 mm or more,
> to tune). The defender picks the piece closest to the ball among those that
> can reach a legal blocking spot, rather than the one needing the least
> strength.

### Q23 — Which 5-a-side formation for the first match

5-a-side is chosen (Q19) with even spacing (Q10). The rules list three 5-a-side
templates: 1-2-1 (diamond), 2-2 (square/box) and 3-0-1 (park the bus). Which
should both teams use first? Suggested default: 2-2 for both teams, because it
is symmetrical and easiest to check.

**Your response: Go with your suggestion, we can review again in testing.**

> **AI note:** Recorded: 2-2 (square/box) for both teams, with even Y spacing,
> to review in testing.

### Q24 — Defender placement in drills and at the goal (follow-up to Q13)

1. **Training drill start:** a training drill begins in the middle of play,
   not at kick-off. May you place (drag) a defender anywhere in the editor,
   including inside the shooting area and right in front of the goal mouth?
   Suggested default: yes, anywhere that does not overlap another piece.
2. **Field pieces and the net:** today a player piece treats the whole goal
   line as a wall, including the goal mouth, so only the ball can enter the
   net. A defender can therefore stand on the goal line in front of the mouth
   but not inside the goal. One piece (18.5 mm) cannot close the 120 mm
   mouth on its own, but several could, until the goalkeeper exists. Keep
   this? Suggested default: yes, field pieces never enter the net.

**Your response: 1) Yes, allow user movement anywhere. 2) Yes, player pieces should not enter the net, only the ball.**

> **AI note:** Recorded: (1) in the training editor, defenders may be placed
> anywhere that does not overlap another piece; (2) player pieces never enter
> the net (the physics already works this way), only the ball.

### Q25 — How intelligence decides whether to move (follow-up to Q14)

To build the "do I need to move?" decision:

1. **Scale:** store intelligence as 0.0 to 1.0 in code and show it as 0 to
   100 in any display. Suggested default: yes.
2. **"Already in a good position":** suggested default: a defending piece
   already sits across the route that the block would protect, that is the
   straight line from the ball to the goal-mouth center when the ball is in
   or near the shooting area, otherwise the line from the ball to the nearest
   uncontrolled attacking piece. "Across" means the piece's base overlaps the
   ball's path (centre within 20.25 mm of the line, the piece and ball radii
   added). This is a quick geometric test. The alternative is to simulate the
   attacker's best shot or pass and see whether it is stopped, which is more
   accurate but slower.
3. **How intelligence turns into a choice:** suggested default: when already
   in a good position, the player skips with a probability equal to its
   intelligence (1.0 always skips, 0.0 always moves), drawn from a seeded
   random generator so harness runs repeat exactly. When not in a good
   position, every player moves. The alternative is a fixed rule with no
   randomness (for example, skip only when intelligence is at least 0.5).
4. **Other effects of low intelligence:** should low intelligence also make
   worse choices for now (less accurate block positions, a poorer choice of
   piece)? Suggested default: no; for now it affects only the skip decision,
   and other effects come with later traits.
5. **Starting value:** suggested default: both teams at 1.0 in training and
   the harness, so the first defender results show the best defending; other
   values are compared later.

**Your response: 1) Yes, 0.0 to 1.0 in the code is good, 0 to 100 for display is better for visual pleasing. 2) My gut says the default as having the AI player simulate an attackers best shot might cause lower scoring games, however this may be counteracted by the introduction of player traits which would de-level the playing field if that makes sense. 3) your default sounds logical for now, testing will confirm. 4) Agreed, I think for now lets concentrate on AI players being equal. 5) As per 5, make all players the same intelligence, at this point we're not introducing any traits, that will follow later. **

> **AI note:** Recorded: (1) 0.0 to 1.0 in code, 0 to 100 on screen;
> (3) skip with probability equal to intelligence, seeded, for the traits
> stage; (4) and (5) all AI players equal until then, with no traits. Point
> (2) needs one clarification, asked in Q27: the "good position" test only
> decides whether the defender skips its move; it does not change how well a
> moving defender blocks, so on its own it should not lower scoring much.
> Until traits exist, equal players behave as if intelligence were 1.0.

### Q26 — Traits for the attacker and the step 3 risk setting

Step 3 adds a setting that allows longer moves when the lane is clear, and
Q17 mentioned riskier styles of play as a later per-team option. Should this
be a second trait next to intelligence, for example **risk** (0 to 1:
cautious to bold), kept together with intelligence in one per-team trait
profile so later traits fit in the same place? Suggested default: yes, a
`risk` trait with a middle default of 0.5. In step 3 it would decide how far
an advance may move the ball when no opposing piece is near; how it affects
riskier flicks that may lose possession is left for later.

**Your response: Yes, this is good. Perhaps compile a list of other similar traits and how they correlate to the simulator. When we reach this stage we can run through and keep/remove each trait accordingly.**

> **AI note:** Recorded. You later decided that traits are a stage of their
> own, after a full match works with equal AI players. So step 3 adds no
> `risk` trait: longer moves use one fixed rule for both teams, kept as a
> named setting that a `risk` trait can drive later (T2). The list of
> possible traits is under "Player traits (later stage)" below.

### Q27 — Step 4 defenders without traits: when to skip

Traits come later, so in step 4 both AI players are equal and behave like
intelligence 1.0. That means a defender skips its block-flick whenever it is
already in a good position, with no randomness, and moves otherwise.

On Q25 point 2: the "good position" test only decides **whether** to skip.
When the defender moves, it picks its blocking spot the same way under either
test. So the test choice mostly affects how often defenders sit still, not
how many goals are scored.

1. Is "skip whenever already in a good position" right for equal players in
   step 4? Suggested default: yes.
2. Which test? Suggested default: the quick geometric test (a defending piece
   already sits across the line from the ball to the goal mouth, or to the
   nearest unmarked attacker). The slower simulation test is kept in the
   traits log as something a high-intelligence player might use (T1).

**Your response: I think in the absence of a trait system a defender should never choose to skip. For the demo I'm not looking to test intelligence yet. That comes once we have a fully working full match.**

> **AI note:** Recorded: until traits exist, a defender never chooses to
> skip; it always makes a block-flick. The "good position" test is therefore
> not needed in step 4 and moves to the traits stage (T1). Two edge cases
> follow in Q28.

### Q28 — A defender that always moves: edge cases (follow-up to Q27)

1. **Already blocking:** a defending piece already sits across the shot line
   (or the pass lane). It must still move. Suggested default: it blocks the
   next most useful route with a different piece, for example the pass lane
   to the nearest unmarked attacker, rather than nudging the piece that is
   already in place.
2. **No legal block exists:** no defending piece can reach a blocking spot
   within its strength cap without touching the ball or an attacking piece.
   Any move would then risk an illegal block-flick, which resets the
   attacker's touch counts. Suggested default: in that case only, the
   defender does not move. This is forced, not a choice, so it still fits
   "never chooses to skip".

**Your response: 1) Yes, agreed, good logic. I'm now wondering if this should be the standard, rather than not moving at all. Note the exception listed under (2). 2) Yes, agreed. **

> **AI note:** Recorded: (1) when a piece already blocks, the defender blocks
> the next most useful route with a different piece; (2) it does not move
> only when no legal block exists. For equal AI players this is already the
> standard. Your thought that it should stay the standard even with traits
> (moving a second piece instead of skipping) is noted in T1, to settle at
> the traits stage: intelligence would then decide which extra route is worth
> blocking rather than whether to move at all.

### Q29 — When should an advance move the ball further? (step 3)

Today every planned advance moves the ball about 30 mm, so an attack from
midfield takes many flicks (12.2 per goal on average, and two test attacks
are still short of goal after 30 flicks). The rules also say that among safe
flicks the AI prefers **lower strength, then shorter ball travel**, and "do
not use power merely to maximize distance". So simply offering longer
advances changes nothing: the 30 mm nudge always wins on strength. Which rule
should equal AI players follow?

- **A. Keep the rule as written.** Longer advances are offered but used only
  when no shorter one is safe. Little change in play.
- **B. Prefer progress when it is safe.** Among safe advances, choose the
  one that moves the ball furthest forward while still leaving a piece behind
  the ball for the next touch, as long as no opposing piece is within, for
  example, 150 mm of the ball's path. Strength is then only the tie-break.
  The rules text would need updating.
- **C. A fixed, longer standard step.** Replace the 30 mm step with a longer
  one (for example 80 mm), keeping "lower strength first" among the options.
  Simple, but still one size for every position.

Suggested default: **B**, with a maximum advance of 150 mm per flick and the
150 mm opposing-piece clearance, both to tune in testing. With no defenders
in training yet the clearance never applies, so step 4 is where it starts to
matter. A future `risk` trait (T2) would set these distances per team.

**Your response: This may eventually be linked to style of play. For example, possession based players will prefer shorter passes over counter attacking style players who want to advance as quickly as possible. I guess we need a standard 'balanced' style of play that incorporates elements of both. My only issue is advancing the ball can lead to a defender getting between the attacker and the ball.**

> **AI note:** Recorded: equal AI players use one standard **balanced**
> style; possession and counter-attack styles come later with traits (noted
> under T2, T9 and G4). Your concern is right: after a long advance a
> defender's block-flick could put a piece between the next attacking piece
> and the ball. A concrete balanced rule that guards against this is proposed
> in Q30.

### Q30 — The balanced advance rule (follow-up to Q29)

Proposed rule for equal AI players:

1. **Prefer progress, up to a balanced limit.** Among safe advances, choose
   the one that moves the ball furthest forward, up to **100 mm** per flick
   (between today's 30 mm and the 150 mm a counter-attacking style might
   use). Lower strength is the tie-break. A piece must still be left with a
   clear next contact behind the ball (already checked by simulation).
2. **Guard the gap.** An advance is **exposed** if any defending piece could
   reach the route between the next attacking piece and the ball with one
   block-flick within its strength cap (Q22). An exposed advance ranks below
   every advance that is not exposed, but is not forbidden. In practice short
   advances stay unexposed and long ones are used when defenders are far
   away.
3. With no defenders in training today, rule 2 has no effect until step 4;
   it is written now and tested properly with the defenders.
4. The rules text ("prefer lower strength, then shorter travel") would change
   to describe this balanced rule.

Is this the balanced standard you want? You can change the 100 mm limit, or
choose a simpler version of rule 2 (for example, "exposed" if any defending
piece is within 150 mm of the gap).

**Your response: Initially I used a more guarded approach simply to test the AI players ability to move the ball, originally the demo was applying too much force to the flick, so I requested it be dampened. But for the purposes of a standard balanced rule I will trust your judgement; progress but not at the expense of losing possession. Remember possession is key.**

> **AI note:** Recorded: the balanced rule above, with possession first.
> Flicks are ranked by possession safety before progress: a flick that keeps
> a piece behind the ball, keeps the ball near a teammate and (from step 4)
> is not exposed always beats one that only goes further. Among equally safe
> advances, the one with more progress wins, up to 100 mm, then lower
> strength. The 100 mm limit is a named setting, to tune in testing.

### Q31 — Bank shots and bank passes (revises Q7)

Step 3.4 was planned to build both bank shots (a shot on goal that rebounds
off a wall first) and bank passes (a pass to a teammate that rebounds off a
wall first). You said bank shots should not be allowed. Does that cover
passes too, and may an exploratory flick still rebound off a wall by
accident?

**Your response (given in the session on 2026-11-27):** No bank shots;
bank passes are allowed. Accidental rebounds are still allowed.

> **AI note:** Recorded. The attacker never aims a shot off a wall. It may
> aim a pass off a wall only when no direct pass works (Q7). A flick found
> by exploration that happens to rebound is still accepted if simulation
> shows a legal, good result, because the walls are part of the pitch. The
> rules were updated at the user's request: the term is now **bank pass**
> throughout ("Clear lanes and bank passes", the dictionary, attacker
> priority 2 and the implementation status), with an explicit "no bank
> shots" rule.

### Q32 — Build step 3.5 (pieces as circles in the planner) now, or after the defenders?

The planner suggests flicks from geometry, and simulation then checks each
one. The planner cannot see other pieces (only the training rectangles, and
in a match only the goalkeeper), so it can suggest a flick straight through
a piece; simulation then rejects it. Step 3.5 would let the planner see every
outfield piece as a circle, so it stops suggesting those flicks.

Measured with static opposing pieces placed at random ahead of the ball
(100 test attacks, four attacking pieces):

- 2 opposing pieces: 3% of suggestions rejected for hitting a piece; 7% of
  decisions affected; in 1.6% of decisions the AI fell back to a worse
  choice. Still 100% goals, 5.7 flicks per goal (5.4 with no opposing
  pieces).
- 4 opposing pieces: 6% of suggestions rejected; 13% of decisions affected;
  2.5% fell back. Still 100% goals, 5.9 flicks per goal.

Real defenders (step 4) will stand in lanes on purpose and move, so these
figures are a lower bound. Options:

- **A.** Build 3.5 now, before the defenders.
- **B.** Defer it: go on to 3.6, build the defenders in step 4, then measure
  again with real defenders and build 3.5 if the cost is clearly higher
  (for example more than 10% of suggestions rejected, or more than 5% of
  decisions falling back).
- **C.** Drop it and rely on simulation alone.

Suggested default: **B**.

**Your response: TBD**

## Player traits (later stage)

This is a log for the **player traits stage**, which comes after a full match
works with equal AI players (your decision on Q25 and Q26). Nothing here is
needed before then. At that stage, go through each item and mark it keep,
change or remove. Each trait would be rated 0.0 to 1.0 in code and 0 to 100
on screen (Q25), in the spirit of old FIFA team ratings.

Each entry says what the trait would change in the simulator, and where in
the code. "Equal players today" says what both AI players do until then.

### General questions for the traits stage

- **G1. Who has traits:** the AI player (one set per team), or each piece
  (for example a sharper-shooting forward)? Subbuteo pieces are identical
  figures, so per team seems the natural fit. Suggested: per AI player.
- **G2. Overall rating:** combine the traits into one overall rating per team
  for display and match-ups, like FIFA? Suggested: yes, an average shown
  0 to 100, with the individual traits behind it.
- **G3. Randomness:** traits that work through chance (T1 skip, T3 and T4
  errors) need random draws. Suggested: one seeded generator per match so a
  match can be replayed exactly.
- **G4. Presets:** name a few ready-made team profiles (for example
  "Balanced", "Possession", "Counter-attack", "Park the bus")? Suggested:
  yes, later. "Balanced" is the style equal AI players use until then (Q29).

**Keep / change / remove: TBD**

### T1 — Intelligence (reading the game)

- Defender skips its block-flick when already well placed (Q14, Q25: skip
  probability equal to intelligence). **To settle first (Q28):** you
  wondered whether the equal-player behaviour should stay the standard even
  with traits, so that a well-placed defender blocks a second route with
  another piece instead of skipping. Intelligence would then decide which
  extra route is worth blocking, not whether to move.
- More bank passes: a high-intelligence player considers them alongside
  direct routes, not only when direct routes fail (Q7). Bank shots are not
  allowed (Q31).
- Better "good position" judgement: a high-intelligence player could use the
  slower simulation test (Q27) instead of the geometric one.
- Looking further ahead: more lookahead checks (today `MAX_SHOT_CHECKS = 3`
  in `sim_ai_verify.py`), and more setup passes that plan two touches ahead.
- Equal players today: intelligence 1.0 behaviour, bank shots only when no
  direct route works.

**Keep / change / remove: TBD**

### T2 — Risk (cautious to bold)

- How far an advance may move the ball when the lane is clear (step 3
  replaces the fixed `BALL_ADVANCE_MM = 30` with one balanced rule for both
  teams, Q29 and Q30). Linked to style of play (Q29): a possession style
  prefers short moves and passes, a counter-attacking style advances as fast
  as it safely can; the balanced style sits between them.
- Riskier flicks that may lose possession, instead of a step back (Q17).
- Shooting from tighter angles, or with defenders close to the shot line.
- Equal players today: one fixed, moderate setting for both teams.

**Keep / change / remove: TBD**

### T3 — Accuracy (aim)

- A small random error in the flick's direction when it is carried out. The
  planner would still plan as if the flick were perfect, so a less accurate
  player sometimes misses the ball, hits a piece first (a foul) or sends a
  pass wide. Code: added where the flick is applied (`flick_toward_target` in
  `sim_ai_flick.py`), never inside the planner's simulation.
- Equal players today: perfect aim.

**Keep / change / remove: TBD**

### T4 — Touch (strength control)

- A small random error in flick strength, separate from aim: passes run long
  or short, and close control near defenders gets harder. Same code place as
  T3.
- Equal players today: exact strength.

**Keep / change / remove: TBD**

### T5 — Decision speed

- The match clock is real time (Q18), so a slower thinker uses more of the
  match. Speed could set how many candidates are simulated per decision
  (today 12 planned and 40 sampled in `sim_ai_verify.py`): fast but shallow,
  or slow but thorough.
- A defender too slow for the 0.10 s response window misses its block-flick
  (the "forced trait of a lower-skilled team" mentioned in Q9).
- Equal players today: the same candidate limits; decision time does not yet
  affect play.

**Keep / change / remove: TBD**

### T6 — Defensive awareness

- Where the block goes: blocking the shot line or the pass lane, and how well
  it anticipates the attacker's next pass rather than the current one.
- Which piece it moves: today's rule is the piece closest to the ball (Q22);
  a weaker defender might move a poorly placed piece instead.
- Equal players today: the step 4 rules (Q22, Q27).

**Keep / change / remove: TBD**

### T7 — Discipline

- How close a flick may come to fouling: a disciplined player rejects flicks
  that pass very near another piece before reaching the ball, which matters
  once T3 and T4 add errors. Also how willing it is to risk a smashing foul
  (Q16).
- Equal players today: the verifier rejects any simulated foul, with no
  extra margin.

**Keep / change / remove: TBD**

### T8 — Composure

- Accuracy (T3, T4) drops under pressure: inside the shooting area, late in a
  half, when behind, or with defenders close.
- Equal players today: no pressure effects.

**Keep / change / remove: TBD**

### T9 — Passing style (teamwork)

- Dribbling with one piece (using all three touches) or passing early,
  setup passes as against direct passes, and how strongly to prefer a ball
  stopping near a teammate (today `SAFE_REACH_MM = 100`).
- Equal players today: the current ranking.

**Keep / change / remove: TBD**

### T10 — Tactics and formation

- Preferred formation (Q19, Q23), how far up the pitch the defending pieces
  sit, and pressing as against sitting back. More a style choice than a
  0 to 100 rating; it may fit G4 presets better.
- Equal players today: 2-2 for both teams.

**Keep / change / remove: TBD**

### T11 — Goalkeeping

- Once the goalkeeper exists: reaction speed along the rod, positioning
  ahead of a shot, and how it uses its three touches (Q4).
- Equal players today: no goalkeeper behaviour yet.

**Keep / change / remove: TBD**

### T12 — Consistency (form)

- How much the other traits vary from match to match or half to half, so a
  strong team can have an off day.
- Equal players today: no variation.

**Keep / change / remove: TBD**

### T13 — Stamina (optional)

- A real Subbuteo player tires over 30 minutes; accuracy (T3, T4) or decision
  speed (T5) could drop late in each half. It may not suit an AI player, so it
  is listed as optional.
- Equal players today: none.

**Keep / change / remove: TBD**
